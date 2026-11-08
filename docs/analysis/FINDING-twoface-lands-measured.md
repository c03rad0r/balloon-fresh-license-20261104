# The 7 two-face wing lands: measured, all genuinely assembly-joined

**2026-11-07, board `a373c118`, 16 opens. Answers the question I had been putting to the operator.**

## The question

Are the two-face wing pads real missing connections, or do they conduct when the wing tab is
soldered? Every earlier answer in this campaign was inherited from `FINDING-18-reclassified.md`
reasoning about `/CUT_SENSE_W1` — it was never measured across all of them.

## What a two-face land actually is here

Not one pad carrying both layers. It is **two pad objects at the same XY**, one on F.Cu and one on
B.Cu, both undrilled. KiCad treats the faces as separate copper, so DRC reports the pair as
unconnected no matter how well either face is routed.

My first probe missed all 7 because it looked for a single pad with both layers. Fixed by grouping
by position.

## Measured result

| ref | pin | net | net reaches F.Cu | net reaches B.Cu | verdict |
|---|---|---|---|---|---|
| J_W1 | 1 | /W1_SOLAR_P | **yes** | – | assembly land |
| J_W1 | 3 | /CUT_SENSE_W1 | **yes** | – | assembly land |
| J_W1 | 4 | /W1_SOLAR_N | – | **yes** | assembly land |
| J_W2 | 1 | /W1_SOLAR_N | – | **yes** | assembly land |
| J_W4 | 1 | /W3_SOLAR_N | **yes** | – | assembly land |
| J_W3 | 4 | /W3_SOLAR_N | – | **yes** | assembly land |
| J_W3 | 1 | /W2_SOLAR_N | **yes** | **yes** | assembly land |

```
two-face pads in opens: 7
of those, REAL GAPS (isolated both faces): 0
```

**Every one has the net arriving on at least one face.** Not one is an isolated pad pretending to
be an assembly land. `J_W3.1` even has copper on both faces.

This is the measurement that the ADR-120 R1 / WING_TAB_4P classification always needed and never
had: the pads are not merely *described* as assembly-joined, they are **routed to on one face with
only the face-to-face link left**, which is exactly the construction the tab closes.

## Consequence for the open count

Of the 16 remaining DRC records:

- **7** are these assembly lands — not missing connections
- **3** are GND zone records against the In1 plane — pour artefacts
- **6** are real copper gaps

So the DRC count of 16 overstates the electrical work by more than 2x. The honest figure for
"connections still to make on copper" is **6**, and those are the ones worth attempting.

## What this does NOT mean

It does not mean the board is finished. It means the 7 wing records should be reported as
assembly-joined rather than as routing failures, and that an order decision should weigh 6 real
connections, not 16 records. Nothing here changes what DRC says.

## Reproduce

```
kicad-cli pcb drc --format json --severity-all --units mm --output /tmp/drc17.json <board>
/usr/bin/python3 -B docs/analysis/twoface_truth.py
```
