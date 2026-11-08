# JLCPCB order settings — bare board, board `31efa2da`

Copy-paste settings for placing the bare-board order. Nothing here is assembled: no BOM, no CPL.

## The files

`docs/analysis/bulk-route-20261107/fab-11opens/` — 28 files. Upload the whole directory as a zip,
or upload `board-job.gbrjob` and let JLCPCB match the rest.

**Required by JLCPCB:**
```
board-F_Cu.gtl          L1 top copper
board-In1_Cu.g1         L2 inner
board-In2_Cu.g2         L3 inner
board-B_Cu.gbl          L4 bottom copper
board-F_Mask.gts        top soldermask
board-B_Mask.gbs        bottom soldermask
board-F_Silkscreen.gto  top legend
board-B_Silkscreen.gbo  bottom legend
board-Edge_Cuts.gm1     board outline / profile
board.drl               drill (PTH + NPTH combined)
```

**Also present, JLCPCB ignores or treats as documentation:** F/B_Paste, F/B_Adhesive, F/B_Fab,
F/B_Courtyard, Margin, User_1..4, User_Drawings, User_Comments, User_Eco1, User_Eco2. Do not
delete them; they cost nothing and the job file references them.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Base material | FR-4 | — |
| Layers | **4** | board is 4-layer |
| Dimensions | **72.10 × 80.10 mm** | measured from Edge.Cuts bounding box |
| Board thickness | **1.600 mm** | `GetBoardThickness()` = 1.600 mm |
| Copper weight | **1 oz** outer / **0.5 oz** inner | S1 assumed the ≥4-layer 0.5/1 oz stack; all minimums quoted against it |
| Surface finish | **HASL (lead-free)** | cheapest that meets the 0.13 mm via annulus; ENIG only needed for fine-pitch assembly, which this order is not |
| Soldermask colour | any | green is cheapest |
| Silkscreen colour | white on green | both sides have legend |
| Min trace / spacing | **0.20 / 0.20 mm** | S1; the board needs nothing finer |
| Min via hole | **0.30 mm** | every via |
| Min via diameter | **0.60 mm** | every via, annulus 0.150 mm |
| **Via covering** | **"Tented" (default)** | vias are non-functional, no test points on them |
| **Confirm production file** | **NO** | see below |
| Panel by JLCPCB | yes, default | small board, panelling is free |
| Quantity | **5** | first article; validate before a larger run |

## Drill table as it will reach them

```
0.200 mm   12 holes   U1.41 thermal pad (PTH)
0.300 mm  161 holes   every via on the board (PTH)
1.000 mm   15 holes   PTH component pins
2.500 mm    8 holes   H1-H4, HW1-HW4 mounting (NPTH)
          ---
          196 holes   total
```

**188 plated + 8 non-plated.** The drill file carries `TF.FileFunction,MixedPlating,1,4` and both
classes in one file, which JLCPCB's uploader handles; it separates them by the pad's plated flag.

## What changed on the last check, and why it matters

The board previously carried **three vias at 0.360 mm drill**:

```
0.600 land / 0.360 drill -> annulus 0.120 mm
```

JLCPCB's published minimum via annular ring is **0.13 mm**, so those three were **non-compliant as
submitted**. Worse, 0.360 is not a stocked drill — JLCPCB moves in 0.05 mm steps, so it would have
been produced as 0.35 (annulus 0.125) or 0.40 (annulus **0.100**, below minimum).

Those three vias were also off-S1: `latest.kicad_dru` freezes the via hole at 0.30 mm and enforces
it. They arrived with the FR3NETS batch from freerouting's geometry and were never normalised.

Fixed by reducing the drill to 0.300 on the same land: annulus 0.150, matching the other 158 vias.
The board now has **one** via geometry and **four** drill tools, all stocked sizes.

## Still true, and should be stated on the order for the record

- **5 REAL copper opens remain.** All four pad-local traps are blocked by S1 pad geometry; three of
  the four clear JLCPCB's real 0.09 mm process minimum (S1 is a deliberate 2× margin). None affects
  fabricability — they are internal copper connectivity, not a fab feature.
- **This is a bare board.** It cannot fly as-is: assembly is blocked separately, and the four cut
  drivers are electrically incomplete (`FINDING-cut-drivers-electrically-incomplete.md`). Ordering
  it is a first-article fabrication check, not a flight build.
- **The wing-socket cavities** (0.5 × 6.0 mm slots at each `J_Wn`) are Edge.Cuts features routed
  through the board outline. Worth naming in the order notes so they are not treated as damage.

## Order notes to paste

```
Bare PCB only. 4-layer FR4, 1.6 mm, 1 oz outer / 0.5 oz inner, HASL lead-free.
Min trace/space 0.20/0.20 mm. All vias 0.60 mm dia / 0.30 mm drill (annulus 0.150).
Drill: 188 plated + 8 NPTH (mounting). Please do NOT normalise any drill size.
Four 0.5 x 6.0 mm slots on the board edges are intentional (wing sockets) - Edge.Cuts.
Do not panel in a way that puts the socket slots on a break-away edge.
```
