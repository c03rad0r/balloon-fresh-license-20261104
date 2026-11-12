# Stale v10 tests target a superseded board file — measured

**Status:** findings only. No test was edited, skipped or weakened.

## What the full suite reports on `origin/master` (`f675f2fb`)

```
5 failed, 956 passed, 30 skipped
FAILED tests/test_c_host.py::TestFIPSTransport::test_fips_transport_host
FAILED tests/test_v10_connectivity.py::test_registry_matches_board
FAILED tests/test_v10_connectivity.py::test_lane_integrity_clean_board_passes
FAILED tests/test_v10_connectivity.py::test_back_side_pads_are_checked
FAILED tests/test_v10_hole_clearance.py::test_hole_clearance_clean_on_v10
```

All five reproduce identically on `4ade5900`, the commit before our three merges.
**None is caused by #389, #390 or #393.** CI (`host-tests`, `Tests`) does not cover
them because the runner's `/usr/bin/python3.14` has no `pcbnew`.

## Root cause: the tests read a board that is not the board of record

`tests/test_v10_connectivity.py:23`:

```python
BOARD = os.path.join(HW, "hub_board_v10.kicad_pcb")
```

Three v10 board files are tracked and all three are 4-layer, 72.1 × 80.1 mm, 49
footprints, 5 zones:

| file | tracks |
|---|---:|
| `hub_board_v10.kicad_pcb` | 782 |
| `hub_board_v10_lora1280_7of9.kicad_pcb` | **884 — the canonical board** |
| `hub_board_v10_lora1280_swap.kicad_pcb` | 659 |

The board of record is `hub_board_v10_lora1280_7of9.kicad_pcb`
(SHA256 `732bfe889020b3c9…`), named as canonical by:

- `docs/adr/140-placement-approval-requires-route-trial.md:94`
- `docs/adr/141-drill-minimum-020-fab-limit.md:41`
- `docs/runbooks/INTERACTIVE-ROUTING-LORA1280.md:66,159`
- `docs/analysis/pr-reconciliation-20261030/REPORT.md:7`

So five tests grade the superseded file. That is why they fail while the canonical
board is the one all fab analysis uses.

## The four stale-assertion causes, each measured

### 1. `test_back_side_pads_are_checked` — asserts footprints removed by ADR-137

```
AssertionError: ANT2 missing
```

The test requires `U3, U_C, U_E28, ANT2, ANT3`. The canonical board carries **no
`ANT*` footprint and no `ANT*` net at all** — deliberate:

> **ADR-137 — No RF on the hub: antennas connect at the radio module, never on our PCB**
> Status: Accepted (operator decision, 2026-10-25)
> §3.1 Delete — `ANT1..ANT4` U.FL connectors … The `ANT*` nets and their 121.9 mm of copper.

`tracker/hardware/connectivity/v10_pinmap.reg` still lists `ANT1..ANT4`, so
`test_registry_matches_board` reports `MISSING: 20` — the registry, not the board,
is stale. Its four `UNASSIGNED` drifts are the radio module antenna pads
(`U2.9`, `U3.10`, `U5.11`, `U_C.10`) whose nets ADR-137 removed; those pads are
now intentionally unassigned.

### 2. `test_lane_integrity_clean_board_passes` — 2 dead ends on the superseded file

```
tracks audited: 730
DEAD END: track on /E28_DIO3 ends at (56.70,72.70) with nothing under it
DEAD END: track on /E28_DIO3 ends at (56.80,72.50) with nothing under it
VIOLATIONS: 2
```

On the canonical board `/E28_DIO3` ends at `(33.25,62.17)` and `(45.27,62.80)` —
both terminate on pads. A 730-track audit confirms this ran against
`hub_board_v10.kicad_pcb` (782 tracks), not the 884-track canonical board.

### 3. `test_hole_clearance_clean_on_v10` — 40 bbox-vs-zone notes, not real DRC findings

```
holes checked: 8  (HW1, H2, HW2, HW3, HW4, H1, H4, H3)
VIOLATIONS: 40
   HW1 <-> ZONE GND bbox intersects (verify keep-out)
```

Every one is a **bounding-box** intersection between a 2.5 mm NPTH and a zone's
bbox — that is expected geometry on a poured board and the message itself says
*verify keep-out*. Native DRC on the canonical board reports no such class.
This checker is advisory and should not gate.

### 4. `test_c_host.py::test_fips_transport_host` — unrelated to the board

Firmware host test, fails independently of PCB state.

## Honest boundary

I did **not** fix these, for two reasons that need your call:

1. Retargeting the tests to `hub_board_v10_lora1280_7of9.kicad_pcb` may make real
   assertions fail for real reasons — that is information, and it should be
   examined, not patched to green.
2. Deleting `ANT1..ANT4` expectations or the registry rows is a **documentation
   decision** under ADR-137; the registry is a pinmap authority and changing it
   must cite the ADR, not a test.

Recommended handling, in this order: retarget the five tests to the canonical
board on a dedicated branch and record what genuinely fails; then update
`v10_pinmap.reg` in a separate ADR-137-citing change.

## Reproduction

```sh
git checkout f675f2fb
PYTHONPATH=/usr/lib/python3/dist-packages python3 -m pytest \
  tests/test_v10_connectivity.py tests/test_v10_hole_clearance.py \
  tests/test_c_host.py -q -p no:cacheprovider
```
