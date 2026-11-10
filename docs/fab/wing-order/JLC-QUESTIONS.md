# Wing interconnect — the two questions JLCPCB support has to answer

**Status: NOT ORDERABLE.** This document exists because the board cannot be
ordered until two questions are answered *by the fabricator/assembler*, in
writing. Neither answer is inferable from our own files, and neither has been
invented here.

- Board of record: `tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
  (sha256 `c05d5d5aa601b57c305574320fdeb8a98e1fcf8ada87b03cb0ed9998df1f0b0d`)
- Package of record: `docs/fab/wing-order/interconnect/` +
  `docs/fab/wing-order/interconnect-jlcpcb-upload.zip`
- Every geometric number below is read out of that board file by
  `tracker/hardware/measure_wing_interconnect.py`; the raw dump is committed at
  `docs/fab/wing-order/layout-facts/interconnect.json`.
- Rules quoted from JLCPCB are cited with their URL in §5. Nothing is quoted
  from memory.

---

## 0. What is already proven, and what is not

| | Status | Evidence |
|---|---|---|
| 2 layers, 0.4 mm, 34.6 × 20.0 mm | **MEASURED** | Edge.Cuts is 4 straight segments; centreline extent exactly 34.6 × 20.0 mm. `(thickness 0.4)`. |
| 32 tracks / 2 vias / DRC 0 violations, 0 unconnected | **MEASURED** | `kicad-cli pcb drc` → *Found 0 violations / Found 0 unconnected items* |
| BOM 3 × SS24 (C50645), CPL 3 placements, all top side | **MEASURED** | `interconnect/bom-jlc.csv`, `interconnect/cpl-jlc.csv` |
| Diode **cathode net** is on pad 1 for D1/D2/D3 | **PROVEN** | merged polarity guard + 3 reversed-diode rejection tests (PR #529 → `871f23fc`) |
| Package rebuilds byte-identically from master | **PROVEN** | `build_wing_order.py --check` → `REPRODUCIBLE`, 29/29 files; see `REPRODUCIBILITY.md` |
| **JLC's zero-angle model lands the banded end on pad 1** | **NOT PROVEN — Q1** | our guard proves the *net*, not their *placement model* |
| **A 34.6 × 20.0 mm × 0.4 mm board is assemblable at all** | **NOT PROVEN — Q2** | 0.4 mm is outside Economic PCBA; Standard needs ≥70 × 70 mm and published rules forbid V-cut at 0.4 mm |

Both open items are **manufacturer questions**. A more careful review of our own
files cannot close either one.

---

## 1. Q1 — the banded (cathode) end of each SS24

### 1.1 What the board says

The part is **SS24 in SMA (DO-214AC)**, LCSC **C50645**, MDD. Its datasheet states
*"Polarity: Indicated by cathode band"*. A Schottky rectifier body is therefore
**asymmetric in appearance but symmetric in footprint**: the two lands are
identical rectangles and nothing in the copper distinguishes K from A. The
cathode is whichever end the pick-and-place rotation puts the **band** on.

Our footprint `D_SMA_Wing` is symmetric by construction:

| | pad 1 | pad 2 |
|---|---|---|
| offset from footprint anchor | (−1.85, 0) mm | (+1.85, 0) mm |
| size | 2.30 × 1.55 mm | 2.30 × 1.55 mm |
| layers | F.Cu / F.Mask / F.Paste | F.Cu / F.Mask / F.Paste |

Because the lands are identical, **a 180° rotation error is electrically
invisible in the artwork and mechanically invisible in the paste layer**. It can
only be caught in JLC's own placement preview against their zero-angle model.

### 1.2 Per-diode cathode coordinates — board space

KiCad board space: origin at the **top-left** corner of the board outline, **X
right, Y down**, millimetres.

| Ref | Anchor (X, Y) | Rot | **Cathode = pad 1** (X, Y) | net | Anode = pad 2 (X, Y) | net |
|---|---|---|---|---|---|---|
| D1 | 14.00, 6.00 | 0° | **12.15, 6.00** | SOLAR_P | 15.85, 6.00 | SOLAR_MID1 |
| D2 | 22.00, 6.00 | 0° | **20.15, 6.00** | SOLAR_MID1 | 23.85, 6.00 | SOLAR_MID2 |
| D3 | 30.00, 6.00 | 0° | **28.15, 6.00** | SOLAR_MID2 | 31.85, 6.00 | SOLAR_N |

All three diodes sit on the **same Y row (6.00 mm)**, 8.00 mm apart in X, all at
rotation 0°, all on the **top** side.

### 1.3 The same three parts in JLC CPL space

Two conventions exist and they differ by a Y sign. Give support **both**, so
their preview can be compared to whichever one they read.

| Ref | committed `cpl-jlc.csv` (KiCad native absolute origin, Y **negative**) | Y-up-from-bottom-left equivalent |
|---|---|---|
| D1 | 14.000000, **−6.000000**, 0.000000, Top | 14.000000, **14.000000** |
| D2 | 22.000000, **−6.000000**, 0.000000, Top | 22.000000, **14.000000** |
| D3 | 30.000000, **−6.000000**, 0.000000, Top | 30.000000, **14.000000** |

Where the values come from: `kicad-cli pcb export pos --format csv --units mm`
on the board (unmodified origin), i.e. the footprint **anchor**, matching the
absolute coordinates used by the Gerber and Excellon files in the same package.
The drill file confirms the same frame — its two holes are
`X7.5 Y−10.9` and `X31.85 Y−10.9`, which are board (7.5, 10.9) and
(31.85, 10.9) with Y negated.

**The board is 20.00 mm tall.** So the two conventions put D1's cathode 6 mm from
one edge or 6 mm from the other — a difference a preview shows immediately and
that nothing in the Gerber can disambiguate. This is exactly what support has to
confirm.

### 1.4 What to look for in their preview

For each of D1, D2, D3 the **banded end must point toward −X** (toward X = 0,
the tab end) if their preview puts the board's origin at the tab side. Concretely,
in the preview the band must be on the pad listed above as **pad 1**, i.e. the
pad that will carry `SOLAR_P` / `SOLAR_MID1` / `SOLAR_MID2` respectively.

Electrical consequence if any one is reversed, measured from the netlist: a
reversed bypass diode is a **permanent short across one cell**, not an open. The
string then cannot rise above that cell's Vf ceiling and the cell is
reverse-biased whenever the string conducts — the exact failure the diode was
fitted to prevent. This is why the answer is required in writing and not eyeballed
from a low-resolution preview.

---

## 2. Q2 — is a 34.6 × 20.0 mm × 0.4 mm board assemblable at all?

### 2.1 The measured board

| Property | Measured value | Source |
|---|---|---|
| Outline (Edge.Cuts **centreline**) | **34.60 × 20.00 mm** | 4 straight segments, y=0, y=20, x=0, x=34.6 |
| Outline (as JLC's Gerber reader will bbox it) | 34.70 × 20.10 mm | outline line width 0.10 mm adds 0.05 each side; the `.gbrjob` already reports 34.7 × 20.1 |
| Thickness | **0.40 mm** | `(thickness 0.4)` |
| Copper layers | **2** | F.Cu / B.Cu; no inner layers, no zones |
| Stackup | F.Cu 0.035 / FR4 0.310 / B.Cu 0.035, mask 0.010 each side | `.gbrjob` `MaterialStackup` |
| Surface finish | **not specified in the package** | `.gbrjob` `"Finish": "None"` — must be chosen at order time; 0.4 mm is ENIG-only at JLCPCB |
| Board area | 6.92 cm² | 34.6 × 20.0 |
| Footprints | **7** (D1, D2, D3, J1, SC1, SC2, SC3) | measured |
| Placements for assembly | **3** (D1, D2, D3), all top side | `cpl-jlc.csv` |
| Tracks / vias | 32 tracks, 2 vias (0.40 mm drill, 0.80 mm pad, F.Cu→B.Cu, through) | measured |
| Drill file | 2 holes, both 0.400 mm, plated | `interconnect.drl` |
| **Fiducials** | **NONE.** No fiducial footprint, no fiducial pad, no free pad on either side. 7 footprints total, all functional. | measured |
| Tooling holes | NONE (NPTH count = 0) | measured |
| Castellated features | **NONE** — the outline has no notch, slot, or castellation; it is a plain closed rectangle | measured |
| Minimum copper-to-board-edge | **1.60 mm** (J1 pads and D3 pad 2); tracks are ≥2.35 mm | measured |

### 2.2 Why this is a question and not a decision we can take

JLCPCB publishes, on the assembly capabilities page:

- **Economic PCBA:** thickness **0.8 – 1.6 mm**; single PCB **10 × 10 mm – 470 × 500 mm**; *edge rails not necessary*; *fiducials not necessary*.
- **Standard PCBA:** thickness "No limit"; single PCB **70 × 70 mm – 460 × 500 mm**; **panel 70 × 70 mm – 250 × 250 mm**; **edge rails necessary**; **fiducials necessary**.

and on the thickness page:

- **"For 0.4 mm thickness boards, only ENIG finish is accepted. These boards cannot be made with a panel and are not available for 1-layer PCBs."**

and on the V-cut page:

- **"V-cut is only supported for board thicknesses ≥ 0.6 mm. 0.4 mm boards are not supported."**

and on the fixtures page:

- **"If the board thickness is 0.4 mm or 0.6 mm, the carrier shall be used for printing and component placement."**

Put together, those four statements are mutually awkward for *this* board:

1. 0.4 mm is outside Economic PCBA, so it must go Standard.
2. Standard requires ≥70 × 70 mm — but as a **single board** this is 34.6 × 20.0 mm, which is *under* the minimum on both axes and *over* Economic's maximum thickness.
3. Standard also requires **edge rails and fiducials**, and the board has **neither** — there is no room for a 1 mm fiducial 3.35 mm from an edge on a 20 mm dimension without consuming placement area, and no tooling holes.
4. The usual way to satisfy (2) is to panelise — but the thin-board page says 0.4 mm boards **cannot be made with a panel**, and the V-cut route is explicitly closed at 0.4 mm. Mouse-bite/tab routing is not forbidden by either page, but neither page says it is *accepted* at 0.4 mm either.

So the board lands in a gap between four published rules. **We are not going to
guess which rule wins.** That is the question.

### 2.3 Options we are NOT assuming

None of these has been selected. Each changes the order, and two of them change
the design:

| Option | What it costs | What it needs |
|---|---|---|
| A. Order bare PCBs only, hand-solder the 3 SS24 | no assembly service at all; 6 hand joints per board | nothing from JLC beyond bare-board fab (0.4 mm **is** a supported bare-board thickness, ENIG) |
| B. Standard PCBA on a self-panelised 6-up (see `PANELIZATION.md`) | panel fee, rails, fiducials added to rails, depanel burr on the two functional edges | JLC to accept a 0.4 mm routed/mouse-bite panel, and to confirm rails + fiducials on the rails satisfy their requirement |
| C. Change thickness to 0.6 mm so V-cut and Standard become legal | +0.2 mm on a **mass-critical** flight part; ADR-132/ADR-063 mass budget must be re-run; 0.6 mm at 2-layer is legal | an **operator decision**, not an agent one |
| D. Change thickness to 0.8 mm and use Economic PCBA | same mass penalty, larger | operator decision; Economic also forbids castellations (none here) |

**Do not pick one of these on the operator's behalf.** Option C/D are mass
changes to a flight part; Option A removes the assembly service; Option B
depends on Q2's answer.

---

## 3. Copy-pasteable support message

> **Subject:** DFM/assembly confirmation for a 34.6 × 20.0 mm, 0.4 mm, 2-layer board with 3 × SMA diodes (2 questions)
>
> Hello,
>
> I have a small 2-layer board I would like to have assembled, and I have two
> questions I could not resolve from the published capability pages. I would
> rather confirm before ordering than receive boards that need rework.
>
> **The board**
>
> - Outline 34.6 mm × 20.0 mm (outline centreline; the Gerber bbox reads
>   34.7 × 20.1 mm because of the 0.1 mm outline line width)
> - 2 layers, **0.4 mm** finished thickness, FR4, ENIG
> - Stackup per the .gbrjob: F.Cu 35 µm / FR4 310 µm / B.Cu 35 µm, 10 µm mask each side
> - 32 tracks, 2 plated through vias (0.4 mm drill / 0.8 mm pad)
> - 7 footprints: 3 diodes to be placed, plus 4 connector/land footprints that
>   are NOT placed (no paste apertures on them)
> - **No fiducials, no tooling holes, no castellations**
> - 3 placements, all on the top side: D1, D2, D3, part **SS24, SMA
>   (DO-214AC), LCSC C50645**, rotation 0° for all three
>
> **Question 1 — diode orientation in your placement preview**
>
> The SS24 is a Schottky rectifier whose cathode is marked with a band on the
> body. My footprint has two identical 2.30 × 1.55 mm lands, so a 180° error is
> invisible in the Gerber and in the paste layer — the only place it can be
> checked is your placement preview.
>
> Board coordinates (origin at the board's top-left corner, X right, Y down):
>
> | Ref | Cathode (banded) end must be at | Anode end at |
> |---|---|---|
> | D1 | X 12.15, Y 6.00 | X 15.85, Y 6.00 |
> | D2 | X 20.15, Y 6.00 | X 23.85, Y 6.00 |
> | D3 | X 28.15, Y 6.00 | X 31.85, Y 6.00 |
>
> My CPL file (`cpl-jlc.csv`, KiCad absolute origin, mm) reads:
> `D1,14.000000,-6.000000,0.000000,Top`, and likewise D2 at X 22 and D3 at X 30,
> all at Y −6.000000. Because the board is 20.0 mm tall, the same parts would read
> Y 14.000000 if your importer places the origin at the bottom-left with Y
> increasing upward.
>
> **Please confirm, in your preview, that the banded (cathode) end of each of
> D1, D2 and D3 lands on the pad at X = 12.15 / 20.15 / 28.15 respectively — and
> tell me which Y convention your preview used, so I know whether to flip the
> sign in the CPL I upload.** A screenshot of the placement preview would be
> ideal.
>
> **Question 2 — is this board assemblable at 0.4 mm, and how?**
>
> Reading your published pages together, I could not tell which rule applies:
>
> - Economic PCBA lists thickness 0.8–1.6 mm, so 0.4 mm is outside it.
> - Standard PCBA lists single PCB 70 × 70 mm minimum and requires edge rails
>   plus fiducials — this board is 34.6 × 20.0 mm and has neither.
> - Your thickness page says 0.4 mm boards "cannot be made with a panel".
> - Your V-cut page says V-cut is not supported for 0.4 mm.
> - Your fixtures page says a carrier "shall be used" for 0.4 mm and 0.6 mm
>   boards for printing and placement.
>
> **Please confirm which of these is possible for this board, and what you need
> from me for each:**
>
> 1. Can you assemble it as a **single, unpanelised 34.6 × 20.0 mm 0.4 mm board**
>    on Standard PCBA, using your carrier/fixture and adding fiducials as you
>    normally do? If the 70 × 70 mm minimum is absolute for a single board, please
>    say so.
> 2. If it must be panelised, can a **0.4 mm** board be supplied as a
>    **routed / mouse-bite tab panel** (not V-cut)? I can supply a 6-up panel at
>    81.2 × 74.0 mm with 5 mm rails and 2 mm gaps — would you accept that, and
>    would you add fiducials and tooling holes to the rails?
> 3. If neither works at 0.4 mm, what is the **minimum thickness** at which you
>    would assemble it, and would that change the panel/rail/fiducial
>    requirements?
>
> I am not asking for a price yet — just whether the process is possible and what
> the panel/rail/fiducial expectation is. Thank you.
>
> Files: Gerbers + drill + BOM + CPL attached as
> `interconnect-jlcpcb-upload.zip`.

---

## 4. What a "yes" and a "no" would each mean

| Answer | Consequence |
|---|---|
| Q1 confirmed: band on pad 1 at those coordinates | the polarity guard's net assignment and JLC's model agree; Q1 closes; record the screenshot as the evidence |
| Q1: band is on pad 2 for any diode | **do not order.** Either mirror the CPL rotation by 180° for that diode, or mirror the footprint; re-run the guard and the reversed-diode tests afterwards |
| Q1: "we cannot check, it is your data" | Q1 stays OPEN. Fall back to hand assembly (option A), where a human sees the band |
| Q2 yes (single board, carrier, Standard) | order path exists; fiducials/rails are JLC's to add; still needs the 0.4 mm ENIG selection at order time |
| Q2 yes (0.4 mm tab panel accepted) | build the 6-up panel per `PANELIZATION.md`; file a new design revision, because the current board has no panel frame |
| Q2 no at 0.4 mm | **operator decision**: 0.6/0.8 mm (mass change) or hand-solder at 0.4 mm (option A) |

---

## 5. Sources for every quoted rule

Fetched 2026-11-10; the pages are server-rendered and were read as text, not
through a browser.

| Claim | URL |
|---|---|
| Economic 0.8–1.6 mm; Standard no thickness limit; single 70 × 70 min; panel 70 × 70 – 250 × 250; rails and fiducials "Necessary" for Standard | `https://jlcpcb.com/capabilities/pcb-assembly-capabilities` |
| "0.4 mm … only ENIG … cannot be made with a panel" | `https://jlcpcb.com/resources/pcb-thickness` |
| "V-cut is only supported for board thicknesses ≥ 0.6 mm. 0.4 mm boards are not supported."; V-cut 70 × 70 min | `https://jlcpcb.com/blog/v-cut-panelization-standards` |
| "If the board thickness is 0.4 mm or 0.6 mm, the carrier shall be used" | `https://jlcpcb.com/help/article/pcb-assembly-fixtures` |
| Mouse-bite: 0.60 mm holes, 5–8 per set, 0.35–0.4 mm edge spacing, 1.6–2 mm panel gap, "thinner boards may require slightly larger spacing" | `https://jlcpcb.com/blog/mouse-bite-panelization-guide` |
| Standard PCBA fee table (setup $25.56/side, stencil $8.21, fixture $8.21, $0.48/board minimum) | `https://jlcpcb.com/help/article/pcb-assembly-price` |
| SS24 cathode "Indicated by cathode band"; SMA/DO-214AC; 2 A / 40 V | MDD SS24 datasheet (via `https://www.lcsc.com/product-detail/C50645.html`) |

---

## 6. Open items — do not close these by assertion

1. **Q1 unanswered.** No JLC placement preview has been obtained.
2. **Q2 unanswered.** No written acceptance of 0.4 mm assembly for this outline exists.
3. **Surface finish is not in the package.** `.gbrjob` says `"Finish": "None"`; it must be ENIG at order time, and that is an order-form choice, not a design fact.
4. **Silkscreen carries no cathode mark.** Measured: the only silkscreen on the board is `IC v1`, the three `D1..D3` / `SC1..SC3` designators, and three `+` marks on the cell lands. There is **no band/line marking the diode cathode**. That is not a blocker for machine placement (which uses the CPL), but it removes the human's only visual check, so it makes Q1 more load-bearing, and it is worth adding a cathode mark in the next revision.
5. **The 0.4 mm thickness itself is a design decision with a mass consequence** (ADR-132 §7 mass table). Nothing here proposes changing it.
