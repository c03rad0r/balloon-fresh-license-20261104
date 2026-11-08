# Partial assembly — 30 placements, 11 DNP, derived from the documented decision

**2026-11-08, board `766fa3aa`.** Population applied as DNP attributes on the board itself.

## Where the decision comes from

`docs/fab/RECOMMENDATIONS-ON-OPEN-DECISIONS.md` (2026-10-14) — the cost/benefit analysis of which
parts go on the board and which stay off. It records the operator's **LOCKED SPLIT** plus four
accepted recommendations. Four of its decisions set population:

| id | decision | population effect |
|---|---|---|
| **D1** | order the board as-is and defer the cut channel | `U_CUT1..4`, `U_HUB_CVT` → **DNP** |
| **D3** | the LOCKED SPLIT wins over the drifted BOM CSV | `U5` (GPS), `U6` (baro) → **DNP**, GPS bought loose |
| **D4** | supercaps DNP on flight 1, keep the sites | `C_CAP1`, `C_CAP2` → **DNP** |
| **D6** | keep `U2` as a DNP site, do not populate | `U2` (F33 PA) → **DNP** |

`J_VCC` was already DNP on the board — it is a solder jumper, the footprint is the part.

**Every one of these was unapplied before today.** Only `J_VCC` carried a DNP flag; the board was
declaring all 48 parts as populated. The analysis existed and had been accepted, but never reached
the board — the same drift class this campaign has caught six times.

## Why the board and not a list

The flags written are `FP_EXCLUDE_FROM_BOM | FP_EXCLUDE_FROM_POS_FILES`. `kicad-cli` honours both,
so the BOM and CPL are derived from the board and **cannot disagree with it by construction**. A
separate CSV of DNP references would be another derived artefact free to drift.

## What gets assembled — 30 placements, 18 unique lines

Split by whether JLC can place it. This matters more than any other split in this document: a JLC
assembly order cannot place the NiceRF modules or the custom wing sockets.

**JLC places 22 placements, 13 lines:**

```
SS24                  D_SMA              6   D_BP1..4, D_HUB1, D_HUB2
10k                   R_0402             2   R_BAL1, R_BAL2
10uF                  C_0402             2   C10, C4
1M                    R_0402             2   R_DIV1, R_DIV2
4.7M                  R_0402             2   R_MON1, R_MON2
100R                  R_0402             1   R_F1
100nF                 C_0402             1   C_HF
100uF                 C_1206             1   C_BULK
10nF                  C_0402             1   C_MON
BAT54                 D_SOD-123          1   D1
HUB_PV_PANEL_5P       1x05 P2.54         1   J_HUB_PV
J_PROG                1x06 P2.54         1   J_PROG
ESP32-S3-WROOM-1U     ESP32-S3-WROOM-1U  1   U1
```

**Hand-fit 8 placements, 5 lines:**

```
WING_SOCKET_4P        Wing_Tab_4P        4   J_W1..J_W4   custom edge connector
LoRa2021_Castellated  LoRa2021_...       2   U3, U_C      NiceRF module
LoRa1280              LoRa1280           1   U_LORA1280   NiceRF module
SOT-23-5              SOT-23-5           1   U7           no part identity yet
```

**Side split: 24 top, 6 bottom.**

## What stays off — 11 sites

| ref | part | why |
|---|---|---|
| `U_CUT1..4` | cut drivers (SOT-23-6) | D1 deferred — and electrically incomplete, 3/6 pads wired |
| `U_HUB_CVT` | hub converter (VQFN-16) | D1 deferral — 3/18 pads connected, cannot function if fitted |
| `U2` | LoRa2021F33 2 W PA | D6 — its power is unlawful at capability in DE (10 mW ERP) |
| `U5` | MAX-M10S GPS | D3 — LOCKED SPLIT: DNP rows + 4 loose units, hand-soldered |
| `U6` | MS5611 baro | D3 — cabin-pressurised thermal cycling makes its value low |
| `C_CAP1`, `C_CAP2` | ±3.3 F supercaps | D4 — accepted-risk register assumes them unfitted; charged-handling hazard |
| `J_VCC` | F33 VCC selector jumper | a solder jumper; the footprint IS the part |

All sites remain on the board. None requires a respin to populate later.

## Files

- `asm-bom-jlc.csv` — 18 lines, 30 placements, JLCPCB column layout. **The `LCSC Part #` column is
  present and EMPTY** — it must be filled before an assembly order; an unverified part number must
  never enter a paid order.
- `asm-cpl-jlc.csv` — 30 rows, `Designator,Val,Package,Mid X,Mid Y,Layer,Rotation`.

## The CPL transform, re-derived because this board's height is not the documented one

The earlier finding derived `jlc_y = H + cpl_y` with **H = 80.0 mm** on a 72.00 × 80.00 board. This
board's Edge.Cuts bounding box is **72.10 × 80.10** (y −0.050 … 80.050), so **H = 80.100 mm**. Using
80.0 would shift every part by 0.100 mm — plausible-looking and wrong, and it would place parts
0.1 mm off their pads.

H is therefore **measured from the board**, not hardcoded, and every row was verified against
`pcbnew`'s own footprint coordinates before the file was written:

```
VERIFIED: all 30 rows match pcbnew footprint coordinates to <0.001 mm
```

X range 0.00–72.00, Y range 0.10–80.10.

The CPL also excludes the 8 NPTH mounting holes. Without that, `kicad-cli pcb export pos` emits 38
rows including `H1..H4`/`HW1..HW4`, which would ask the assembler to place eight parts that do not
exist.

## Verified: nothing physical changed

```
tracks before/after    3092 / 3092   identical
pad positions          identical
DRC                    11 unconnected records, 16 violations, same type mix  (unchanged)
gerber geometry        all 7 layers byte-identical to the committed fab package
drill tools            identical
```

Only the attribute bits changed. The C10 freeze and the routed copper are untouched.

## Still blocking an assembly order

1. **The `LCSC Part #` column is empty.** 18 lines need part numbers before JLC can quote or build.
2. **`U5` and `U6` are DNP but the GPS is wanted on 4 units** — that is 4 loose MAX-M10S to buy and
   hand-solder, not an assembly line item.
3. **`U2` should not be bought in quantity** — D6 recommends 1–2 modules, not 10.
4. **The JLC per-placement fee is still unmeasured** — flagged in the analysis as the last
   unidentified cost. 30 placements, not the 37 the doc assumed.
