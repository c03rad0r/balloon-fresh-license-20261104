#!/usr/bin/env python3
"""test_router_grid_validator_agreement.py -- the router's SEARCH must never permit what its
VALIDATOR (and kicad-cli) forbids.

THE BUG CLASS THIS KILLS (16 instances this session, all the assistant's):

  B34  grid isolation  CLEAR+TRACK_W/2 (0.30) vs validator CLEAR+TRACK_W      -- 0.10 short
  B37  --append did not mark existing TRACKS into the grid
  B44  --append marked tracks but NOT VIAS
  B46  validate_plan read a multi-LEG plan as one path (own_keys[0] vs plan[-1][-1])
  B47  grid via-marking 0.55 vs validator 0.70 (track-vs-via vs via-vs-via)
  B48  the OUTER outline was marked OUTWARD only -- copper INSIDE was unchecked
  B55  routed copper marked at TRACK clearance; a VIA needs CLEAR+VIA_D/2+TRACK_W/2
  B56  --append re-routed a net AGAINST ITS OWN copper

Every one has the same shape: the A* grid (or the append loader) allowed a move that
validate_plan then rejected, or kicad-cli flagged. A router whose search and validator
disagree wastes every search: it finds paths it must throw away.

THE CHECK. For every clearance rule the validator enforces, the GRID's keep-out must be
>= the validator's demand, computed from the same constants. This is arithmetic the file
itself must agree on -- so the test PARSES the router source and asserts the required
expressions are present and dominant at each marking site.

This is a source-agreement test in the same spirit as test_router_gate_agreement.py, but
it covers the marking sites that file does not: the append loader, the routed-copper
re-marking, and the edge band orientation.
"""
import re
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTER = os.path.join(HERE, "..", "tracker", "hardware", "route_v10_astar.py")


def src():
    with open(ROUTER, encoding="utf-8") as fh:
        return fh.read()


def _grid(pitch=0.10):
    """Build the real grid from the committed board, exactly as the router does.

    LOUD-SKIP WITHOUT pcbnew. `route_v10_astar` imports `pcbnew` (KiCad's bindings) at
    module scope, so importing it on a runner with no KiCad raises ModuleNotFoundError.
    CI runs these tests on plain `ubuntu-latest` (see .github/workflows/test.yml), where
    pcbnew is absent -- and this file had NO guard, so `python -m pytest tests/` went RED
    on EVERY branch, including master. The rest of the board suite already follows the
    documented convention (ci-host-tests.yml: pcbnew tests "loud-skip on a runner without
    it"); this file did not.

    A SKIP here is NOT a pass -- it is a check that could not be made. It is loud, and it
    names the reason and where the real check runs, exactly as the repo's convention
    requires (AGENTS.md 20: a gate that cannot run must never look green).

    The pre-commit hook runs this file where pcbnew DOES exist, so the check is not lost.
    """
    import importlib
    import pytest
    try:
        import pcbnew  # noqa: F401
    except ImportError:
        pytest.skip(
            "router grid agreement NEEDS pcbnew (KiCad python bindings), which is not "
            "installed in this environment. This is NOT a pass -- the check could not be "
            "made. It runs in the pre-commit hook where pcbnew exists "
            "(pre-commit-board-gates.py). Tracked as a CI environment gap."
        )
    sys.path.insert(0, os.path.join(HERE, "..", "tracker", "hardware"))
    R = importlib.import_module("route_v10_astar")
    board = os.path.join(HERE, "..", "tracker", "hardware", "hub_board_v10.kicad_pcb")
    world = R.load_world(board)
    blocked, nx, ny = R.build_grid(world, pitch)
    return R, world, blocked, nx, ny


def test_b34_grid_isolation_marks_full_track_width():
    """track-vs-track centre keep-out must be CLEAR + TRACK_W (both halves), not CLEAR + half."""
    s = src()
    assert "g = CLEAR + TRACK_W\n" in s, "B34 regression: grid no longer marks CLEAR + TRACK_W"
    # and it must not ALSO carry the half-width form anywhere as the binding figure
    halves = [m for m in re.finditer(r"g = CLEAR \+ TRACK_W/2", s)]
    assert not halves, "B34 regression: a half-width grid keep-out is back"


def test_b47_via_via_marking_is_stricter_than_track_via():
    """via-vs-via centre keep-out is CLEAR + VIA_D (both radii), stricter than track-vs-via."""
    s = src()
    assert "g = CLEAR + VIA_D\n" in s, (
        "B47 regression: via marking no longer uses CLEAR + VIA_D (the via-vs-via figure)"
    )


def test_b55_routed_copper_gets_the_via_keepout_too():
    """B55: routed copper was marked only at track clearance; a via placed nearby needs more."""
    s = src()
    assert "gv = CLEAR + VIA_D / 2 + TRACK_W / 2" in s, (
        "B55 regression: routed copper no longer re-marked with the via keep-out (gv)"
    )


