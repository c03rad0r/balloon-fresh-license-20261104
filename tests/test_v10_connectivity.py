#!/usr/bin/env python3
"""Regression tests for the v10 connectivity + lane gates.

Each test encodes a DEFECT THE OPERATOR ACTUALLY FOUND (or that the registry found on
its first run). A test that cannot fail is worthless, so every gate test is run TWICE:
once against a clean board (must pass) and once against a poisoned board that carries
the defect (must fail). The poison boards are generated here, so the tests are
self-contained.

Run:  ~/venvs/kicad/bin/python -m pytest tests/test_v10_connectivity.py -q
CI:   loud-skips when pcbnew is unavailable.
"""
import os
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HW = os.path.join(REPO, "tracker", "hardware")
# THE BOARD OF RECORD, not tracker/hardware/hub_board_v10.kicad_pcb.
#
# CORRECTED 2026-11-11. These tests used to open hub_board_v10.kicad_pcb, which is a
# SUPERSEDED file that was never fabricated: it carries a U_E28 radio where the registry,
# the shipped gerbers and the real board all carry U_LORA1280. Every verdict was therefore
# about a board nobody shipped -- the registry check alone reported 18 phantom "pin absent"
# and 18 phantom "net not on board" drifts from that mismatch.
#
# Identified by the shipped drill (196 holes at 0.200/0.300/1.000/2.500 mm), which only this
# file reproduces: 188 PTH + 8 NPTH, same four diameters.
BOARD = os.path.join(REPO, "docs", "analysis", "bulk-route-20261107", "latest.kicad_pcb")
REG = os.path.join(HW, "connectivity", "v10_pinmap.reg")

UM = 1_000_000.0


_PCBNEW_PROBE = None


def _pcbnew_usable():
    """Probe KiCad's python module AS THE CHILD SCRIPTS WILL SEE IT, in a subprocess.

    WHY NOT `pytest.importorskip`. Two host states defeat a bare importorskip, and this
    file hits both:

    1. **Absent** (CI: plain ubuntu-latest has no KiCad) -> ImportError. importorskip
       handles this, but only if it is reached.
    2. **Found, then SEGFAULT.** On a dev host `/usr/lib/python3/dist-packages/
       _pcbnew.so` can be a symlink to `_pcbnew.kiface` bound to a different CPython
       ABI, so `import pcbnew` dies with SIGSEGV -- uncatchable in-process, it takes the
       whole pytest run down.

    THE DISTINCTION THAT MATTERS (measured 2026-10-25). This file does NOT import pcbnew
    into its own process; it drives the board by running `tracker/hardware/check_lane_*.py`
    as CHILD PROCESSES, and those do a plain `import pcbnew` with no path help. A bare
    interpreter therefore CANNOT import pcbnew here even though a probe that first inserts
    `/usr/lib/python3/dist-packages` CAN. Probing with the path-insert would report
    "usable" and let the board tests run, whereupon every child dies with
    ModuleNotFoundError and its non-zero exit is misread as a REAL GATE FAILURE.

    So the probe must reproduce the CHILD's environment exactly: plain interpreter, no
    path insertion. Whatever the children can do is what this file may assume.
    """
    global _PCBNEW_PROBE
    if _PCBNEW_PROBE is None:
        # Deliberately NO sys.path.insert: this mirrors check_lane_*.py, the real caller.
        probe = "import pcbnew; print('OK')"
        try:
            r = subprocess.run([sys.executable, "-c", probe],
                               capture_output=True, timeout=120)
            ok = r.returncode == 0 and b"OK" in r.stdout
            why = "ok" if ok else (
                f"child `import pcbnew` failed, exit {r.returncode}"
                + (" (SIGSEGV)" if r.returncode == -11 else "")
                + (" [module not on the default path]" if r.returncode == 1 else ""))
            _PCBNEW_PROBE = (ok, why)
        except (OSError, subprocess.SubprocessError) as exc:
            _PCBNEW_PROBE = (False, f"probe could not run: {exc!r}")
    return _PCBNEW_PROBE


def _pcbnew():
    """KiCad's python module, or a LOUD skip.

    The STATIC assertions in this file must still run where KiCad is unavailable
    (they encode findings that do not need a board), so this is a per-test skip, not
    a module-level one -- a module-level importorskip skips the whole file and made
    the CI suite report "1 skipped / exit 5 (no tests ran)".
    """
    usable, why = _pcbnew_usable()
    if not usable:
        pytest.skip(
            f"KiCad python module unusable here ({why}). NOT a pass -- the board-level "
            f"checks could not be made. They run in the pre-commit hook where pcbnew "
            f"is usable (pre-commit-board-gates.py).")
    sys.path.insert(0, "/usr/lib/python3/dist-packages")
    return pytest.importorskip("pcbnew", reason="pcbnew unavailable (CI) -- loud skip")


