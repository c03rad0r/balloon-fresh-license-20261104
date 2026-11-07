# The three floating GND islands cannot be stitched at S1 rules

**Measured 2026-11-07, `latest.kicad_pcb` (22 opens / 24 warnings / 0 errors).**

## Result

Per island, candidate points whose via land overlaps the island copper, and how many of
those are legal at S1 (0.600 land / 0.300 drill / 0.200 clearance / 0.250 hole-to-hole):

| island | layer | area | bbox | overlapping points | legal |
|---|---|---|---|---|---|
| 0 | F.Cu | 0.844 mm² | 1.13 × 1.11 mm | 466 | **0** |
| 11 | F.Cu | 2.249 mm² | 1.80 × 1.26 mm | 468 | **0** |
| 3 | B.Cu | 0.925 mm² | 1.31 × 0.74 mm | 468 | **0** |

**Zero legal stitching sites on all three.** They float because there is nowhere legal to
stitch them, not because nobody tried.

## Why, and how I know the test is sound

A null result is only worth reporting if the primitive can return yes. Controls:

- `isl.Collide(land, 0)` at each island's own centre returns **True** — the overlap test
  works, so the 466–468 overlapping points are real overlaps, not a broken predicate.
- The rejections are dominated by foreign copper named explicitly: `PAD R_BAL1.2`,
  `PAD U1.39`, and individual track GUIDs crowding the island perimeter. For island 11,
  581 of 626 coarse-grid points failed an over-strict containment gate first, then 210
  failed `via_ok` outright, then named pads/tracks took the rest.
- An earlier version of this analysis wrongly required the via land to lie *entirely inside*
  the island polygon. That was my invention, not the physics — a stitching via only has to
  overlap the copper. Even with that corrected to overlap, the legal count stays 0.

## What this means

These islands are an artefact of routing around dense pads, and they cannot be fixed by
adding a via. The options are:

1. **Remove the island copper** — KiCad zone setting or a small keepout. Removes floating
   copper entirely, no clearance risk, no effect on any net (it is not connected to
   anything by definition).
2. **Leave them.** gpt-6-astra on this board: *"I would not hold an otherwise-verified board
   solely for these 4 mm² of floating copper."* 4.018 mm² against a 5478 mm² solid In1 GND
   plane is not a return-path problem.
3. **Move parts** to open a stitching site — disproportionate for 4 mm².

Recommendation: **option 2 (leave), with option 1 available** if a JLCPCB or assembly house
flags floating copper. Island 0 is inside the C10 frozen region and must not be touched
regardless.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/stitch_primitive_check.py
```
