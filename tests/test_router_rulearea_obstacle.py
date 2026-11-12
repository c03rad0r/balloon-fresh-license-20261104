#!/usr/bin/env python3
"""Rule-area (keep-out zone) must be an OBSTACLE in the router's grid.

WHY: `route_v10_astar.load_world` modelled pads, footprint bodies, board edges and
footprint-owned edge cuts -- but not RULE AREAS. The pressure-controller board
(`pressure-controller-core/routing/core-routing.kicad_pcb`) carries a 30 x 24 mm
all-copper-layer rule area reserved for future motor/protection circuitry. A router
that cannot see it will happily lay copper into the reservation, and no custom gate
would notice: the area is a KiCad *rule*, and the router is the only thing that
decides where copper goes.

This file is the forcing function: it builds the REAL grid from the real board with
the router's own `load_world` + `build_grid`, and asserts a cell at the centre of the
reserved box is blocked on BOTH copper layers. A one-layer fix would pass a
single-layer assertion, so both are checked.

LOUD-SKIP WITHOUT pcbnew (repo convention, AGENTS.md 20): a check that cannot run is
not a pass.
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(HERE, "..", "tracker", "hardware")
BOARD = os.path.join(HW, "pressure-controller-core", "compact", "compact.kicad_pcb")

sys.path.insert(0, HW)


def _grid(pitch=0.1):
    try:
        import pcbnew  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("rule-area grid check NEEDS pcbnew; not installed here. NOT a pass.")
    R = importlib.import_module("route_v10_astar")
    world = R.load_world(BOARD)
    blocked, nx, ny = R.build_grid(world, pitch)
    return R, world, blocked, nx, ny


def test_reserved_rule_area_is_blocked_on_both_layers():
    R, world, blocked, nx, ny = _grid()
    ox, oy = world["origin"]
    pitch = 0.1
    # Centre of the reservation measured on the 65x50 candidate: x 33..63, y 24..48 mm.
    cx, cy = 48.0, 36.0
    i = int(round((cx - ox) / pitch))
    j = int(round((cy - oy) / pitch))
    got = [blocked[lay][j][i] for lay in (0, 1)]
    assert got == [1, 1], (
        f"rule area not modelled as an obstacle: cell at ({cx},{cy}) mm reads {got} "
        "for layers [F.Cu, B.Cu], expected [1, 1]. Copper placed here invades the "
        "reserved motor/protection area."
    )


def test_rule_area_obstacle_is_the_area_not_the_whole_board():
    """A control: the rule area must not block the whole board.

    Without this, 'block everything' would satisfy the test above while making the
    router useless -- the same shape as a gate that passes on a broken board.
    """
    R, world, blocked, nx, ny = _grid()
    ox, oy = world["origin"]
    pitch = 0.1
    free = 0
    for (x, y) in [(10.0, 25.0), (30.0, 18.0), (8.0, 45.0), (20.0, 20.0)]:
        i = int(round((x - ox) / pitch))
        j = int(round((y - oy) / pitch))
        if not blocked[0][j][i] or not blocked[1][j][i]:
            free += 1
    assert free >= 3, (
        f"only {free}/4 sampled cells outside the reservation are free -- the rule-area "
        "obstacle is over-grown and blocks legal routing space"
    )
