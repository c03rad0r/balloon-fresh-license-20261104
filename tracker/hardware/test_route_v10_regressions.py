#!/usr/bin/env python3
"""Regression tests for the three route_v10_astar bugs measured on 2026-11-09.

Each test pins a defect that was silently costing us either data or truth:

1. CRASH -- PCB_TRACK::Remove() invalidates the SWIG wrapper for the BOARD it removed from.
   The next b.GetTracks() raised "'SwigPyObject' object has no attribute 'GetTracks'" AFTER
   the stripped board had already been written to disk.

2. DATA LOSS -- a failed re-route stripped the net's copper and SAVED the stripped board.
   "I could not improve this net" became "this net is now unwired".

3. WRONG PAIR -- the pad chain followed dict order, so it asked for two pads that were already
   joined by existing copper, failed on its own occupied cells, and never attempted the pair
   that was genuinely open.

4. ZONES -- a pad/track-only union-find reports every zone-carried net as disconnected. On this
   board /VSCAP split into 11 islands that are electrically one net. A plane is a conductor.

Run: /usr/bin/python3 tracker/hardware/test_route_v10_regressions.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402

BOARD = os.path.join(HERE, "..", "..", "docs", "analysis", "bulk-route-20261107",
                     "latest.kicad_pcb")
DRU = os.path.join(HERE, "..", "..", "docs", "analysis", "bulk-route-20261107",
                   "latest.kicad_dru")
ROUTER = os.path.join(HERE, "route_v10_astar.py")


def _sig(board):
    tracks = sorted(
        (t.GetNetname() or "", int(t.GetStart().x), int(t.GetStart().y),
         int(t.GetEnd().x), int(t.GetEnd().y), t.GetLayer())
        for t in board.GetTracks() if t.Type() != pcbnew.PCB_VIA_T)
    vias = sorted((t.GetNetname() or "", int(t.GetPosition().x), int(t.GetPosition().y))
                  for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
    return tracks, vias


def _copy_board(dst_dir):
    # the .kicad_dru is NAME-MATCHED: renaming the board silently drops every custom rule and
    # DRC then reports ~540 library violations instead of 16. Keep the stem identical.
    dst = os.path.join(dst_dir, "board.kicad_pcb")
    shutil.copy(BOARD, dst)
    shutil.copy(DRU, os.path.join(dst_dir, "board.kicad_dru"))
    pro = BOARD[:-len(".kicad_pcb")] + ".kicad_pro"
    if os.path.exists(pro):
        shutil.copy(pro, os.path.join(dst_dir, "board.kicad_pro"))
    return dst


def test_failed_reroute_keeps_the_copper():
    """A re-route that finds no path must leave the board byte-identical, not strip the net."""
    from route_v10_astar import _pad_components_of  # noqa: F401  (import sanity)
    tmp = tempfile.mkdtemp(prefix="reroute_")
    try:
        board = _copy_board(tmp)
        before = _sig(pcbnew.LoadBoard(board))
        net_before = sum(1 for t in before[0] if t[0] == "/F33_VSENSE")
        assert net_before > 0, "fixture is wrong: /F33_VSENSE should already have copper"

        proc = subprocess.run(
            [sys.executable, ROUTER, "--board", board, "--nets", "/F33_VSENSE", "--append"],
            capture_output=True, text=True, timeout=900)
        out = proc.stdout + proc.stderr
        assert "RESTORED" in out, f"no restore reported -- the net would have been lost:\n{out[-2000:]}"

        after = _sig(pcbnew.LoadBoard(board))
        assert after == before, (
            "board changed after a FAILED re-route; a failed search must be a no-op.\n"
            f"tracks {len(before[0])} -> {len(after[0])}, vias {len(before[1])} -> {len(after[1])}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_zone_carried_net_is_one_component():
    """/VSCAP is carried by the B.Cu pour; a pad/track-only graph splits it into 11 islands."""
    from route_v10_astar import _pad_components_of
    board = pcbnew.LoadBoard(BOARD)
    groups = _pad_components_of(board, "/VSCAP")
    assert len(groups) < 11, (
        f"/VSCAP reported {len(groups)} components -- zones are not being counted as conductors. "
        "A plane joins its net; ignoring it produces a false 'disconnected' verdict.")
    assert len(groups) == 2, f"/VSCAP should be 2 components (the pour, and R_BAL1.1), got {len(groups)}"


def test_fully_connected_net_reports_one_component():
    board = pcbnew.LoadBoard(BOARD)
    from route_v10_astar import _pad_components_of
    groups = _pad_components_of(board, "/SCAP_MID")
    pads = sorted(k[0] + "." + k[1] for g in groups for k in g)
    assert len(groups) == 1, f"/SCAP_MID is fully routed but reported {len(groups)} components: {pads}"
    assert "R_BAL1.2" in pads and "R_BAL2.1" in pads, f"balance string missing from {pads}"


def test_reroute_picks_an_open_pair():
    """The pair asked for must be between different copper components, never inside one."""
    from route_v10_astar import _pad_components_of
    board = pcbnew.LoadBoard(BOARD)
    groups = _pad_components_of(board, "/F33_VSENSE")
    assert len(groups) == 2, f"expected 2 components, got {len(groups)}"
    a, b = groups[0][0], groups[1][0]
    # each representative must come from a DIFFERENT group by construction
    assert a not in groups[1] and b not in groups[0], (
        "the chain asked for two pads inside the same copper component; the search would fail "
        "on its own occupied cells")


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            fails += 1
            print(f"FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            fails += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{'FAILED' if fails else 'ALL PASS'} ({fails} failure(s))")
    sys.exit(1 if fails else 0)
