# JLCPCB order settings — PARTIAL ASSEMBLY, board `0602c7c8`

Two orders in one upload: **bare PCB × 5** plus **assembly of 30 placements**. Settings for both,
in the order the JLC quote page asks for them.

## Step 1 — PCB specification

| JLC field | Value | Why |
|---|---|---|
| Base Material | FR-4 | — |
| Layers | **4** | board is 4-layer |
| Dimensions | **72.10 × 80.10 mm** | Edge.Cuts bounding box, measured |
| **PCB Thickness** | **1.600 mm** | `GetBoardThickness()` = 1.600 mm. The doc's "re-price at 0.8 mm" note was about a *quote* default, not the board — the board is 1.6 mm |
| **Copper Weight** | **1 oz outer / 0.5 oz inner** | the stack S1's minimums were quoted against |
| Min Trace/Spacing | **0.20 / 0.20 mm** | S1; nothing on the board needs finer |
| Min Via Hole | **0.30 mm** | every via |
| Min Via Diameter | **0.60 mm** | every via, annulus 0.150 mm |
| Surface Finish | **HASL (lead-free)** | meets the 0.13 mm via annulus; ENIG not needed — the finest pitch here is 0.5 mm QFN on a DNP site |
| Soldermask | Green | cheapest |
| Silkscreen | White | both sides carry legend |
| **Via Covering** | **Tented** (default) | no test points on vias |
| Gold Fingers | No | — |
| **Confirm Production File** | **No** | the files are verified; this adds days for nothing |
| Remove Order Number | Specify a location | keeps the edge clean |
| Panel by JLC | **Yes** | small board; free, and protects the edge slots |
| **Quantity** | **5** | first article |

### Drill table (as it will reach them)

```
0.200 mm   12   U1.41 thermal pad      PTH
0.300 mm  161   every via              PTH
1.000 mm   15   component pins         PTH
2.500 mm    8   H1-H4, HW1-HW4         NPTH
          ---
          196   total  (188 plated + 8 non-plated)
```

### Order notes to paste into the "special instructions" box

```
Bare + partial assembly. 4-layer FR4, 1.6 mm, 1 oz outer / 0.5 oz inner, HASL lead-free.
Min trace/space 0.20/0.20 mm. All vias 0.60 mm dia / 0.30 mm drill (annulus 0.150).
Drill: 188 plated + 8 NPTH. Please do NOT normalise any drill size.
Four 0.5 x 6.0 mm slots on the board edges are intentional (wing sockets) - they are Edge.Cuts.
Do not panel so that a socket slot lands on a break-away edge.
This is a partial assembly: the BOM is the complete population list - do not add parts.
```

## Step 2 — Assembly specification

| JLC field | Value |
|---|---|
| Assembly Side | **Top + Bottom** (24 top, 6 bottom) |
| **PCBA Type** | **Standard** (not Economic — the bottom side and the QFN/U1 module need it) |
| Quantity | 5 |
| Tooling holes | Added by JLC |
| **Parts selection** | **"Do not include parts not in BOM"** — the BOM is complete |

### Uploads

- **BOM:** `asm-bom-jlc.csv` — **13 lines, 22 placements** (the JLC-placeable subset)
- **CPL:** `asm-cpl-jlc.csv` — 30 rows, verified against `pcbnew` coordinates to <0.001 mm.
  JLC will match the 22 it places; the 8 hand-fit rows are ignored or flagged by JLC's uploader
  as "part not in BOM", which is the correct behaviour.
- **Hand-fit list:** `asm-bom-jlc-handfit.csv` — 5 lines, 8 placements

### Both files must agree on the same 30 references

```
C10 C4 C_BULK C_HF C_MON D1 D_BP1 D_BP2 D_BP3 D_BP4 D_HUB1 D_HUB2
J_HUB_PV J_PROG J_W1 J_W2 J_W3 J_W4 R_BAL1 R_BAL2 R_DIV1 R_DIV2
R_F1 R_MON1 R_MON2 U1 U3 U7 U_C U_LORA1280
```

## ⚠ The one thing blocking the assembly upload

**`asm-bom-jlc.csv` has an empty `LCSC Part #` column.** All 18 lines need part numbers before JLC
can price or build. This is deliberate — an unverified part number must never enter a paid order,
and `C5913567` (the F33) is already flagged `(check)` in the project's own docs.

The 18 lines needing a number:

```
SS24          D_SMA         6   LCSC has this; confirm the exact suffix
WING_SOCKET_4P Wing_Tab_4P  4   NOT a stocked part — this is a custom edge connector.
                                JLC cannot place it. It must be hand-fitted or excluded.
10k           0402          2
10uF          0402          2
1M            0402          2
4.7M          0402          2
100R          0402          1
100nF         0402          1
100uF         1206          1
10nF          0402          1
BAT54          SOD-123       1
HUB_PV_PANEL_5P 1x05 2.54   1   a pin header, stocked
J_PROG        1x06 2.54     1   a pin header, stocked
LoRa1280      LoRa1280      1   NiceRF module — NOT an LCSC part
ESP32-S3-WROOM-1U            1   stocked (Espressif)
LoRa2021_Castellated  ×2     2   NiceRF module — NOT an LCSC part
SOT-23-5                     1   value is 'U7', not a part — needs identification
```

**Five of the 20 lines are not LCSC-stockable** — `WING_SOCKET_4P` (custom edge connector),
`LoRa1280`, the two `LoRa2021_Castellated` modules (all NiceRF), and `U7` whose value field is
literally `"U7"` — it has no part identity. That is the real assembly problem: a JLC assembly order
cannot place modules the project buys from NiceRF.

## Honest summary of what JLC can and cannot build

Measured, not estimated:

| | lines | placements |
|---|---|---|
| **JLC can place** | **13** | **22** |
| **must be hand-fitted** | **5** | **8** |
| **total** | **18** | **30** |

**JLC can place 22:** the 6 SS24 diodes, the BAT54, 8 passive lines (12 placements), both pin
headers, and the ESP32-S3-WROOM-1U.

**Hand-fit 8:** the 4 wing sockets, `U3` and `U_C` (LoRa2021), `U_LORA1280` (LoRa1280), and `U7`
until it is identified.

Two BOM files are therefore provided:

- **`asm-bom-jlc.csv`** — 13 lines / 22 placements, upload this to JLC
- **`asm-bom-jlc-handfit.csv`** — 5 lines / 8 placements, your hand-fit list

Practical options, in order of cost:

1. **Order bare PCBs + JLC-assemble the 23 stockable placements**, hand-solder the 7 modules. This
   is what the population decision already assumes for the GPS (bought loose), and modules are the
   parts you would hand-place anyway.
2. **Order bare only** and assemble everything by hand — viable at 30 placements, and avoids the
   assembly setup fee entirely.
3. Fill the LCSC column and let JLC do the 23 — least hand work, most paperwork.

## What is verified vs assumed

**Verified on this machine:** dimensions, thickness, layer count, drill table, all 30 CPL
coordinates, BOM↔CPL reference agreement, gerber geometry identical across all 7 layers, DRC
unchanged.

**Assumed, not verified:** JLC's *current* per-placement and setup fees (the analysis flags this as
unmeasured); the stock status of each passive at JLC's library on the day of order; the `U7` part
identity.
