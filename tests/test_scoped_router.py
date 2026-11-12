"""Regression tests for the scoped router's obstacle model and path reconstruction.

Every test here pins a bug that was MEASURED on this board, not a hypothetical. Each one was live
while the router reported success, which is the reason they exist.

Run: PYTHONPATH=/usr/lib/python3/dist-packages python3 -m pytest tests/test_scoped_router.py -q
"""
import math
import os
import sys

import pytest

sys.path.insert(0, "/usr/lib/python3/dist-packages")
pcbnew = pytest.importorskip("pcbnew")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "docs", "analysis", "solar-8land-verify"))

BOARD = os.environ.get(
    "ROUTER_TEST_BOARD",
    os.path.join(os.path.dirname(ROOT), "..", "reports", "flight-readiness-20261102",
                 "merge", "out.kicad_pcb"),
)


def _world():
    import route_scoped as R
    b = pcbnew.LoadBoard(BOARD)
    return R, R.World(b)


pytestmark = pytest.mark.skipif(not os.path.exists(BOARD), reason="candidate board not present")


def test_layer_ids_are_f_cu_and_b_cu_not_adjacent():
    """B36: the A* goal used `1 - layer0`, i.e. layer 1, an INNER layer.

    F.Cu=0 and B.Cu=2 in KiCad. `1 - layer` therefore never named a routable layer, so the goal
    state was unreachable and every same-layer pair returned "no path" in 0.0s having expanded
    nothing. Asserted directly against the binding values, because the bug was arithmetic.
    """
    assert pcbnew.F_Cu == 0
    assert pcbnew.B_Cu == 2
    assert 1 not in (pcbnew.F_Cu, pcbnew.B_Cu)


def test_blocked_ignores_other_layer_copper():
    """B37: `blocked()` scanned every track regardless of layer.

    Measured 2026-11-03: 228 of 4000 random probes disagreed with a layer-correct check, and ALL
    228 were "blocked() says blocked, the only cause is other-layer copper". Copper on the far side
    of a 4-layer board is not an obstacle. If this regresses, legal B.Cu escapes get refused and
    pairs are reported unroutable for no physical reason.
    """
    R, w = _world()
    # Find a point where an F.Cu track is close but B.Cu is clear, then assert B.Cu is legal.
    checked = 0
    for (x1, y1, x2, y2, rw, lay, code) in w.segs:
        if lay != pcbnew.F_Cu:
            continue
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        if not (2 < mx < 70 and 2 < my < 78):
            continue
        # a point just beside the middle of this F.Cu track
        px, py = mx, my + 0.35
        if w.blocked(px, py, pcbnew.F_Cu, 0) and not w.blocked(px, py, pcbnew.B_Cu, 0):
            checked += 1
            if checked >= 5:
                break
    assert checked > 0, "no test point found; board may have changed, re-derive"


def test_fast_and_slow_path_agree():
    """B38: the spatial index must give the SAME answer as the linear scan.

    The index exists because the linear scan cost 1.36ms/call (measured), making a pair take ~54
    minutes. An index that is subtly wrong would route through copper, so agreement is asserted over
    a pseudo-random sweep with a FIXED SEED -- reproducible, not flaky.
    """
    R, w = _world()
    import random
    rng = random.Random(7)
    for _ in range(800):
        x = rng.uniform(1, 71)
        y = rng.uniform(1, 79)
        lay = rng.choice((pcbnew.F_Cu, pcbnew.B_Cu))
        net = rng.choice((0, 1, 2, 3, 5, 8, 13))
        assert w.blocked(x, y, lay, net) == w.blocked_fast(x, y, lay, net), (x, y, lay, net)


def test_via_ok_agrees_with_reference():
    """B39: via_ok was 14.7s of a 21.5s search (seg_pt called 8.7M times).

    A via is an ALL-LAYER object, so unlike a track it must consider both copper layers. Indexing it
    must not accidentally filter by layer -- that would allow a via to short an inner-layer plane.
    """
    R, w = _world()
    import random
    rng = random.Random(11)
    for _ in range(600):
        x = rng.uniform(1, 71)
        y = rng.uniform(1, 79)
        net = rng.choice((0, 1, 2, 3, 5, 8, 13))
        assert w.via_ok(x, y, net) == w.via_ok_slow(x, y, net), (x, y, net)


def test_no_via_inside_a_pad():
    """ADR: never via-in-pad. JLCPCB does not fill/cap vias, so an uncapped barrel in a pad wicks
    solder during reflow. The boolean must agree with the reference scan (which net is reported can
    differ where pads overlap; whether we are inside ANY pad may not)."""
    R, w = _world()
    import random
    rng = random.Random(3)
    for _ in range(800):
        x = rng.uniform(1, 71)
        y = rng.uniform(1, 79)
        assert (w.in_any_pad(x, y) is not None) == (w.in_any_pad_slow(x, y) is not None)


def test_sweep_detects_a_crossing_leg():
    """B40: the A* validates CELLS, not the segment between them.

    Measured 2026-11-03: a 7.9257mm +3V3 leg was emitted straight across /SPI2_MOSI giving 3
    shorting_items. Path legs are now sampled at 0.05mm before being written. This asserts the
    sampler actually rejects a leg that crosses copper.
    """
    R, w = _world()
    # Use a REAL other net code taken from the board. Inventing `code + 991` gives a code no copper
    # carries, so the sweep legitimately reports "clear" and the test fails for the wrong reason
    # (measured 2026-11-03: that is exactly how this test first failed).
    codes = sorted({s[6] for s in w.segs})
    found = False
    for (x1, y1, x2, y2, rw, lay, code) in w.segs:
        if lay != pcbnew.F_Cu:
            continue
        own_ok = w.sweep_ok(x1, y1, x2, y2, lay, code)
        if not own_ok:
            continue
        for other in codes:
            if other == code:
                continue
            if not w.sweep_ok(x1, y1, x2, y2, lay, other):
                found = True
                break
        if found:
            break
    assert found, "sampler failed to reject a leg lying on another net's copper"
