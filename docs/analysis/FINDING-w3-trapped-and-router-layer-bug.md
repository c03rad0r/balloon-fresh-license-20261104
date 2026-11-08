# `/W3_SOLAR_N` is genuinely trapped on B.Cu — and my router had a real multi-layer bug

**2026-11-08, board `322ade1e`, 11 opens. Nothing in this document changed the board.**

Two separate findings, one of which corrects a claim I made repeatedly this campaign.

## Finding 1: the router's layer arithmetic was wrong for anything but two layers

`collide_router.py` line 255 was:

```python
other = LAYERS[1 - LAYERS.index(l)]
```

That is only correct for exactly two layers. With three `(F, B, In2)` it evaluates to `1 - 2 = -1`,
i.e. `LAYERS[-1]` = In2, so a via from In2 "switches" to In2 and the third layer is **never reachable**.

How it was caught: a probe ran the router twice — once with `LAYERS=(F,B)` and once with
`LAYERS=(F,B,In2)` — and both returned the **identical 472 steps**. A parameter that changes nothing is
inert; that signature has exposed three defects in this campaign already, so I checked the source
before believing the result.

Fixed to iterate every other layer:

```python
if via(i, j):
    for other in LAYERS:
        if other != l and ok(i, j, other):
            cand.append(((i, j, other), 4.0))
```

`test_collide_router.py`: **17/17 still pass** after the change.

## Finding 2: multi-via was never the limitation — I said it was, repeatedly

I told the user several times that "route_batch.py does ONE via and cannot plan across two layer
changes", and treated that as the reason `/EN`, `/SPI2_SCK`, `/F33_VSENSE`, `/VSCAP` and
`/W3_SOLAR_N` could not close.

**That was wrong.** Layer switching is an ordinary A\* neighbour, so the search chains as many vias as
it needs. The real restriction was the two-layer `LAYERS` tuple plus the arithmetic bug above — a
**layer count** limit, not a via count limit. The distinction matters because "needs two vias" sounds
like a bigger engineering problem than "one constant needs a third entry".

## Finding 3: `/W3_SOLAR_N` really is trapped, measured directly

With the fix in place and In2 available, a controlled BFS on the actual obstacle field:

```
bbox 161 x 96 cells; start (127,25), goal (30,15); both inside the bbox
reachable cells on B.Cu from the start: 516 of 15456
goal reached: False
closest flood cell to goal: (37.800,0.700), 8.896 mm away
first blockage walking that line: PAD GND J_W4.2
```

516 cells is a pocket, not a route. `J_W4.2` — the neighbouring wing pad of the same connector — seals
the mouth. So the "search exhausted 472 steps" verdicts from earlier in the campaign were **correct**,
even though the layer plumbing was broken.

This also explains the hand-placed B.Cu dogleg that shorted three nets: there is no free B.Cu corridor
from `J_W4.1` toward `D_BP4.1`. The dogleg was not unlucky, it was impossible.

## What this means for the remaining opens

Every remaining net now has a measured verdict, not an assumption:

| net | status | measurement |
|---|---|---|
| `/EN` U1.3 | enclosed at S1 | 166-cell pocket (raster) / 164 steps (A\*), 0/12 free rays |
| `/SPI2_SCK` U1.4 | enclosed at S1 | 112-cell pocket / 118 steps, 0/12 free rays |
| `/F33_VSENSE` U1.21 | enclosed at S1 | 138-cell pocket / 138 steps × 4 targets |
| `/VSCAP` R_BAL1.1 | enclosed at S1 | 38-cell pocket / 186 steps |
| `/W3_SOLAR_N` | enclosed on B.Cu | 516/15456 cells, blocked by `J_W4.2` |
| 3 GND records | pour records | In1 is one continuous 100% island |
| 3 two-face lands | assembly-joined | measured: 0 isolated faces |

The multi-layer router is now correct, and it does not change any of these verdicts — which is itself
the useful result: the walls are geometry, not tooling.

## Note on scope

`collide_router.py` lives in the analysis tree
(`~/reports/flight-readiness-20261102/rdiv2-local-clearance/`), not in the repo, so the fix is recorded
here rather than as a repo commit. Any future routing work must use the fixed copy.
