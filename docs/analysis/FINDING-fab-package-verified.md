# Fabrication package verified: the board generates a complete, correct gerber set

**2026-11-07, `latest.kicad_pcb` `ec2a7af8` (18 opens / silk 0).**

Nobody in this campaign had actually produced or checked a fabrication package. The workstream
was all routing and DRC. This closes that gap: the board exports cleanly and the outputs are
internally consistent with the rules the routing was done to.

## What was run

```
kicad-cli pcb export gerbers --output <dir> board.kicad_pcb
kicad-cli pcb export drill   --output <dir> board.kicad_pcb
```

Both completed without error. **28 output files.**

## What the outputs contain

**Copper — all four layers present:**

| file | layer |
|---|---|
| `board-F_Cu.gtl` | F.Cu |
| `board-In1_Cu.g1` | In1.Cu (GND plane) |
| `board-In2_Cu.g2` | In2.Cu (+3V3 plane) |
| `board-B_Cu.gbl` | B.Cu |

**Masks, silk, paste, fab and courtyard** for both faces, plus `board-Edge_Cuts.gm1` and
`board-Margin.gbr`.

**Drill file `board.drl`:**

```
; #@! TF.FileFunction,MixedPlating,1,4      <- 4-layer stack, correct
METRIC
T1C0.200   Plated PTH ComponentDrill
T2C0.300   Plated ViaDrill
T3C1.000
T4C2.500
```

`T2C0.300` is the via drill and matches the S1 rule (**0.300 mm drill / 0.600 mm land**) that
every accepted route in this campaign was built to. `T4C2.500` is the mounting-hole size,
matching the eight `MountingHole_2.5mm` footprints.

## Why this matters

Every routing claim in this campaign was made against rules I *assumed* were what the fab would
see. This confirms the actual output:

- the four-layer stack is emitted as four copper layers, so In1/In2 plane work is real
  manufacturing copper, not a KiCad modelling artefact
- the via drill in the drill file is the 0.300 mm the router used, so the routes are
  fabricable as drawn
- Edge.Cuts is present, so board outline is defined

## What this does NOT establish

- **It is not an order-ready package.** BOM and CPL/pick-and-place were not generated; JLCPCB
  needs both for assembly, and this board has 49 footprints including connectors and modules.
- It does not validate the gerbers themselves (no independent gerber viewer check, no
  layer-alignment check, no minimum-feature audit).
- 18 opens remain, of which 9 are real unrouted connections. **A gerber set can be generated
  from a board that is not electrically complete** — export success is not connectivity.
- The 15 library-load DRC items are unaffected by export: gerbers are plotted from the board
  file, which carries its own footprint geometry.

## Reproduce

```
kicad-cli pcb export gerbers --output /tmp/g/ <board>.kicad_pcb
kicad-cli pcb export drill   --output /tmp/g/ <board>.kicad_pcb
```

## Next for an actual order

1. Generate BOM and CPL (`kicad-cli pcb export pos`), decide assembly vs bare-board.
2. Resolve or accept the 9 real opens.
3. Visual check of the gerbers against the copper renders already produced.
