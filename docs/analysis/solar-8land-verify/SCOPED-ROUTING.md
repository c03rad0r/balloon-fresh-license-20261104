# Scoped routing: what the opens actually are, and four search bugs

**Additive router for the remaining opens. Nothing ripped up.** Verified so far: **44 → 43** with one
pair routed and no new violation classes (`v11`). The 8-way + edge-check version is still being
validated; this file records the diagnosis and every bug found, including those not yet resolved.

## Why not the existing router

`tracker/hardware/auto_route_v1.py` deletes every track, via and zone and re-routes from scratch.
On this candidate that would discard verified work: 6 solar routes proven pair-by-pair, 37 GND
stitching vias, 12 +3V3 taps, the In2 3V3 plane, the /VSCAP pour taps, the thermal fix, the via
upsizing. Closing ~30 opens is not worth re-opening 80 closed ones, and ADR-140 requires a route
trial before placement sign-off anyway.

`route_scoped.py` touches only the pads DRC names, and refuses to run its own result if a
short/clearance class appears.

## What the 44 actually are — three different things

| kind | count | verdict |
|---|---|---|
| same pad number on F.Cu **and** B.Cu of one footprint | **7** | **Not a defect.** Each `J_W` tab is soldered on both faces — ADR-046 line 280: the tab "inserts 6 mm into the slot and is **soldered on both faces**"; ADR-120 R1 two-sided lands; ADR-142 §"Consequences". Assembly joins them. No via needed. |
| zone-to-zone | 5 | A pour problem, not a missing track. Handled by island bridging (#449). |
| genuine pad-pair | 14 | Routable, or blocked by geometry. |

So the honest "open copper" count is lower than the DRC headline.

## "No path" is a corridor report, not a wall

First run used a fixed 14 mm corridor and reported 4 failures. `why_no_path.py` probed each pad at
0.40 mm and `pad_escape_map.py` swept radii 0.30–3.00 mm in 16 directions:

```
C10.1   net=+3V3  at (9.50,42.98)
  r=0.30  5/16 free      r=1.00  0/16 ALL BLOCKED      r=3.00  6/16 free
  blocking at r=0.40: F.Cu /SPI1_MISO, B.Cu /SPI1_MOSI

U1.21   net=/F33_VSENSE  at (20.43,51.65)
  r=0.30  1/16 free      r=1.00  0/16 ALL BLOCKED      r=3.00  8/16 free
  blocking at r=0.40: In2.Cu /GNSS_PPS, B.Cu /SPI1_SCK
```

Both have free directions; the escape is **narrow and non-monotonic** — free at 0.40 mm, sealed at
1.00 mm, open again at 2.00 mm. So "no path" was wrong about the board three times over.

### The four search bugs, all mine

**1. 4-way Manhattan cannot follow an off-axis escape.** Identified by Kimi K3.1 Pro's method review
(`kimi-k3`, served id recorded in `review/lanes/kimi-routing-review.txt`). Escapes here are as narrow
as 1/16 of the circle and can sit at any angle; a 4-way grid can only leave a pad along ±x/±y, so an
off-axis free wedge is unreachable and the search reports a wall that is not there. Fixed with 8-way
moves at √2 cost. Kimi also flagged that this write-up described a "fixed 14 mm corridor" while the
code had already moved to a span-derived margin — stale documentation — and it declined to accept
the claim rather than paper over it. Correct call, and the reason the file was rewritten.

**2. Corridor width was fixed.** Now derived from the pair's span, `min(18, max(6, span*0.25))`. A
42 mm pair was being told "no path" by a corridor that could never contain it.

**3. Track moves never checked Edge.Cuts.** Only via placement did. The first 8-way run routed
`D_BP2.2 → J_W2.4` straight across J_W4's cavity slot and produced **6 `copper_edge_clearance`
errors**; the run's own gate refused the result (`rc=3`). ADR-142 keeps the edge exemption pad-only,
so a track must never cross a socket cavity.

**4. Edge testing per A* cell was far too slow.** 17 edge polygons (board outline + 16 J_W cavity
slots) with a `Distance()` call each, for every candidate cell: one pair ran past 500 s. The geometry
is static, so it is now rasterised **once** into a 0.25 mm mask, built per-shape from each polygon's
own bounding box rather than sweeping the whole board. Measured: mask build **0.3 s**, 10,000
lookups **0.01 s**. The mask is dilated by one cell, so it over-reports — which only refuses sites,
never permits an illegal one.

**5. The outer budget was checked only between pairs.** One hard pair consumed the whole run and 10
pairs were reported "budget exhausted (not attempted)". There is now a deadline *inside* the A*
loop, so a hard pair returns `None` and the remaining pairs still get their turn.

None of these is a board property. Recording them because the same mistake — a search limit reported
as a physical wall — is what produced the wrong "3 geometrically blocked" claim corrected in ADR-142.

## Rule that follows

**A router's "no path" is a claim about the search, not about the board.** Before any pair is
reported blocked, sweep radii and check whether the pad has a legal escape at *some* radius. If it
does, the search is wrong, not the geometry.

## Reproduce

```
python3 docs/analysis/solar-8land-verify/why_no_path.py <board> C10.1:U1.2 U1.21:R_MON2.1
python3 docs/analysis/solar-8land-verify/pad_escape_map.py <board> C10.1 U1.21
python3 docs/analysis/solar-8land-verify/route_scoped.py <src> <out> \
    --dru tracker/hardware/jlcpcb-s1-frozen.kicad_dru --report <dir>
```
