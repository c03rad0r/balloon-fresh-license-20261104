# Wing interconnect — panelisation arithmetic

**Status: ARITHMETIC ONLY. No panel design exists and none has been approved.**
This document answers "what panel would be needed, and does the design allow it"
with measured numbers. It does **not** answer whether JLCPCB will accept a 0.4 mm
panel — that is question **Q2** in `JLC-QUESTIONS.md` and it is unanswered.

Board: `tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`,
**34.6 × 20.0 mm** Edge.Cuts centreline, 0.4 mm, 2 layers, 6.92 cm².

---

## 1. Why a panel is being considered at all

JLCPCB Standard PCBA quotes a **single-PCB minimum of 70 × 70 mm** and a
**panel minimum of 70 × 70 mm**. This board is 34.6 × 20.0 mm, so it is under
the minimum on *both* axes as a single board. The only published route to a
70 × 70 mm footprint is a panel.

The competing fact is on the thickness page: **"For 0.4 mm thickness boards, only
ENIG finish is accepted. These boards cannot be made with a panel."** And the
V-cut page: **"V-cut is only supported for board thicknesses ≥ 0.6 mm."**

So the panel arithmetic below is necessary but **not sufficient**: it shows a
geometrically legal panel exists, not that JLC will make one at 0.4 mm.

## 2. Arithmetic

Assumptions, each a published or standard number:

- rails **5.0 mm** each side (JLC recommends 5–8 mm for assembly edge rails)
- board-to-board gap **2.0 mm** (mouse-bite panels: 1.6–2.0 mm; use the top)
- no V-cut (forbidden at 0.4 mm) → every separation is a routed slot or a
  mouse-bite tab, and **every** board therefore needs its own tabs

Reproduce with `/usr/bin/python3 tools/wing_panel_arithmetic.py`. Smallest legal
grids:

| grid | n-up | panel W × H (mm) | ≥70 × 70 | ≤250 × 250 | product cm² | panel cm² | utilisation |
|---|---|---|---|---|---|---|---|
| **2 × 3** | **6** | **81.2 × 74.0** | yes | yes | 41.52 | 60.09 | **69.1 %** |
| 3 × 3 | 9 | 117.8 × 74.0 | yes | yes | 62.28 | 87.17 | 71.4 % |
| 2 × 4 | 8 | 81.2 × 96.0 | yes | yes | 55.36 | 77.95 | 71.0 % |
| 4 × 4 | 16 | 154.4 × 96.0 | yes | yes | 110.72 | 148.22 | 74.7 % |
| 6 × 4 | 24 | 227.6 × 96.0 | yes | yes | 166.08 | 218.50 | 76.0 % |
| 6 × 11 | 66 | 227.6 × 250.0 | yes | yes (at the cap) | 456.72 | 569.00 | 80.3 % |

- **6-up at 81.2 × 74.0 mm is the smallest legal panel** — 2 columns × 3 rows.
  It clears 70 mm on both axes with 11.2 mm and 4.0 mm of margin.
- **1 × n does not work**: 1 × 3 is 44.6 × 74.0 mm and 1 × 4 is 44.6 × 96.0 mm —
  the width stays under 70 mm no matter how many rows are stacked. **At least two
  columns are mandatory**, so the panel is always ≥ 2 boards wide.
- Laminate cost per board at 6-up: 60.09 / 6 = **10.02 cm² per board** versus
  6.92 cm² as a single board = **1.45×** the laminate, before any panel fee.
- Utilisation only creeps from 69 % (6-up) to 80 % (66-up): rails and gaps are a
  fixed ~30 % tax on a board this small.

## 3. Does the design support breakaway tabs? — measured, not assumed

This is the part that is usually answered by assumption, so it is answered by
reading the board.

### 3.1 The Edge.Cuts outline has no castellated or notched feature

```
Edge.Cuts: 4 items, all SHAPE_T_SEGMENT, 0 arcs, 0 circles, 0 rects, 0 polys
  (0,0) → (34.6,0)
  (0,0) → (0,20.0)
  (0,34.6) … (34.6,0) / (34.6,20.0)
```

It is a **plain closed rectangle**: four straight segments, no castellation, no
notch, no slot, no internal cutout. The `.gm1` confirms it — one 0.10 mm circular
aperture and eight draw commands.

**So there is no outline feature that conflicts with a tab.** Nothing has to be
removed or re-routed to add one.

### 3.2 The wing tab is a PAD, not an edge feature

The thing called "the wing tab" (`J1`) is a **footprint with two SMD pads**, not
a castellated edge:

| | measured |
|---|---|
| `J1` anchor | (3.60, 10.00) mm |
| pad 1 | 4.00 × 1.20 mm at (3.60, 9.10), net `SOLAR_P` |
| pad 2 | 4.00 × 1.20 mm at (3.60, 10.90), net `SOLAR_N` |
| nearest copper to the left board edge | **1.60 mm** |

The wing socket on the hub is an Edge.Cuts slot in *the hub's* outline — it does
not exist on this board at all. There is **no castellation and no edge-plated
feature anywhere on the interconnect** (0 NPTH holes, 0 castellation pads; the
only drilled features are the 2 × 0.40 mm via holes).

### 3.3 What this means for tab placement

The conflict is therefore not geometric (nothing to break) but **mechanical and
electrical**: depanel stress and burr land on the edges where this board's
function lives.

