# J_W2 "edge clearance" is a pad-to-SLOT clearance, not a board-edge problem

**Measured 2026-11-07 on `latest.kicad_pcb` (22 opens / 24 warnings).**

## What DRC actually reports

16 `copper_edge_clearance` errors, all of the form:

```
Segment of J_W2 on Edge.Cuts  ||  Pad 2 [GND] of J_W2 on F.Cu   (and B.Cu)
Segment of J_W2 on Edge.Cuts  ||  Pad 3 [/CUT_SENSE_W2] of J_W2 on F.Cu (and B.Cu)
actual 0.0500 mm, board setup constraint 0.5000 mm
```

My first reading was "connector too close to the board edge — move it inboard". **That was
wrong**, and the measurement says so three ways.

## What is physically there

J_W2 is `Wing_Tab_4P`, rotation 90°, at y=77.0. All four pads are **1.0000 mm** from the
y=80.000 mm board outline. No pad is near the board edge.

Inside the footprint there is a **rectangle on Edge.Cuts**:

```
PCB_SHAPE (35.750, 74.000) -> (36.250, 74.000)   width 0.050
PCB_SHAPE (35.750, 80.000) -> (35.750, 74.000)   width 0.050
PCB_SHAPE (36.250, 74.000) -> (36.250, 80.000)   width 0.050
PCB_SHAPE (36.250, 80.000) -> (35.750, 80.000)   width 0.050
```

A **0.50 x 6.00 mm routed slot cut through the board edge**, i.e. a wing-tab insertion slot.
Pads 2 (GND, x=35.100) and 3 (/CUT_SENSE_W2, x=36.900) flank that slot. Each pad's inner
edge sits **0.0502 mm** from a slot wall; pads 1 and 4 are 1.0001 mm clear.

Four of the 49 footprints carry Edge.Cuts graphics; the four `Wing_Tab_4P` connectors do.
So this is a deliberate, repeated design feature, not one stray line.

## Why this matters for the order — the honest position

`copper_edge_clearance` in KiCad applies to copper near **any** Edge.Cuts geometry, including
internal cut-outs. A 0.5 mm slot with copper 0.05 mm from its wall is a genuine
manufacturing consideration: the router bit needs clearance, and 0.05 mm is far inside a
0.5 mm rule.

But it is **not** the "move the connector" problem I described earlier, and it is **not**
caused by any routing. It is a property of the Wing_Tab_4P footprint as placed, on all four
wing connectors.

Three real options, and none of them is mine to choose:

1. **Ask JLCPCB whether they accept 0.05 mm copper-to-slot on a 0.5 mm slot** — they may,
   or they may charge for it, or refuse. This is a fab capability question, not a CAD one.
2. **Narrow the slot or shift the pads** in the footprint — a real design change touching
   all four wing connectors, and it interacts with the assembly-join intent.
3. **Widen the slot clearance in the board's edge rule** if 0.5 mm is stricter than this
   design needs internally — but that weakens a rule to hide a real gap, which I would not
   do without an explicit decision.

## Correction to what I said earlier

I told you J_W2's pads were "0.05 mm from the board edge — ten times inside the rule" and
that the board could not be ordered until the connector moved. **The distance to the board
edge is 1.0000 mm and is fine.** The 0.05 mm is to an internal slot wall. The ordering
consequence may still be real, but the diagnosis and the fix I implied were both wrong.

## Reproduction

```
/usr/bin/python3 -B docs/analysis/jw2_edge_measure.py
```

Note on method: the first version of that script reported 0.0003 mm for every pad because it
bisected with `SHAPE_POLY_SET.Collide`, which has containment semantics and is true anywhere
inside the board. It now walks each pad's perimeter and uses `CollideEdge` (point-to-edge),
resolving to 0.5 um.