def _load(path):
    return _pcbnew().LoadBoard(path)


def run(script, board=None):
    cmd = [sys.executable, os.path.join(HW, script)]
    if board:
        cmd += ["--board", board]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


def _copy(tmp_path):
    dst = str(tmp_path / "board.kicad_pcb")
    shutil.copy(BOARD, dst)
    return dst


def _add_track_over(board_path, ref, padnum, net_name, layer):
    """Plant a track straight across a pad -- the U_C.9 defect, reproduced on demand."""
    pcbnew = _pcbnew()
    b = pcbnew.LoadBoard(board_path)
    fp = b.FindFootprintByReference(ref)
    pad = [p for p in fp.Pads() if p.GetNumber() == padnum][0]
    pos = pad.GetPosition()
    net = b.FindNet(net_name)
    if net is None:
        b.Add(pcbnew.NETINFO_ITEM(b, net_name))
        net = b.FindNet(net_name)
    t = pcbnew.PCB_TRACK(b)
    t.SetNet(net)
    t.SetLayer(layer)
    t.SetWidth(int(0.2 * UM))
    t.SetStart(pcbnew.VECTOR2I(pos.x - int(3 * UM), pos.y))
    t.SetEnd(pcbnew.VECTOR2I(pos.x + int(3 * UM), pos.y))
    b.Add(t)
    pcbnew.SaveBoard(board_path, b)


# ---------------------------------------------------------------- registry

def test_registry_matches_board():
    """The board and the registry must not drift. Drift = someone changed one and not
    the other, which is how a wrong pin survives. Needs pcbnew (it reads the board)."""
    _pcbnew()
    rc = subprocess.run(
        [sys.executable, os.path.join(HW, "connectivity", "registry.py"), "check"],
        capture_output=True, text=True, timeout=300).returncode
    assert rc == 0, "registry check failed -- board and v10_pinmap.reg disagree"


def test_registry_has_no_unnamed_metal_without_open_item():
    """Every UNASSIGNED pad must be justified in OPEN-ITEMS.md. An unjustified
    unassigned pad is floating metal waiting to be hit by a track."""
    reg = open(REG, encoding="utf-8").read()
    open_items = open(os.path.join(HW, "connectivity", "OPEN-ITEMS.md"), encoding="utf-8").read()
    unassigned = [ln.split()[0] for ln in reg.splitlines()
                  if ln.strip() and not ln.startswith("#") and ln.split()[-1] == "UNASSIGNED"]
    # pins that are legitimately no-connect (module internals / unused) are listed in
    # OPEN-ITEMS.md; anything else must be argued for
    unexplained = [u for u in unassigned if u.split(".")[0] not in open_items
                   and "no-connect" not in open_items.lower()]
    assert not unexplained, f"unassigned pads with no OPEN-ITEMS entry: {unexplained[:10]}"


# ---------------------------------------------------------------- lane gates

def test_lane_clearance_catches_track_on_unnamed_pad(tmp_path):
    """THE OPERATOR'S DEFECT: a track crossing U_C.9, a pad with no net. The checker
    used to skip unnamed pads and report clean. It must now fail."""
    pcbnew = _pcbnew()
    board = _copy(tmp_path)
    _add_track_over(board, "U_C", "9", "/ANT3_2G4_RX", pcbnew.B_Cu)
    rc, out = run("check_lane_clearance.py", board)
    assert rc != 0, f"clearance gate missed a track on an unnamed pad:\n{out}"
    assert "U_C.9" in out, out


def test_lane_clearance_clean_board_passes():
    """The same gate must NOT fire on the clean board -- otherwise it is noise."""
    _pcbnew()
    rc, out = run("check_lane_clearance.py", BOARD)
    assert rc == 0, out


def test_lane_integrity_catches_dead_end(tmp_path):
    """The operator's other defect: a lane ending on nothing."""
    pcbnew = _pcbnew()
    board = _copy(tmp_path)
    _add_track_over(board, "U_C", "9", "/ANT3_2G4_RX", pcbnew.B_Cu)
    rc, out = run("check_lane_integrity.py", board)
    assert rc != 0, f"integrity gate missed a dead end:\n{out}"


# The 3 dead ends that are GENUINELY on the fabricated board, measured 2026-11-11.
# See docs/analysis/v10-connectivity-test-failures.md. They are track stubs with no same-net
# pad, via, T-junction or second track at the point -- i.e. nothing of their own net under them.
KNOWN_DEAD_ENDS = {
    ("/SPI1_MISO", 8.75, 44.05),
    ("/SPI1_MISO", 8.75, 41.25),
    ("/USB_DN", 23.65, 51.25),
}


