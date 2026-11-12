"""CI wrapper: the deterministic hole-clearance gate (ADR-125) on the v10 board.

Loud-skips when pcbnew is unavailable (CI), runs the real check locally:
    tracker/hardware/check_hole_clearance.py --board tracker/hardware/hub_board_v10.kicad_pcb

A gate that cannot fail proves nothing: the poison self-test is part of THIS test --
it copies the board, plants a hole 2 mm from a pad, and asserts the checker refuses.

The zone rule used to test each zone's BOUNDING BOX. v10's pours all span the full
71.1 x 79.1 mm outline, so every one of the 8 tether/string holes "intersected" every
one of the 5 zones by construction: 40 violations, annotated "verify keep-out", on a
board whose real minimum hole-to-foreign-copper gap is 0.250 mm against the 0.250 mm
design floor. That false positive is what made this file fail on master, and a gate
that cannot pass is worse than no gate -- it also hides genuine pour violations of the
same shape. The zone rule now measures the actual filled copper polygon per layer.

The fixtures below are written as text so they are deterministic and reviewable; each
one isolates a single question, and the group is a two-sided control:
  * a hole inside / too close to a DIFFERENT-NET pour must be REJECTED;
  * a real sub-floor gap that the old bbox rule silently PASSED must be rejected now
    (otherwise "more precise" would just mean "more permissive");
  * a zone with no fill data must fall back to the bbox test, not be silently skipped.
"""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CHECKER = "tracker/hardware/check_hole_clearance.py"
BOARD = "tracker/hardware/hub_board_v10.kicad_pcb"


