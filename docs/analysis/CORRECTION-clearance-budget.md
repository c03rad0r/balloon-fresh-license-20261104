# Correction: the "clear corridor" was my arithmetic error — the router was right

**2026-11-07, board `e00b98e7`. Retracts the claim that the U1 pads had an open escape.**

## What I claimed, and why it was wrong

I measured edge-to-edge gaps from each pad to nearby tracks, subtracted **0.200 mm clearance**, and
reported corridors as "clear by" whatever remained. On that basis I declared `/SPI2_SCK`'s `+x` side
open (`/SPI2_MISO` 0.350 mm, `/F33_CS_N` 1.050 mm) and wrote a router script to exploit it.

The router said **NO PATH, 118 steps, at seed radius 2, 4 and 6**. It was right.

**The error:** fitting a NEW 0.200 mm track between two existing coppers needs

```
0.200 mm clearance + 0.200 mm of the new track's own width = 0.400 mm
```

not 0.200 mm. I subtracted only the clearance and ignored the track's own width, which inflated every
corridor by exactly 0.200 mm. `/SPI2_MISO` at 0.350 mm is therefore **0.050 mm short**, not "clear by
0.150". The gap I called generous was the one I had mismeasured.

## Corrected measurement (0.400 mm required)

```
/EN  pad U1.3
    0.350 mm  /SPI2_MISO  RIGHT +x   BLOCKS, short by 0.050   <- the only near neighbour close enough
    0.562 mm  /SPI2_MOSI  LEFT  -x   clear by +0.162
    0.720 mm  +3V3        LEFT  -x   clear by +0.320
    1.050 mm  /F33_CS_N   RIGHT +x   clear by +0.650

/SPI2_SCK  pad U1.4
    0.200 mm  /SPI2_MOSI  LEFT  -x   BLOCKS, short by 0.200
    0.250 mm  /SPI2_MOSI  LEFT  -x   BLOCKS, short by 0.150
    0.300 mm  /SPI2_MOSI  LEFT  -x   BLOCKS, short by 0.100
    0.350 mm  /SPI2_MISO  RIGHT +x   BLOCKS, short by 0.050
    1.050 mm  /F33_CS_N   RIGHT +x   clear by +0.650
```

Every candidate is short. `/SPI2_MISO` blocks **both** pads by the same **0.050 mm**.

## The near-miss that matters

**0.050 mm.** That is not a design wall — it is 50 micrometres. It is the entire obstruction, and it
suggests that a small, deliberate nudge to `/SPI2_MISO` would free both pads at once. But a nudge is
still a copper move on a routed track, and the standing authority covers routing strategy; the
question is whether nudging an existing, DRC-clean track is the right call or whether accepting the
open is. I am recording it as the cheapest remaining option, measured, rather than acting on it
unilaterally in this same breath.

## Also corrected

The 12-ray escape probe reported `0 free directions` for these pads, and its blockers were
**centre-distance** based, so its "0.40–1.40 mm clear" numbers were also inflated by the pad's own
half-extent. The Collide-bisection measurement above is the trustworthy one.

## What is unchanged

The router's conclusions were right throughout: these pads are enclosed at S1. Its step counts
(118/138/164/186) and this measurement now agree. **My analysis was the unreliable instrument, three
times over on the same pads** — first a wrong metric, then a wrong Collide polarity, then a wrong
clearance budget.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/corridor_gap_collide.py
/usr/bin/python3 -B docs/analysis/spi2sck_retry.py     # NO PATH, 118 steps
```
