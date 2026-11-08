# Authoritative gate status — all five pre-commit gates, not the two I had been running

**Run 2026-11-07 on `latest.kicad_pcb` = `5d5b7ed6` / 18 opens / silk 1.**

## The five gates the pre-commit hook actually runs

`scripts/git-hooks/pre-commit-board-gates.py` defines `GATES` with **five** entries. It takes no
board argument (it inspects the staged set), so it cannot be pointed at an analysis board — which
is why I ended up running a hand-picked subset. The correct argument form differs per gate:

| gate | argument form | blocking |
|---|---|---|
| `check_drc.py` | `--board <path>` | yes |
| `check_schematic_parity.py` | `--board <path>` | yes |
| `check_socket_edge_tracks.py` | `<path>` positional | yes |
| `check_hv_lanes.py` | `<path>` positional | no (ADR-143 report-only) |
| `check_silk.py` | `--board <path>` | yes |

## Current verdict

```
check_drc.py                 FAIL
check_schematic_parity.py    PASS
check_socket_edge_tracks.py  PASS
check_hv_lanes.py            PASS (report-only, non-blocking)
check_silk.py                FAIL

VERDICT: 2 BLOCKING GATE(S) FAIL: ['check_drc.py', 'check_silk.py']
```

## What each failure actually is

**`check_drc.py` FAIL** — 19 failing items, all `lib_footprint_issues` (8) and
`lib_footprint_mismatch` (11). Every one is on a mechanical/passive footprint:
`MountingHole_2.5mm` x8, `CP_Radial_D10.0mm_P5.00mm` x2, `SolderJumper-3` x1, plus unnamed
issues entries. No clearance, no shorting, no thermal, no isolated copper.

The `lib_footprint_issues` messages name missing libraries: *"The current configuration does not
include the footprint library 'tracker_m…'"* and *"…'balloon_f…'"*. That is a **library table
resolution problem on this machine**, not board geometry: the project's own footprint libraries
are not registered in the KiCad config being used. On a machine with the project libraries
loaded, these would resolve. This is worth trying before treating them as real.

**`check_silk.py` FAIL** — 1 `silk_over_copper` on `U_LORA1280`. Two of the original three were
fixed by moving body silk to F.Fab. The remaining one is the footprint's reference text, which
sits 12 mm wide straight across the part body.

## What I had been reporting, and why it was wrong

I reported "0 errors" and "19 failing violations" all campaign. Those figures came from
`check_drc.py` alone, whose allow-list treats `silk_over_copper` as cosmetic and passes it. The
project's binding rule (AGENTS.md 23) has **no allow-list for silk**. A board cannot be called
gate-clean on a single gate's report when the hook runs five.

`check_socket_edge_tracks.py` PASS is genuinely reassuring: it is the gate that refuses any
track within 0.50 mm of, or across, a wing-socket cavity edge (ADR-142), which is exactly the
class of mistake available to a router working in the wing area. My BRIDGE3 and CUTSENSE routes
did not trigger it.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/run_all_gates.py docs/analysis/bulk-route-20261107/latest.kicad_pcb
```