def _find_kicad_python():
    """Interpreter that can import pcbnew, or None.

    Prefer the dedicated KiCad venv, but fall back to the interpreter running pytest when it
    already has pcbnew -- otherwise the gate is silently skipped in every environment where
    somebody installed KiCad's Python bindings system-wide or into the test venv, and a gate
    that silently skips proves nothing.
    """
    env = os.environ.get("KICAD_PY")
    if env:
        return env if os.path.exists(env) else None
    for cand in (os.path.expanduser("~/venvs/kicad/bin/python"), sys.executable):
        if not cand or not os.path.exists(cand):
            continue
        try:
            ok = subprocess.run([cand, "-c", "import pcbnew"], capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            continue
        if ok.returncode == 0:
            return cand
    return None


KICAD_PY = _find_kicad_python()

needs_pcbnew = pytest.mark.skipif(
    KICAD_PY is None, reason="no interpreter with pcbnew; the checker cannot run here")

# --------------------------------------------------------------------------------------
# Fixture board templates
#
# Board is 60 x 40 mm with an Edge.Cuts rectangle. A single GND pour covers y in
# [POUR_TOP, POUR_BOT] across x in [4, 56]; the hole sits BELOW it, so the only thing
# in play is the hole-vs-zone rule (no pads, no tracks, no vias, and 20+ mm of edge).
# `filled_polygon` is written explicitly because ZONE_FILLER segfaults on a bare BOARD()
# with no project behind it -- the fill is a fixture input, not something we recompute.
# --------------------------------------------------------------------------------------
POUR_TOP, POUR_BOT = 5.0, 20.0
POISON_X = 30.0

BOARD_TMPL = '''(kicad_pcb
\t(version 20241229)
\t(generator "pcbnew")
\t(generator_version "9.0")
\t(general (thickness 1.6) (legacy_teardrops no))
\t(paper "A4")
\t(layers
\t\t(0 "F.Cu" signal)
\t\t(2 "B.Cu" signal)
\t\t(5 "F.SilkS" user "F.Silkscreen")
\t\t(1 "F.Mask" user)
\t\t(25 "Edge.Cuts" user)
\t)
\t(setup (pad_to_mask_clearance 0))
\t(net 0 "")
\t(net 1 "GND")
\t(gr_rect (start 0 0) (end 60 40)
\t\t(stroke (width 0.1) (type default)) (fill no)
\t\t(layer "Edge.Cuts") (uuid "aaaaaaaa-0000-0000-0000-000000000001"))
\t(footprint "hole:TETHER"
\t\t(layer "F.Cu") (uuid "11111111-1111-1111-1111-111111111111")
\t\t(at {hx} {hy})
\t\t(property "Reference" "H1" (at {hx} {hy} 0) (layer "F.SilkS")
\t\t\t(uuid "22222222-2222-2222-2222-222222222222")
\t\t\t(effects (font (size 1 1) (thickness 0.15))))
\t\t(property "Value" "TETHER" (at {hx} {hy} 0) (layer "F.SilkS")
\t\t\t(uuid "33333333-3333-3333-3333-333333333333")
\t\t\t(effects (font (size 1 1) (thickness 0.15))))
\t\t(attr through_hole)
\t\t{padspec}
\t)
\t(zone
\t\t(net {zn}) (net_name "{zname}") (layer "F.Cu")
\t\t(uuid "55555555-5555-5555-5555-555555555555")
\t\t(name "POUR") (hatch edge 0.5)
\t\t(connect_pads (clearance 0.25))
\t\t(min_thickness 0.25)
\t\t(filled_areas_thickness no)
\t\t(fill yes)
\t\t(polygon (pts (xy 4 {zt}) (xy 56 {zt}) (xy 56 {zb}) (xy 4 {zb})))
{blob}\t)
)
'''

NPTH_PAD = '''(pad "" np_thru_hole circle
\t\t\t(at 0 0) (size {drill} {drill}) (drill {drill})
\t\t\t(layers "*.Cu" "*.Mask")
\t\t\t(uuid "44444444-4444-4444-4444-444444444444"))'''

# A PLATED hole tied to a net: the only shape where the same-net exemption can apply.
NETTED_PAD = '''(pad "1" thru_hole circle
\t\t\t(at 0 0) (size {drill} {drill}) (drill {drill})
\t\t\t(layers "*.Cu" "*.Mask")
\t\t\t(net {pad_net} "{zname}")
\t\t\t(uuid "44444444-4444-4444-4444-444444444444"))'''


def _board(tmp_path, name, hy, *, drill=2.5, net=1, zname="GND", pad_net=None,
           filled=True, zt=POUR_TOP, zb=POUR_BOT):
    """Write one fixture board; returns its path as a str.

    pad_net=None -> NPTH, unconnected (the v10 case). pad_net=<net> -> plated hole on that net,
    which is the only way to exercise the same-net zone exemption.
    """
    blob = ""
    if filled:
        blob = ("\t\t(filled_polygon (layer \"F.Cu\")\n"
                f"\t\t\t(pts (xy 4 {zt}) (xy 56 {zt}) (xy 56 {zb}) (xy 4 {zb})))\n")
    padspec = (NPTH_PAD.format(drill=drill) if pad_net is None
               else NETTED_PAD.format(drill=drill, pad_net=pad_net, zname=zname))
    p = tmp_path / f"hole_zone_{name}.kicad_pcb"
    p.write_text(BOARD_TMPL.format(hx=POISON_X, hy=round(hy, 4), zt=zt, zb=zb,
                                   zn=net, zname=zname, blob=blob, padspec=padspec))
    return str(p)


def _run(board, *extra):
    return subprocess.run([KICAD_PY, str(REPO / CHECKER), "--board", str(board), *extra],
                          capture_output=True, text=True, timeout=300)


# --------------------------------------------------------------------------------------
# The v10 board must pass, and the number it passes on must be the measured one.
# --------------------------------------------------------------------------------------

@needs_pcbnew
def test_hole_clearance_clean_on_v10():
    r = _run(REPO / BOARD)
    assert r.returncode == 0, f"checker refused the board:\n{r.stdout}"
    # Not just "rc 0": the tightest hole-to-foreign-copper gap on v10 is 0.250 mm, which
    # is exactly the board's min_hole_clearance. If that figure moves, the board or the
    # measurement changed and somebody should look -- so pin it rather than only the exit.
    assert "0.250 mm" in r.stdout, f"expected the measured 0.250 mm floor in output:\n{r.stdout}"
    assert "VIOLATIONS" not in r.stdout, f"clean board must report no violations:\n{r.stdout}"


@needs_pcbnew
def test_zone_rule_reports_no_violations_on_v10():
    """The fill-based zone rule finds nothing on v10 (was 40 false positives)."""
    r = _run(REPO / BOARD)
    assert r.returncode == 0
    assert "ZONE" not in r.stdout, f"zone rule must be silent on v10:\n{r.stdout}"


# --------------------------------------------------------------------------------------
# Two-sided control on the REAL board: the old rule produced 40 false positives, the new
# one produces none. Both halves are asserted, so neither can drift into vacuity.
# --------------------------------------------------------------------------------------

@needs_pcbnew
def test_legacy_bbox_rule_reproduces_the_false_positive():
    """`--zone-check bbox` must still report the 8 holes x 5 zones = 40 phantom hits."""
    r = _run(REPO / BOARD, "--zone-check", "bbox")
    assert r.returncode == 1, "the legacy bbox test is expected to fail on v10"
    assert "VIOLATIONS: 40" in r.stdout, f"expected the historical 40:\n{r.stdout}"
    assert "bbox intersects" in r.stdout


# --------------------------------------------------------------------------------------
# Negative controls: a hole in / near a DIFFERENT-NET pour must be REJECTED.
# --------------------------------------------------------------------------------------

@needs_pcbnew
def test_negative_control_hole_inside_pour_is_rejected(tmp_path):
    """Hole drilled straight through foreign copper: gap = -hole_radius, must fail."""
    board = _board(tmp_path, "inside", hy=(POUR_TOP + POUR_BOT) / 2)   # dead centre of the pour
    r = _run(board)
    assert r.returncode == 1, f"a hole inside a pour must FAIL the gate:\n{r.stdout}"
    assert "ZONE" in r.stdout, f"the violation must name the zone:\n{r.stdout}"
    assert "-1.250" in r.stdout, (
        f"expected a measured NEGATIVE gap of -1.250 mm (hole radius), got:\n{r.stdout}")


@needs_pcbnew
def test_negative_control_hole_too_close_to_pour_is_rejected(tmp_path):
    """Hole edge 0.15 mm from foreign copper: under the 0.25 mm floor, must fail."""
    board = _board(tmp_path, "close", hy=POUR_BOT + 0.15 + 1.25)
    r = _run(board)
    assert r.returncode == 1, f"a 0.15 mm gap must FAIL the gate:\n{r.stdout}"
    assert "0.150 < 0.25" in r.stdout, f"expected the measured 0.150 mm gap:\n{r.stdout}"


@needs_pcbnew
def test_negative_control_clean_gap_passes(tmp_path):
    """Same fixture with a 2.0 mm gap must PASS -- so the control is not "always fail"."""
    board = _board(tmp_path, "clean", hy=POUR_BOT + 2.0 + 1.25)
    r = _run(board)
    assert r.returncode == 0, f"a 2.0 mm gap must pass:\n{r.stdout}"
    assert "2.000 mm" in r.stdout, f"expected the measured 2.000 mm gap:\n{r.stdout}"


# --------------------------------------------------------------------------------------
# The new rule must be STRICTLY more precise, not merely less strict.
#
# The old bbox rule granted the hole an hr-wide grace band past the pour's box edge:
# it flagged only when (centre - hr) < (pour_edge + hr). For a SMALL hole that band is
# narrower than the 0.25 mm design floor, so a genuine violation hid inside it. This
# fixture is exactly that case: drill 0.2 mm, hole edge 0.20 mm above the pour.
# --------------------------------------------------------------------------------------

@needs_pcbnew
def test_new_rule_is_stricter_than_bbox_on_small_hole(tmp_path):
    """A real 0.20 mm sub-floor gap: the new rule rejects it, the old bbox rule MISSED it."""
    hy = POUR_BOT + 0.20 + 0.10        # hole radius 0.10 mm -> true gap 0.200 mm
    board = _board(tmp_path, "subfloor", hy=hy, drill=0.2)

    new = _run(board)
    old = _run(board, "--zone-check", "bbox")

    assert new.returncode == 1, (
        f"a 0.200 mm gap is under the 0.250 mm floor and must be rejected:\n{new.stdout}")
    assert "0.200 < 0.25" in new.stdout, f"expected the measured 0.200 mm gap:\n{new.stdout}"

    assert old.returncode == 0, (
        "this fixture is only meaningful if the legacy bbox rule MISSES it; if the bbox "
        f"rule now catches it, the fixture no longer proves stricter precision:\n{old.stdout}")


# --------------------------------------------------------------------------------------
# Conservatism and the documented same-net exemption.
# --------------------------------------------------------------------------------------

@needs_pcbnew
def test_zone_without_fill_falls_back_to_bbox(tmp_path):
    """An unfilled zone cannot be measured, so it must fall back to bbox -- not pass silently."""
    board = _board(tmp_path, "unfilled", hy=(POUR_TOP + POUR_BOT) / 2, filled=False)
    r = _run(board)
    assert r.returncode == 1, (
        f"a zone with no fill data must still be flagged via the bbox fallback:\n{r.stdout}")
    assert "no fill data" in r.stdout, f"the report must say it fell back:\n{r.stdout}"


@needs_pcbnew
def test_same_net_zone_is_skipped(tmp_path):
    """A hole inside ITS OWN net's pour is intended contact, not a clearance defect.

    Stated deliberately: if a plated, net-tied hole sits in its net's pour the copper is
    supposed to touch it. Keeping same-net strict would flag every such hole on every
    future board, so the rule skips it. The exemption is inert on v10 (all 8 tether/string
    holes are NPTH with no net), which is why v10 still reports the honest 0.250 mm.
    """
    # Plated hole on GND, sitting dead centre of the GND pour.
    board = _board(tmp_path, "samenet", hy=(POUR_TOP + POUR_BOT) / 2, net=1, zname="GND",
                   pad_net=1)
    r = _run(board)
    assert r.returncode == 0, f"same-net contact must not be reported:\n{r.stdout}"
    assert "same-net" in r.stdout, (
        f"the report must state the same-net exemption was applied:\n{r.stdout}")


@needs_pcbnew
def test_same_net_skip_does_not_disable_the_rule(tmp_path):
    """Same-net is exempt, but a DIFFERENT-net pour in the same board must still be caught.

    Guards the exemption from over-reaching: if the skip were implemented as "skip all zones
    once any zone matches", this hole in foreign copper would slip through.
    """
    # Plated hole on GND buried in the GND pour (exempt) -- and we verify the rule still
    # fires on the same geometry when the pour is a different net.
    exempt = _board(tmp_path, "skip_exempt", hy=(POUR_TOP + POUR_BOT) / 2,
                    net=1, zname="GND", pad_net=1)
    foreign = _board(tmp_path, "skip_foreign", hy=(POUR_TOP + POUR_BOT) / 2,
                     net=2, zname="+3V3", pad_net=1)
    assert _run(exempt).returncode == 0, "own-net pour must be exempt"
    r = _run(foreign)
    assert r.returncode == 1, (
        f"the same hole in a DIFFERENT net's pour must still fail:\n{r.stdout}")


# --------------------------------------------------------------------------------------
# Pre-existing pad poison test (unchanged behaviour).
# --------------------------------------------------------------------------------------

@needs_pcbnew
def test_gate_can_fail_poison(tmp_path):
    """Plant a hole 2 mm from a pad; the checker MUST report violations and exit 1."""
    poison = '''import pcbnew
b=pcbnew.LoadBoard("{b}")
m=pcbnew.FOOTPRINT(b); pad=pcbnew.PAD(m)
pad.SetSize(pcbnew.VECTOR2I(int(2.5e6),int(2.5e6)))
pad.SetDrillSize(pcbnew.VECTOR2I(int(2.5e6),int(2.5e6)))
pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE); pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
pad.SetNumber("1"); m.Add(pad)
m.SetReference("HX"); m.SetValue("TETHER_POISON")
u3=b.FindFootprintByReference("U3")
q=list(u3.Pads())[0].GetPosition()
m.SetPosition(pcbnew.VECTOR2I(q.x+int(2.0e6), q.y))
b.Add(m)
pcbnew.SaveBoard("{out}", b)
'''.format(b=REPO / BOARD, out=tmp_path / "holegate_poison.kicad_pcb")
    gen = tmp_path / "holegate_poison_gen.py"
    gen.write_text(poison)
    subprocess.run([KICAD_PY, str(gen)], capture_output=True, timeout=120)
    r = _run(tmp_path / "holegate_poison.kicad_pcb")
    assert r.returncode == 1, "poisoned board must FAIL the gate"
    assert "PAD" in r.stdout, "violation must name the pad"