| Edge | nearest functional copper | what a tab there would damage |
|---|---|---|
| X = 0 (left, tab end) | **1.60 mm** — `J1` pads 1 & 2 | the wing→hub interface pads; burr and micro-crack on the pads that carry the whole wing current |
| X = 34.6 (right) | **1.60 mm** — `D3` pad 2 (`SOLAR_N`); `SC3` pad 2 at 1.65 mm | the last diode's anode land and the cell tail |
| Y = 0 (top) | 5.22 mm — diode pads | safest; a tab here is ~5 mm from any copper |
| Y = 20.0 (bottom) | 3.00 mm — cell-tail pads | usable but closer |

So **tabs on the long (Y = 0 / Y = 20) edges are the only comfortable choice**,
and that is exactly the geometry the 2 × 3 grid gives (columns side by side in X,
rows stacked in Y, separation along Y). A tab on X = 0 or X = 34.6 should be
avoided: 1.60 mm of clearance is inside the "≥ 0.4 mm, recommended 1.0–2.0 mm"
V-cut/mouse-bite clearance band's *recommended* zone, and the pads there are the
ones the board exists to provide.

Mouse-bite sets per board: JLC wants **5–8 holes of 0.60 mm, edge spacing
0.35–0.4 mm**, and **at least 2 symmetric sets for boards under 30 mm wide** —
this board is 20 mm wide, so it needs **≥ 2 tab sets per board**, i.e. **≥ 12
sets on a 6-up panel**, and "thinner boards may require slightly larger spacing"
is stated without a number, which is another thing Q2 should ask.

### 3.4 Two things the current design does NOT have, that a panel needs

1. **A panel frame, rails, tooling holes and fiducials.** None exist. All of that
   is new artwork (`FRAME.gm1` or added Edge.Cuts + 3 fiducial footprints +
   3 NPTH tooling holes of ≥ 1.5 mm). That is a **design revision**, not an export
   option. `build_wing_order.py` cannot produce it, by design — it exports the
   board as drawn.
2. **Cathode silkscreen marks.** Measured: the entire front silkscreen is
   `IC v1`, `D1`/`D2`/`D3`, `SC1`/`SC2`/`SC3` and three `+` marks. There is **no
   band or line marking the diode cathode** anywhere. Panelising multiplies the
   number of boards a human cannot polarity-check visually, which makes Q1 more
   load-bearing rather than less.

## 4. The tradeoff, stated honestly

| | **A. bare boards + hand-solder 3 × SS24** | **B. 0.4 mm 6-up tab panel, Standard PCBA** |
|---|---|---|
| Fabrication | supported today: 0.4 mm 2-layer ENIG is a normal bare-board order; the board is 34.6 × 20.0 mm, inside every single-board fab envelope | needs Q2 answered YES |
| Assembly | none. **6 hand joints per board** (2 per diode) | 3 machine placements |
| New design work | **none** | panel frame + rails + fiducials + tooling holes + tab geometry = a revision, then re-verify DRC/export |
| Failure mode added | a human cold joint or a hand-reversed diode | depanel burr/crack 1.60 mm from the tab pads; 0.4 mm board handling |
| Polarity risk | **low** — the band is visible while hand-soldering; the silkscreen still has no band, but the part is in your hand | **Q1 becomes the only check**; no visual mark on the silkscreen |
| Cost shape | bare-board price only (small) | panel fee + Standard setup $25.56/side + stencil $8.21 + fixtures $16.42 + $0.48/board, plus ~1.45× laminate |
| Quantity needed | 4 wings → 4 boards, +spares. A 5-off bare order is the natural quantity | 6-up means **6 boards per panel**; at 4 wings you would order one panel and keep 2 spares |
| Blocks on | nothing (ordering is allowed once the operator says go) | Q2 |

**The honest asymmetry:** option A is available *today* and adds 6 hand joints
per board on a vehicle that is already hand-built; option B is a design revision
that trades those 6 joints for an unanswered manufacturing question, and adds a
depanel step 1.6 mm from the interface pads.

For 4 boards, option A's 24 hand joints are a small job for the person who is
already soldering the cells and the wing tab. Option B only starts to pay if the
wing count rises or if hand-soldering an SMA proves unreliable.

**This document does not recommend one.** The choice between a mass-neutral
hand-build and a manufacturing-question-dependent panel is the operator's, and
Option C/D (change thickness to 0.6/0.8 mm to reach Economic PCBA or legal
V-cut) is a **mass change to a flight part** that ADR-132's mass table would have
to be re-run for.

## 5. What would have to happen, in order, for option B

1. Q2 answered YES for a 0.4 mm routed/mouse-bite panel. *(blocking, external)*
2. Decide whether the panel is built by us or by "Panel by JLCPCB" — the latter
   exists only for regular outlines and adds fiducials/tooling to the rails.
3. New board revision with a panel frame: 6-up 81.2 × 74.0 mm at 5 mm rails and
   2 mm gaps, tabs on Y = 0 / Y = 20 only, ≥ 2 mouse-bite sets per board.
4. Re-run: `kicad-cli pcb drc` on the framed board, the export regression, and
   `build_wing_order.py --check` so the committed package still matches.
5. Only then an assembly order. **No order has been placed.**

## Sources

See `JLC-QUESTIONS.md` §5. The 70 × 70 mm minimums, the 0.4 mm "cannot be made
with a panel" clause, the V-cut ≥ 0.6 mm restriction and the mouse-bite
dimensions are all quoted there with URLs.
