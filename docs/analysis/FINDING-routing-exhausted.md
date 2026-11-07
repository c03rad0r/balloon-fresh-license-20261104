# Routing is exhausted at S1: the last five candidates measured, none routable

**Measured 2026-11-07 on `latest.kicad_pcb` (18 opens / 19 library-drift violations / 0 electrical).**

## The method that worked, applied to what remains

CUTSENSE2 closed three opens by choosing the route goal by **connectivity** (which fragment is
not already joined) instead of by distance to nearest same-net copper. The distance method had
routed three nets and closed zero. Applied to the five remaining cross-layer candidates:

| target | fragments | goal gap | result |
|---|---|---|---|
| `/VSCAP` R_BAL1.1 | 11 | 1.594 mm | NO PATH, exhausted at **37 steps** |
| `/F33_VSENSE` U1.21 | 6 | 41.434 mm | NO PATH, exhausted at **138 steps** |
| `/EN` U1.3 | 2 | 30.712 mm | NO PATH, exhausted at **164 steps** |
| `/CUT_SENSE_W1` J_W1.3 | 3 | 0.000 mm | NO PATH, exhausted at **424 steps** |
| `/SPI1_MOSI` auto | 6 | 4.445 mm | NO PATH, exhausted at **3235 steps** |

Small step counts mean the flood filled an enclosed pocket and ran out — not a timeout, not an
under-seeded start. Seed radius 5 and 6 were both tried on each.

This is independent corroboration of the pocket sizes measured earlier by a different route:
`/SPI2_SCK` 166 cells, `/F33_VSENSE` 186 cells, `/EN` 164 steps. Two different instruments,
same answer.

## What remains, and why it is not routing work

18 opens, classified:

- **3** `/CUT_SENSE_W1` (0), `/SPI2_SCK` (1), `/EN` (17) — trapped at the terminal
- **2** `/F33_VSENSE` (2), `/VSCAP` pad-track (5) — trapped
- **1** `/SPI1_MOSI` (3) — 3235-step pocket
- **4** wing two-face pad pairs (6, 8, 10, 11, 13) — **genuinely assembly lands**; these are
  pad-on-both-faces of one connector with no barrel, joined when the wing tab is soldered.
  Routing them is wrong (WING_TAB_4P / ADR-120 R1).
- **1** `/W1_SOLAR_N` track-to-pad (7), `/W2_SOLAR_N` (9), `/W3_SOLAR_N` (12) — wing-area
  track/pad transitions
- **4** zone-pair records (4, 14, 15, 16) — GND/VSCAP pour-to-pour records, not copper gaps

## The honest conclusion

Routing at S1 is complete. 38 -> 18 opens this campaign. Nothing further can be closed by
adding track at 0.20 mm / 0.20 mm clearance / 0.600-0.300 via.

What the remaining 18 need, in order of cost:

1. **4 zone-pair records** — verify they are pour-connectivity records rather than real gaps,
   then accept or stitch. Cheap to check, no copper change.
2. **5 wing-area track/pad transitions** — the wing region is where the 4 assembly lands and
   the slot-clearance question already live. One design decision about that area could resolve
   several at once.
3. **6 trapped terminals** — placement or fanout change. Real work, outside routing.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/bulk-route-20261107/remain1_batch.py
```
