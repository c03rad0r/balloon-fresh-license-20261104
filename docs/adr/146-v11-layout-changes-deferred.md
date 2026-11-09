# ADR-146 — v11 layout changes deferred from the v10 order

- **Status:** **Proposed for v11** — recorded so the measurements are not re-derived.
- **Date:** 2026-11-09
- **Decision owner:** Felix (operator)
- **Related:** ADR-120 R3 (placement gate), ADR-139 (2G4 site part), ADR-143 (lane discipline),
  ADR-145 (v11 GPIO economy).

## Context

The v10 hub is being ordered from JLCPCB as an **assembled board** (Standard PCBA, because
`U1` `C298200`-class ESP32-S3-WROOM-1U is restricted to Standard). Three layout changes were
considered during the order and **deliberately deferred to v11** rather than applied to a board
that was already order-ready. This ADR records them with the measurements that justified the
deferral, so v11 starts from evidence instead of repeating the analysis.

### What v10 ships as (the decision this defers from)

- **Top-side-only assembly**, 19 placements, Economic-class part set on a Standard tier (Standard
  is required for `U1`; assembly side is Top only, so the second-side $25 setup is not paid).
- **`D_BP1..D_BP4` hand-soldered** on the bottom by the operator: SS24 in SMA, 2 pads each.
- Remaining hand-fit: `J_W1..J_W4`, `U3`, `U_LORA1280`, plus the four `D_BP`.

## Item 1 — move `D_BP1..D_BP4` to the TOP side (v11)

**Why:** on v10 they are the only bottom-side parts JLC places, and a second assembled side costs
$50 of setup (2 x $25) instead of $25. Hand-soldering four SMA diodes is cheap on the bench but it
is also the *only* reason the bottom face is touched at all during assembly.

**Measured on `work.kicad_pcb` (2026-11-09)** — free F.Cu area scanned on a 0.5 mm grid within 7 mm
of each diode, needing 2.2 mm clear for an SMA body:

| diode | present position (B.Cu) | free F.Cu spot | clearance |
|---|---|---|---|
| `D_BP1` | (4.00, 33.00) | (2.00, 29.50) | 5.13 mm |
| `D_BP2` | (29.00, 76.00) | **none within 7 mm** | — |
| `D_BP3` | (68.00, 33.00) | (70.00, 26.00) | 6.29 mm |
| `D_BP4` | (29.00, 4.00) | (22.50, 2.00) | 3.89 mm |

F.Cu copper for both nets of every diode exists within **1.2–7.8 mm** of its present position
(`/W1_SOLAR_N`, `/W1_SOLAR_P`, `/W2_SOLAR_N`, `/W3_SOLAR_N`, `GND`), so the move is electrically
tractable for three of the four.

**`D_BP2` is the blocker.** It sits at the `J_W2` wing socket with the solar chain packed around it;
no SMA-sized free top spot exists within 7 mm. Moving it is a **reroute**, not a nudge — and on a
two-signal-layer board with both layers poured, that is the same class of problem as `/EN`
(30.71 mm, sealed) and `/IO0` (shorts to `/USB_DN` on every attempt), neither of which closed in
five router attempts.

**v11 requirement:** place the four bypass diodes on **F.Cu at the four wing entry points by
schematic/placement time**, not by retrofit. `D_BP2`'s constraint is a *placement* constraint, so it
must be solved while the wing socket geometry is being laid out, not after routing.

**Caveat on the measurement above:** the free-spot search is a genuine geometric scan. The
per-net "distance to F.Cu copper" figures are measured from each diode's **current** position, not
from a candidate new position, so they show that the nets are nearby on F.Cu — not that any
specific spot is clear. Re-run against a real candidate placement before committing v11.

## Item 2 — wire `/SCAP_ADC` to an MCU ADC pin (v11)

`R_DIV1`/`R_DIV2` (1 M + 1 M) form a 2:1 divider from `/VSCAP` to `GND`, but their midpoint net
`/SCAP_ADC` has **exactly two pads and no MCU pin**:

```
/SCAP_ADC  ->  R_DIV1.2, R_DIV2.1     ...and nothing else
```

**Consequence: firmware cannot read the storage-rail voltage.** The divider was drawn; the wire to
the processor was never made. Same shape as the `/IO0` single-pad net (ADR-128) and the `U_CUT`
placeholder channels.

This matters because ADR-006 §*Spannungsueberwachung* and ADR-036 both assume firmware can measure
the rail — ADR-006 specifies *"ADC an GPIO0 misst Supercap-Spannung ueber Spannungsteiler"* and
*"Firmware bricht TX ab wenn Spannung unter 3.0 V faellt"*. **That abort path does not exist on v10.**

**v11 requirement:** route `/SCAP_ADC` to an ADC-capable pin **at layout time**.

## Item 3 — add dividers on the solar inputs (v11)

No solar input has a divider. `/W1_SOLAR_P` touches only `D1`, `D_BP1` and `J_W1` — there is nothing
to measure the array with. `/W2_SOLAR_P`, `/W3_SOLAR_P`, `/W4_SOLAR_P` do not exist as nets at all
(the array is one series string, so only `W1_SOLAR_P` and the `*_SOLAR_N` inter-wing nodes are real).

**v11 requirement:** if per-wing illumination telemetry is wanted, it needs both dividers **and** a
mux or an ADC with enough channels — decide which at schematic time, not after routing.

## Why these are v11 and not v10

Each one is a **placement or netlist change**, and the v10 board is otherwise order-ready:

- copper is routed on every flight part (`U1`, `U3`, `U_LORA1280`, `U7` all have **zero** single-pad
  nets — see `docs/analysis/FINDING-flight-readiness-audit.md`)
- BOM / CPL are derived from board attributes and verified to **0.0000 mm**
- all 11 gerber layers are geometrically identical to the board of record

A placement change on this board requires a fresh **ADR-120 R3 human placement gate**, and each of
the three items above lands in the congested region (wing corners, `U1` pin field, array feed). The
expected cost of doing them now is a reroute that may not close, on the critical path to an order
that is otherwise ready.

**None of the three stops the board flying.** They cost capability and telemetry, not function.

## What v11 must do differently

1. Place `D_BP1..D_BP4` on F.Cu at the wing entry points **as part of the wing-socket layout step**.
2. Wire `/SCAP_ADC` to an ADC pin in the **schematic**, so it cannot be a dangling net.
3. Decide solar telemetry (per-wing vs string) **before** placing dividers.
4. Keep the ADR-145 pin-economy measures in the same pass — the ADC pin for item 2 and the GPIOs
   for item 3 come out of the same budget.

## Reproduce

```
/usr/bin/python3 tracker/hardware/tmp_probes/dbp_move_feasibility.py
/usr/bin/python3 tracker/hardware/tmp_probes/railcaps.py
```

Both read `docs/analysis/bulk-route-20261107/work.kicad_pcb`. `pcbnew` lives in the **distro**
python, not the project venv.

## What would change this decision

If a v11 placement puts `D_BP2` clear of the `J_W2` socket fan-out (for example by moving the wing
socket or shrinking the solar-chain landing), item 1 becomes a trivial move and can be done as a
single-commit tweak rather than a layout step.
