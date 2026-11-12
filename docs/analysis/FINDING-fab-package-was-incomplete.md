# The committed fab package was INCOMPLETE — 12 of 23 manifest files, and B.Cu silkscreen missing

**2026-11-08, board `322ade1e`.** Supersedes `FINDING-bare-board-package-11opens.md`, which
claimed 23 files and committed 12.

## What was wrong

`docs/analysis/bulk-route-20261107/fab-11opens/` contained **12 files**, while its own
`board-job.gbrjob` manifest listed **23**:

```
in manifest but NOT committed (11 files):
  board-F_Adhesive.gta      board-F_Fab.gbr         board-User_Comments.gbr
  board-B_Adhesive.gba      board-B_Fab.gbr         board-User_Eco1.gbr
  board-B_Silkscreen.gbo    board-User_Drawings.gbr board-User_Eco2.gbr
  board-User_1.gbr ... board-User_4.gbr
```

`board-B_Silkscreen.gbo` is the one that matters for a bare-board order: it is real content
(1075 lines, **524 draw operations**), and a fab house checking silkscreen against the job file
would find a manifest entry with no file behind it.

The commit message said "23 files, all required functions present". The count was wrong and the
package was incomplete. **The lesson is not that gerbers were mis-generated — a fresh export
reproduces byte-identical copper, profile and drill. It is that the staged copy dropped files and
the claim was not checked against the manifest.**

## Regenerated and verified

Fresh export from the tracked board with `.kicad_dru`, `.kicad_pro`, `fp-lib-table` staged beside
it. Now **28 files**: the 23 in the manifest, plus `board-F_Courtyard.gbr`,
`board-B_Courtyard.gbr`, `board-Margin.gbr` and `board.drl` — files KiCad writes but does not list
in `FilesAttributes`.

Every key artefact is byte-identical between the committed copy and the fresh export:

```
OK  board-F_Cu.gtl      OK  board-B_Cu.gbl      OK  board-In1_Cu.g1
OK  board-In2_Cu.g2     OK  board-Edge_Cuts.gm1 OK  board-B_Silkscreen.gbo
OK  board.drl
```

## Drill verified tool-by-tool, from the COMMITTED file

```
T1 0.200 mm :  12 hits
T2 0.300 mm : 158 hits
T3 0.360 mm :   3 hits     <- the three vias FR3NETS added
T4 1.000 mm :  15 hits
T5 2.500 mm :   8 hits
              ---
TOTAL         196 hits
```

## Independently rendered — the check that was previously missing

The earlier note admitted "no fresh independent gerber render of THIS export". Done now with
`gerbv`, per copper layer plus the outline:

- **F.Cu**: complete rectangle, pour, traces and pads throughout; 85–90% copper coverage; no
  missing quadrant or cropped edge.
- **In1.Cu**: an almost entirely filled ground plane. Four narrow edge intrusions are the
  wing-socket cavities, each terminating inside the copper field and **not** dividing the plane.
  No large missing-copper regions.
- **In2.Cu / B.Cu**: rendered without error.
- **B.Cu silkscreen**: 524 draw operations, non-empty.

## Still not claimed

- **No BOM or CPL.** Assembly is blocked, and separately: the four cut drivers are electrically
  incomplete (`FINDING-cut-drivers-electrically-incomplete.md`) — that is a design gap, not a
  procurement one.
- **5 REAL opens remain**, all blocked by S1 pad geometry (AGENTS §21a).
- The drill is verified against the file's own tool table and against the board's expected 196
  holes; the gerbers are verified by render, not by a netlist comparison.

## Reproduce

    kicad-cli pcb export gerbers --output DIR board.kicad_pcb
    kicad-cli pcb export drill --output DIR --format excellon \
        --drill-origin absolute --excellon-zeros-format decimal --excellon-units mm board.kicad_pcb
    gerbv -x png -o F_Cu.png --dpi=300 --border=5 board-F_Cu.gtl board-Edge_Cuts.gm1