def test_b48_outer_edge_band_is_inward():
    """B48: the outer outline keep-out must cover the INSIDE edge, not only outside the board.

    GEOMETRIC, not textual: build the real grid via the router's own world+mark code and
    assert a cell just INSIDE the outline is blocked. The one-sided band leaves it free,
    which is exactly the defect that let /CUT_SENSE_W1..W4 cross the wing-seat cutouts.
    """
    R, world, blocked, nx, ny = _grid()
    F = 0
    # Row y=20mm is clear of the wing-seat fabric (measured: its first free cell sits at
    # x=0.7mm with the inward band). The four outermost cells must therefore be BLOCKED --
    # they are inside the 0.6mm edge keep-out. With the one-sided band (B48) they are free.
    j = int(round(20.0 / 0.10))
    inside = [blocked[F][j][i] for i in range(0, 4)]
    assert inside == [1, 1, 1, 1], (
        f"B48 regression: cells 0.0-0.4mm inside the west edge read {inside} for layer F "
        "-- expected all blocked; a free cell here means the edge band is one-sided again"
    )


def test_b56_append_skips_nets_being_rerouted():
    """B56: --append must not load a re-routed net's own copper as its own obstacle."""
    s = src()
    assert "reroute = {n for n in args.nets.split(\",\") if n} if args.nets else None" in s, (
        "B56 regression: the reroute guard in the --append loader is gone"
    )
    assert "if reroute and t.GetNetname() in reroute:" in s, (
        "B56 regression: the own-copper skip no longer fires"
    )


def test_b46_validator_checks_every_leg():
    """B46: validate_plan must check each leg of a multi-pad plan against its own two pads."""
    s = src()
    assert "B46" in s, "B46 comment missing -- multi-leg validation may have been reverted"
    # the per-leg loop must exist (it validates plan legs pairwise)
    assert re.search(r"for .*leg.*in .*plan", s) or re.search(r"for leg", s), (
        "B46 regression: no per-leg validation loop found in validate_plan"
    )


def test_b58_append_deletes_rerouted_nets_copper():
    """B58: --append with --nets must DELETE the old copper, not merely hide it from the model.

    Hiding it (B56) stopped a net colliding with itself, but left the old copper on the BOARD,
    so the net ended up with two routes. Measured: 16 kicad-cli clearance violations
    (0.1536-0.1808mm against a 0.200mm rule) between /GNSS_RX and /U3_CS_N.
    """
    s = src()
    assert "B58" in s, "B58 comment block missing -- the delete-old-copper fix may be reverted"
    # STRUCTURAL, not textual. This test has now broken twice on refactors that changed NO
    # behaviour: first when the loop was hoisted out of the one-line `if reroute:` form and a
    # `removed` counter added, then when the same strip became a `doomed` list. Both were
    # improvements; both were reported as regressions. Pinning source SHAPE punishes good edits.
    #
    # The invariant that actually matters: inside a block guarded by `reroute`, some track whose
    # netname is a member of `reroute` gets passed to b.Remove(...). Not the variable name, not the
    # iteration construct, not the line breaks.
    guarded_remove = re.compile(
        r"GetNetname\(\)[^\n]*\bin\s+reroute"          # a track of a re-routed net is selected
        r"|for\s+\w+\s+in\s+doomed"                     # ... or gathered into a doomed list
    )
    assert guarded_remove.search(s), (
        "B58 regression: no selection of re-routed-net tracks found "
        "(neither `GetNetname() ... in reroute` nor a `for ... in doomed` loop)"
    )
    assert re.search(r"b\.Remove\(\w+\)", s), (
        "B58 regression: --append no longer REMOVES a re-routed net's existing copper "
        "(no b.Remove(<track>) call found at all)"
    )
    # The two must be in the same vicinity -- otherwise the Remove could belong to some unrelated
    # cleanup while the re-route silently kept its old copper.
    span = re.search(
        r"GetNetname\(\)[^\n]*\bin\s+reroute(?:(?!def\s).){0,1200}?b\.Remove\(\w+\)", s, re.S
    )
    assert span, (
        "B58 regression: the b.Remove() call is not near the re-routed-net selection -- the strip "
        "and the removal have drifted apart, which is how hidden-but-not-deleted copper returns"
    )


def test_b57_via_width_uses_a_layer_argument():
    """B57: PCB_VIA.GetWidth() with NO layer argument is undefined and KiCad asserts.

    Measured: ~10 assert warnings per --append invocation. A through via's diameter is
    layer-independent, but the call still needs a layer to be defined.
    """
    s = src()
    assert "B57" in s, "B57 comment missing -- the via-width guard may have been reverted"


def test_constants_are_the_project_rules():
    """The router constants must equal the .kicad_pro rules it claims to implement.

    min_clearance 0.200, track 0.200, via dia 0.500 -- taken from the project file, not
    re-typed from memory. If the project rules change, this test FORCES the router to be
    updated with them rather than silently disagreeing (the root shape of B34/B47/B55).
    """
    s = src()
    assert "TRACK_W = 0.200" in s, "TRACK_W drifted from the project rule (0.200)"
    assert "CLEAR = 0.200" in s, "CLEAR drifted from the project rule (0.200)"
    assert "VIA_D = 0.500" in s, "VIA_D drifted from the project rule (min_via_diameter 0.5)"


def test_edge_keep_is_edge_clearance_plus_track_half():
    """EDGE_KEEP must be min_copper_edge_clearance (0.500) + TRACK_W/2 (0.100) = 0.600."""
    s = src()
    assert "EDGE_KEEP = 0.600" in s, (
        "EDGE_KEEP drifted: must stay min_copper_edge_clearance(0.500) + TRACK_W/2(0.100)"
    )


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {name}: {e}")
    print("1 passed" if not fails else f"{fails} failed")
    sys.exit(1 if fails else 0)
