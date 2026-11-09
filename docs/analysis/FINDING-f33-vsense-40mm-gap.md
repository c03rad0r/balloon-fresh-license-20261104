# `/F33_VSENSE` is not a small break — it is a 40.9 mm missing trunk

**2026-11-09.** Corrects a claim I made twice earlier ("the divider is complete and correct…
46 segments already exist, so it's a local join"). That was wrong. The 46 segments exist, and they
are all in the wrong place.

## Measured

`/F33_VSENSE` has **4 pads, 46 tracks, 2 vias, 0 zones**:

| pad | position | size |
|---|---|---|
| `R_MON2.1` | (22.000, **8.010**) | 0.54 × 0.64 |
| `R_MON1.2` | (15.000, **6.990**) | 0.54 × 0.64 |
| `C_MON.1` | (14.000, **7.980**) | 0.56 × 0.62 |
| `U1.21` | (20.435, **51.650**) | 1.50 × 0.90 |

**Track extent: x 12.50…21.95, y 6.40…10.25.** Layers: F.Cu and B.Cu.

The divider lives at **y ≈ 7–10**. The ESP32 ADC pin is at **y = 51.65**. The copper spans y ≤ 10.25.

**Nearest same-net track to `U1.21`: 41.434 mm** centre-to-centre, i.e. a **40.9 mm** edge-to-edge
gap. There is no `/F33_VSENSE` copper anywhere in the top 80 % of the board.

## Why this matters more than the count suggests

The DRC record reads like one small unfinished net. It is not. **Three of four pads are tied
together at the divider; the fourth is 41 mm away with nothing running to it.** The net has a
complete local island and a completely isolated pin.

Practical consequence: **`F33_VSENSE` cannot measure anything.** The F33 PA rail divider is wired,
the ADC pin is not, so the firmware would read a floating input. On a board where the F33 PA is
DNP that is harmless *today* — but it means "the divider is complete" was never true, and any
future plan that assumes the sense path works is built on a false premise.

## What this changes about the routing effort

`/EN` and `/IO0` were attempted five times by the router and rejected. `/F33_VSENSE` was **never
attempted**, because I had recorded it as "a local join". It is a **41 mm run across a dense board**
— comparable to `/EN`'s 30.71 mm, which the router cannot solve either.

So the honest position on all three remaining routable nets:

| net | state | measured obstacle |
|---|---|---|
| `/EN` | 0 tracks | 30.71 mm, no path found |
| `/IO0` | 0 tracks | must cross `USB_DN`/`USB_DP`, router shorts to them |
| `/F33_VSENSE` | 46 tracks, **wrong region** | **40.9 mm gap** between divider and pin |

## What this does NOT change

`/F33_VSENSE` is **not a flight blocker**: its only load is `U2` (the F33 PA), which is DNP for
2 W / +33 dBm being outside licence-free limits in Germany. With `U2` unpopulated the divider
measures nothing and nothing depends on it.

## Correction record

Claims this supersedes, both mine:

1. *"`/F33_VSENSE` — the divider is complete and correct … 46 segments already exist, so it's a
   local join"* — **wrong**. Complete locally, absent globally.
2. Any framing of the `/F33_VSENSE` DRC record as "a small open" — **wrong**. It is 40.9 mm.

Method and reproduce command are in `tracker/hardware/tmp_probes/f33vsense_where.py`. Run it with
`/usr/bin/python3` (the distro python has `pcbnew`; the project venv does not).
