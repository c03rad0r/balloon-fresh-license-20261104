# The four trapped pads: both options costed — and my standing recommendation does not work

**2026-11-08, board `31efa2da`.** Measured with bisection on `SHAPE.Collide` (Distance is unreliable
on this board's pads).

## The budget I had been using was wrong

A 0.200 mm track threading between a pad and a neighbour needs **clearance + its own width**:

```
S1       0.200 clearance + 0.200 track = 0.400 mm corridor
0.150    0.150 clearance + 0.200 track = 0.350 mm corridor
fab min  0.090 clearance + 0.200 track = 0.290 mm corridor
```

Earlier in this campaign I made this exact error once (documented in
`CORRECTION-clearance-budget.md`) and then **made it again** in the script that produced the first
version of this table, by testing the gap against 0.200 instead of 0.400. Every verdict was
inflated by exactly 0.200 mm. Corrected below.

## Measured, per trap, against the nearest blocker

```
/EN  U1.3 (11.050, 36.430)
    0.350 to track /SPI2_MISO   S1 short 0.050 | 0.150 OK | fab OK
    0.370 to pad U1.2, U1.4     S1 short 0.030 | 0.150 OK | fab OK

/SPI2_SCK  U1.4 (11.050, 37.700)
    0.200 to track /SPI2_MOSI   S1 short 0.200 | 0.150 SHORT 0.150 | fab SHORT 0.090
    0.250 to track /SPI2_MOSI   S1 short 0.150 | 0.150 SHORT 0.100 | fab SHORT 0.040

/F33_VSENSE  U1.21 (20.435, 51.650)
    0.250 to track /U3_CS_N     S1 short 0.150 | 0.150 SHORT 0.100 | fab SHORT 0.040
    0.335 to track /SPI1_SCK    S1 short 0.065 | 0.150 SHORT 0.015 | fab OK
    0.370 to pad U1.20          S1 short 0.030 | 0.150 OK          | fab OK

/VSCAP  R_BAL1.1 (40.490, 43.500)
    0.282 to track /SCAP_MID    S1 short 0.118 | 0.150 SHORT 0.068 | fab SHORT 0.008
```

## Option A — a 0.150 mm rule scoped to those four pads

**It closes two of the four, not four.**

- `/EN` — works: its blockers are 0.350 and 0.370, both ≥ 0.350.
- `/F33_VSENSE` — works against the 0.370 pad, but its nearest blocker `/U3_CS_N` is 0.250, which
  is **short 0.100 at 0.150**. So `/F33_VSENSE` does **not** close on the 0.150 rule either.
- `/SPI2_SCK` — does **not** work: nearest blocker 0.200, short 0.150 at the 0.150 rule.
- `/VSCAP` — does **not** work: nearest blocker 0.282, short 0.068 at the 0.150 rule.

So the scoped 0.150 rule buys **at most one** of the four (`/EN`), against spending 25 % of the S1
safety margin board-wide on those pads. That is a materially worse trade than the campaign has been
assuming since `FINDING-jlcpcb-capability-vs-S1.md`, which said "three of four clear the process
minimum" — true of the *fab* minimum, but the track still has to physically fit, and it does not.

## Option B — move the enclosing copper

The targets are now named and measured:

| trap | target to move | how much | object |
|---|---|---|---|
| `/EN` U1.3 | nothing needed if A is used; else `/SPI2_MISO` track | ≥ 0.050 | F.Cu track |
| `/SPI2_SCK` U1.4 | `/SPI2_MOSI` track | ≥ 0.200 (S1) or ≥ 0.090 (fab) | F.Cu track |
| `/F33_VSENSE` U1.21 | `/U3_CS_N` track | ≥ 0.100 (at 0.150) or ≥ 0.040 (fab) | F.Cu track |
| `/VSCAP` R_BAL1.1 | `/SCAP_MID` track | ≥ 0.068 (at 0.150) or ≥ 0.008 (fab) | F.Cu track |

Every one is a **track**, not a pad, not a component. All four are on F.Cu. That is a much better
shape of problem than "move enclosing copper" implied: four track nudges of 0.008–0.200 mm, on one
layer, none requiring a component to move.

`/VSCAP` is striking: it needs **0.008 mm** against the fab minimum. That is 8 µm — inside the
track-width tolerance itself.

## What I would actually recommend, now that it is measured

Not the 0.150 rule. **Nudge four F.Cu tracks.** Specifically:

1. `/VSCAP` — move `/SCAP_MID` by 0.010 mm. 8 µm is not a design problem, it is a rounding artefact.
2. `/F33_VSENSE` — move `/U3_CS_N` by 0.040 mm.
3. `/SPI2_SCK` — move `/SPI2_MOSI` by 0.090 mm. This is the only one that is real work.
4. `/EN` — nothing, if any of the above is done; otherwise 0.050 mm on `/SPI2_MISO`.

That keeps S1 at 0.200 intact, closes up to four opens rather than one, and touches only tracks —
which is ordinary routing work, inside my standing authority, not a rule change.

**The catch, stated plainly:** moving `/SPI2_MOSI` 0.090 mm to free `/SPI2_SCK` may in turn pinch
something else, and `/SPI2_MOSI` is itself one of the nets being routed. Each nudge has to be
re-checked against its own neighbours, and the C10 freeze still applies to anything inside
x 8.00–11.20, y 41.00–44.20 — `/EN` and `/SPI2_SCK` at x ≈ 11.05 sit right at that boundary.

## Reproduce

    /usr/bin/python3 -B docs/analysis/trap_option_costs.py