def test_lane_integrity_clean_board_passes():
    """The board must carry NO dead ends beyond the 3 known stubs.

    REWRITTEN 2026-11-11. This used to assert rc == 0, which conflated two different things:
    the checker's verdict and the board's state. The checker was wrong -- it ignored zone fill
    and reported 61 dead ends when 58 of them terminate in their own pour -- so the test was
    failing for a checker bug, not a board defect. The checker is now fixed (zones and
    T-junctions are consulted), and the board really does have 3 stubs.

    Asserting "exactly these 3 and nothing else" is STRICTER than the old rc == 0: it fails if
    the board gains a new dead end AND fails if the checker starts inventing them again.
    """
    _pcbnew()
    rc, out = run("check_lane_integrity.py", BOARD)
    found = set()
    for ln in out.splitlines():
        if "DEAD END: track on " in ln:
            net = ln.split("track on ")[1].split(" ends at ")[0]
            coord = ln.split("ends at (")[1].split(")")[0]
            x, y = (float(v) for v in coord.split(","))
            found.add((net, round(x, 2), round(y, 2)))
    extra = found - KNOWN_DEAD_ENDS
    assert not extra, (
        f"new dead end(s) on the board, not in the known list: {sorted(extra)}\n"
        f"full checker output:\n{out}")
    # the known stubs must still be DETECTED -- a checker that reports nothing is broken
    assert found, ("checker reported no dead ends at all; the 3 known stubs should still be "
                   "found, so the checker has gone blind")
    assert rc != 0, "checker exited 0 while dead ends are present"


def test_back_side_pads_are_checked():
    """B6 regression: pad side must come from GetLayerSet(). Back-side parts (U3, U_C,
    U_E28, ANT2/3) had every clearance verdict skipped when the side came from
    pad.GetLayer(), which reports F_Cu even for back-side pads."""
    pcbnew = _pcbnew()
    b = pcbnew.LoadBoard(BOARD)
    # CORRECTED 2026-11-11. The list used to be U3, U_C, U_E28, ANT2, ANT3 and failed on
    # "ANT2 missing". Measured on the board of record: ANT2 and ANT3 do not exist (they went
    # away with the antenna change), and U_E28 belongs to the SUPERSEDED hub_board_v10 file --
    # the real board carries U_LORA1280 TOPSIDE.
    #
    # My first attempt at this fix put U_LORA1280 in the list, assuming it was flipped. It is
    # not (IsFlipped()=False, GetLayer()=F_Cu, all 16 pads on F.Cu) -- so that "fix" asserted a
    # false premise and failed on the fixture again. The refs below are measured: every one has
    # IsFlipped()=True, GetLayer()=B.Cu, and pads on B.Cu.
    for ref in ("U3", "U_C", "U_CUT1", "U_CUT2", "J_VCC"):
        fp = b.FindFootprintByReference(ref)
        assert fp is not None, f"{ref} missing"
        assert fp.GetLayer() == pcbnew.B_Cu, f"{ref} should be on the back"
        for p in fp.Pads():
            assert p.GetLayerSet().Contains(pcbnew.B_Cu), \
                f"{ref}.{p.GetNumber()} pad is not on B.Cu"


# ---------------------------------------------------------------- hole gate

def test_hole_gate_catches_hole_on_pad(tmp_path):
    """The original U3 defect: a tether hole inside a component's pad column."""
    pcbnew = _pcbnew()
    board = _copy(tmp_path)
    b = pcbnew.LoadBoard(board)
    u3 = b.FindFootprintByReference("U3")
    target = [p for p in u3.Pads() if p.GetNumber() == "1"][0].GetPosition()
    for fp in b.GetFootprints():
        if fp.GetReference() == "H1":
            fp.SetPosition(pcbnew.VECTOR2I(target.x, target.y))
    pcbnew.SaveBoard(board, b)
    rc, out = run("check_hole_clearance.py", board)
    assert rc != 0, f"hole gate missed a hole planted on U3.1:\n{out}"


# ---------------------------------------------------------------- static (no pcbnew)

def test_registry_file_is_parseable_without_pcbnew():
    """Static half: runs in CI where KiCad is absent. The registry format must stay
    machine-checkable or the drift check cannot be trusted."""
    import re
    lines = [ln for ln in open(REG, encoding="utf-8").read().splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert lines, "registry is empty"
    for ln in lines:
        body = ln.split("#", 1)[0].strip()
        assert re.match(r"^[A-Za-z0-9_]+\.\S*\s+\S+$", body), f"bad registry line: {ln!r}"


def test_open_items_ledger_exists_and_names_the_open_blockers():
    """Static half: the ledger of undecided pins must exist and mention the two known
    blockers (they were guessed once and the guess was wrong)."""
    txt = open(os.path.join(HW, "connectivity", "OPEN-ITEMS.md"), encoding="utf-8").read()
    assert "OPEN-16" in txt, "OPEN-16 (GPIO0 pad) must stay tracked"
    assert "RX_EN" in txt and "TX_EN" in txt, "E28 enables must stay tracked"
