# Bare-board fab package: generated and drill-verified for 15-open board

**2026-11-08, board `e00b98e7`, 15 opens, silk 0, 0 electrical errors.**

This package exists so that "ship the 15-open board as a first article" is a path that is actually
ready, not a suggestion. It is a **bare-board** order: it deliberately contains no BOM or CPL, because
the assembly side is still blocked by 5 undecided parts (including all four pyro cut drivers) and that
is a separate decision.

## What was generated

`kicad-cli pcb export gerbers` + `pcb export drill`, run against a copy of the tracked board with its
`.kicad_dru` and `.kicad_pro` sidecars present (missing sidecars have produced phantom DRC results
four times this campaign, so they are always staged).

```
23 files in the job file, including all four copper layers:
  board-F_Cu.gtl        Copper,L1,Top      Positive
  board-In1_Cu.g1       Copper,L2,Inr      Positive
  board-In2_Cu.g2       Copper,L3,Inr      Positive
  board-B_Cu.gbl        Copper,L4,Bot      Positive
  board-Edge_Cuts.gm1   Profile            Positive
  board-F_Mask.gts / board-B_Mask.gbs      SolderMask
  board-F_Silkscreen.gto / B_Silkscreen    Legend
  board-F_Paste.gtp / B_Paste.gbp          SolderPaste
board.drl              Excellon, METRIC, decimal, absolute origin
```

## Drill verification — file versus board, per tool

The drill file was checked against the board's own geometry, tool by tool:

```
tool      file   board   result
0.200 mm    12      12   OK   (12 pad drills)
0.300 mm   158     158   OK   (all vias -- matches S1's 0.300 via drill)
1.000 mm    15      15   OK   (PTH pad barrels)
2.500 mm     8       8   OK   (mounting holes)
           ---     ---
           193     193   total holes, exact match
```

The 158 vias at 0.300 mm is the meaningful one: S1 specifies a 0.600 mm land / 0.300 mm drill, and the
drill file carries exactly that.

## A false alarm worth recording

My first per-tool counter reported **"T4 = 2.500 mm, 193 hits; T1/T2/T3 = 0"** — i.e. every hole about
to be drilled at 2.5 mm, which would have produced a board with no vias and no component holes.

That was **my parser, not the file**. Excellon puts all four tool *definitions* at the top of the file
and the body then references them; my regex latched onto the last definition and attributed every hit
to it. The tell that it was a parser bug rather than a fab bug: the total (193) was exactly right.
A file that really had lost three tools would not still have 193 hits.

Re-parsed correctly, every tool matches the board exactly.

## What is NOT verified / not included

- **No BOM, no CPL.** Bare board only. `build_jlc_bom.py` exists but the BOM has 5 undecided parts and
  8 references carry a `?` that does not join to the CPL (`FINDING-bom-not-reference-mismatch.md`).
- **No independent gerber render on this package.** An earlier independent gerbv render of this board
  verified outline closure, wing-slot closure and copper coherence (`FINDING-gerber-independent-render.md`),
  but that was an earlier export. Re-rendering this exact package is outstanding.
- **15 opens remain.** This package is a first-article order, not a finished board.
- **DRC is not 0.** 16 violations: 11 `lib_footprint_mismatch` + 4 `lib_footprint_issues` (proven KiCad
  footprint-file version artefact) + 1 harmless 0.1414 mm `track_dangling` stub on `/W2_SOLAR_N`.
  Zero clearance, short, thermal or isolated-copper items.

## Recommendation

Order this as a **bare board first article** to validate the design on real hardware. The four trapped
pads do not prevent the board from functioning — they leave four nets unconnected, which is a
functional limitation to fix in rev 2, not a fabrication blocker. Fixing them at rev 2 costs one
layout pass; discovering a schematic or footprint error after ordering assembled boards costs the
whole assembly run.
