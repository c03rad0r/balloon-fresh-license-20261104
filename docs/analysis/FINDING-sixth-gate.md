# The gate suite is SIX gates, not five — and the sixth one passes

**2026-11-07, board `e00b98e7`. Corrects `GATE-STATUS-authoritative.md`.**

## What I had been reporting

Five gates: `check_drc`, `check_schematic_parity`, `check_silk`, `check_socket_edge_tracks`,
`check_hv_lanes`. I wrote that list up as authoritative and quoted it repeatedly.

## What the hook actually runs

`scripts/git-hooks/pre-commit-board-gates.py` calls **`_run_router_agreement()` at line 132**,
before the five I knew about. It runs:

```
tests/test_router_grid_validator_agreement.py
```

with its own interpreter selection (`~/venvs/kicad/bin/python`, then `/usr/bin/python3`, then
`sys.executable`), skipping any candidate that cannot import `pcbnew`, and **REFUSING rather than
passing** if no interpreter can run the tests — the comment says so explicitly:
"a gate that cannot run must never look green (AGENTS.md 20)".

**This is the third time this session that a requirement lived in a gate I was not running.** The
first was `check_schematic_parity` defaulting to `hub_board_v10`; the second was `check_silk`, which
fails hard where `check_drc` allow-lists silk as cosmetic. My "five gates, authoritative" doc was
wrong in the same way both times.

## The gate's actual status

```
$ ~/venvs/kicad/bin/python tests/test_router_grid_validator_agreement.py
HOOK_EXIT=0
PASS test_b34_grid_isolation_marks_full_track_width
PASS test_b46_validator_checks_every_leg
PASS test_b47_via_via_marking_is_stricter_than_track_via
PASS test_b48_outer_edge_band_is_inward
PASS test_b55_routed_copper_gets_the_via_keepout_too
PASS test_b56_append_skips_nets_being_rerouted
PASS test_b57_via_width_uses_a_layer_argument
PASS test_b58_append_deletes_rerouted_nets_copper
PASS test_constants_are_the_project_rules
PASS test_edge_keep_is_edge_clearance_plus_track_half
1 passed
```

**PASSES.** Both `pytest` (9.1.1) and `pcbnew` are available in `~/venvs/kicad/bin/python`, which is
the hook's first candidate, so the hook runs it correctly on this machine.

## A false alarm I raised and retracted

Running it under `/usr/bin/python3` fails:

```
ModuleNotFoundError: No module named 'pytest'
```

I first read that as "the sixth gate has been failing all session". That was wrong — the hook does
not use `/usr/bin/python3` first, and it skips an interpreter that cannot import `pcbwn` before
reporting failure. The gate passes in the hook's real environment. The failing run was my own
invocation with the wrong interpreter.

Worth recording because it is the same shape as several other errors this session: a real
observation, read as a defect in the object under test rather than a defect in my instrument.

## Consequence

The corrected gate status for `e00b98e7`:

| gate | status |
|---|---|
| router grid/validator agreement | **PASS** (10/10) |
| check_drc | FAIL — 15 library-load items, 0 electrical |
| check_schematic_parity | PASS |
| check_socket_edge_tracks | PASS |
| check_hv_lanes | PASS (report-only) |
| check_silk | PASS — LEGIBLE, 0 violations |

**Still one blocking failure, and it is the library-load artefact** documented in
`FINDING-library-items-are-version-mismatch.md` — `pcbnew.FootprintLoad()` returns None for
well-formed `.kicad_mod` files whose header declares a newer format than this pcbnew build.

## Reproduce

```
~/venvs/kicad/bin/python tests/test_router_grid_validator_agreement.py; echo "exit=$?"
```
