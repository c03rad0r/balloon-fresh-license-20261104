# Bare-board fab package regenerated for the 11-open board (`322ade1e`)

**2026-11-08.** Supersedes `FINDING-bare-board-package-verified.md`, which described the 15-open board
`e00b98e7`. That package is now stale — the adopted FR3NETS batch closed four opens since.

## Generated

`kicad-cli pcb export gerbers` + `pcb export drill` against a copy of the tracked board with
`.kicad_dru`, `.kicad_pro` and `fp-lib-table` staged beside it.

```
23 files in the job manifest, all required functions present:
  Copper,L1,Top        board-F_Cu.gtl
  Copper,L2,Inr        board-In1_Cu.g1
  Copper,L3,Inr        board-In2_Cu.g2
  Copper,L4,Bot        board-B_Cu.gbl
  Profile              board-Edge_Cuts.gm1
  SolderMask,Top/Bot   board-F_Mask.gts / board-B_Mask.gbs
  Legend,Top           board-F_Silkscreen.gto
  SolderPaste,Top/Bot, AssemblyDrawing, Glue, Other,User ...
drill: Excellon, METRIC, decimal zeros, absolute origin
```

## Drill verification, per tool

```
0.200 mm : file  12   board  12   OK
0.300 mm : file 158   board 158   OK     <- all vias, S1's 0.600/0.300
0.360 mm : file   3   board   3   OK     <- 3 new vias from FR3NETS
1.000 mm : file  15   board  15   OK
2.500 mm : file   8   board   8   OK
total    : file 196   board 196   OK
```

The 0.360 mm entry is new relative to the 15-open package (193 holes then, 196 now) and is expected: it
is the drill for the three vias FR3NETS added. Every tool count matches the board exactly, and no board
drill size is missing from the file.

## What this package is and is not

**Is:** a complete, internally consistent bare-board order set for board `322ade1e`, 11 opens, silk 0,
zero electrical errors.

**Is not:**
- a BOM or CPL — assembly remains blocked by 5 undecided parts, including all four pyro cut drivers
- a fresh independent gerbv render of this export (the earlier independent render was a different
  export and a different board)
- a finished board: 11 opens remain

DRC on this board is 16 violations, all of them either a KiCad footprint-file version artefact
(11 `lib_footprint_mismatch` + 4 `lib_footprint_issues`) or a single cosmetic 0.1414 mm
`track_dangling` stub on `/W2_SOLAR_N`. Zero clearance, short, thermal, crossing or isolated-copper
items.

## Ordering caveat

AGENTS.md reserves placing a purchase order to the operator. This package is ready to upload; ordering
it is the user's decision, not the assistant's.
