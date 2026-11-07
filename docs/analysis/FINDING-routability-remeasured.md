# Re-measured routability on the CURRENT board — one net previously written off is a candidate

**2026-11-07, `latest.kicad_pcb` `ec2a7af8`, 18 opens, S1 rules (0.200/0.200, guard band).**

## Why this was re-run

"Routing is exhausted at S1" was concluded on a **25-open** board. Since then BRIDGE3 added a
42.61 mm cross-layer bridge, DEADVIA removed two vias, and SILKTEXT moved silk to F.Fab. Copper
topology changed, so a corridor that was blocked at 25 opens deserves re-asking.

## Method

Read-only. For each current open: classify by the item kinds DRC reports, then run a Collide-only
A* on F.Cu/B.Cu at frozen S1 rules with the `CLEAR + 70711 nm` guard band, 0.250 mm grid, 2 mm
spatial-hash buckets, 400k step cap.

**Three tool bugs were found and fixed while getting this to produce sane output. All three
produced confident, wrong answers first:**

1. **Units.** DRC JSON is `--units mm`; positions were treated as nm. Bounding boxes became
   ±8,000,000 nm and every result read `ROUTABLE_NOW` in 1 step.
2. **Wrong nesting level.** The net name lives in the **item** description
   (`Pad 4 [/SPI2_SCK] of U1 on F.Cu`), not the violation's (`Missing connection between
   items`). Reading the violation left `net=''`, so every pad counted as its own blocker and
   the router walled itself in.
3. **Silent nonsense.** Neither bug raised an error; both produced plausible-looking verdicts.
   Added a hard contract: if the two endpoints land in the same grid cell the result is
   reported as `ENDPOINTS_IN_SAME_CELL_BUG`, never as a routing verdict.

## Results

| open | net | distance | verdict | steps |
|---|---|---|---|---|
| 1 | /SPI2_SCK | 23.76 mm | NO_PATH | 59 |
| 2 | /F33_VSENSE | 41.43 mm | NO_PATH | 6 |
| 3 | /SPI1_MOSI | 26.85 mm | NO_PATH | 1075 |
| 4 | /VSCAP | 51.35 mm | NO_PATH | 166,463 |
| 5 | /VSCAP | 1.59 mm | NO_PATH | 25,713 |
| 9 | /W2_SOLAR_N | 42.64 mm | NO_PATH | 1,983 |
| **12** | **/W3_SOLAR_N** | **46.04 mm** | **ROUTABLE_NOW** | **4,907** |
| 17 | /EN | 30.71 mm | NO_PATH | 119 |
| 14,15,16 | — | 0.283 mm | sub-cell, needs finer grid | — |
| 7 others | — | 0.000 mm | SAME_XY_ASSEMBLY_LAND | — |

```
SUMMARY: {'SAME_XY_ASSEMBLY_LAND': 7, 'NO_PATH': 7,
          'ROUTABLE_NOW': 1, 'ENDPOINTS_IN_SAME_CELL_BUG': 3}
```

## The finding that matters

**`/W3_SOLAR_N` was on my earlier list as "needs drill-in-pad" and unroutable. A 46.04 mm
single-layer path now exists at S1 rules.** That earlier verdict is wrong for this board state.

This is a **candidate, not a route.** The probe is coarse (0.250 mm grid), has **no via
transitions at all**, does not validate that the path actually lands on the target pad, and has
not been through `route_batch.py` or any DRC. Treat it as "worth one real attempt", which is
exactly what the earlier dismissal denied it.

## Where my earlier accounting was wrong

I had been quoting **9 real / 5 assembly lands / 4 pour artefacts**. This measurement says:

- **7** same-XY assembly lands (not 5)
- **3** sub-0.283 mm pad-to-track gaps that need a finer grid, not a routing decision
- **7** NO_PATH at this grid resolution
- **1** router candidate

The 9/5/4 split was inherited from the 25-open classification and never re-derived after three
copper-changing batches. Do not rely on it.

## Honest limits

- no via transitions: a path needing a layer change is invisible to this probe
- 0.250 mm grid: anything narrower than ~0.45 mm of free channel can be missed
- NO_PATH here means "no path found by this probe", not "no path exists" — open 4 explored
  166,463 cells, opens 1 and 17 explored 59 and 119, which is suspiciously shallow and suggests
  the grid is coarse relative to the pinch rather than that the region is large
- no DRC was run on anything

## What the /W3_SOLAR_N candidate actually is

`batch.sh` refused with `no pad J_W3.3 on net /W3_SOLAR_N` — my pad guess was wrong, and the
refusal was correct. Reading the real DRC records, `/W3_SOLAR_N` produces **three** records:

```
Pad 1 [/W3_SOLAR_N] of J_W4 on F.Cu   (38.7, 3.0)     <- same XY, two-face pad
Pad 1 [/W3_SOLAR_N] of J_W4 on B.Cu   (38.7, 3.0)
Track [/W3_SOLAR_N] on B.Cu len 3.3004  (69.0, 37.3)  <- REAL GAP, 46.04 mm
Track [/W3_SOLAR_N] on F.Cu  len 3.8000  (38.35, 2.95)
Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu   (69.0, 37.3)    <- same XY, two-face pad
Pad 4 [/W3_SOLAR_N] of J_W3 on B.Cu   (69.0, 37.3)
```

So the closable connection is **track-to-track**, not pad-to-pad. That is why the pad-based
`batch.sh` cannot address it: it resolves endpoints by `REF.PIN`, and this open has track
endpoints. The right tool is the fragment-bridge path (`bridge_halves.py`, the same one that
closed BRIDGE3).

**Unresolved and important:** both J_W4 pad 1 and J_W3 pad 4 are two-face pads at identical XY
with no drill — the same construction that this campaign already classified as an assembly land
joined when the wing tab is soldered. If those pads only connect in assembly, then a 46 mm track
across the board may be the wrong repair entirely, and the real question is a placement/assembly
one. I am not routing it until that is settled.

## Next

Either bridge the two track fragments with `bridge_halves.py` and gate on opens, or first settle
whether the two-face wing pads are meant to conduct in assembly. Those are different repairs.

## Reproduce

```
kicad-cli pcb drc --format json --severity-all --units mm --output /tmp/drc18.json <board>
/usr/bin/python3 -B docs/analysis/current_routability.py
```
