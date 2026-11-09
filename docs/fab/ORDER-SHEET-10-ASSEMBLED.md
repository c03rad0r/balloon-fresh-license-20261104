# JLCPCB order sheet — 10 boards, assembled, `U_C` DNP

**Board of record:** `docs/analysis/bulk-route-20261107/latest.kicad_pcb`
**Board SHA:** `92ff3705`
**Generated from the artefacts on this branch — every number below is read from the board or the
derived CSVs, not retyped.**

Placement of the order itself is outside assistant authority (`AGENTS.md` line 153). This sheet is
everything needed to place it.

---

## 1. Bare board

| setting | value | source |
|---|---|---|
| Size | **72.10 × 80.10 mm** | `Edge.Cuts` bbox, measured `x −0.050..72.050`, `y −0.050..80.050` |
| Layers | **4** | design |
| Thickness | 1.600 mm | `docs/fab/JLCPCB-ORDER-SETTINGS.md` |
| Copper | 1 oz outer / 0.5 oz inner | ditto |
| Surface | HASL lead-free | ditto |
| Vias | tented | ditto |
| Quantity | **10** | operator decision |

**Drill table — 4 standard tools, 196 holes:**

| tool | dia | holes | what |
|---|---|---|---|
| T1 | 0.200 mm | 12 | `U1.41` module thermal pad — **not vias** |
| T2 | 0.300 mm | 161 | all vias, 0.600 mm land, 0.150 mm annulus |
| T3 | 1.000 mm | 15 | through-hole pads |
| T4 | 2.500 mm | 8 | NPTH mounting: `H1–H4`, `HW1–HW4` |

PTH 188 / NPTH 8. All annuli ≥ 0.150 mm against JLCPCB's 0.13 mm minimum.
**Do not normalise the drill sizes.** The four edge slots are intentional wing sockets.

## 2. Assembly — 29 placements, both sides

BOM: `docs/analysis/bulk-route-20261107/assembly-partial/asm-bom-jlc.csv` — **14 lines**
CPL: `docs/analysis/bulk-route-20261107/assembly-partial/asm-cpl-jlc.csv` — **29 rows**, every row
verified to <0.001 mm against pcbnew (`docs/analysis/make_cpl_from_board.py`).

Side split **24 top / 5 bottom** (counted from the CPL `Layer` column, not estimated).

**Standard PCBA, both sides.** Extended-part fee applies to 9 part numbers:

| line | designators | qty | LCSC |
|---|---|---|---|
| U1 ESP32-S3-WROOM-1U-N8R8 | U1 | 1 | `C2980300` |
| U7 TPS7A0233DBVR | U7 | 1 | `C5142805` |
| 100 µF 1206 10 V X5R | C_BULK | 1 | `C312983` |
| SS24 | D_BP1..4, D_HUB1, D_HUB2 | 6 | `C50645` |
| 10 µF 0402 | C10, C4 | 2 | `C15525` |
| 10 kΩ 0402 | R_BAL1, R_BAL2 | 2 | `C25744` |
| 4.7 MΩ 0402 | R_MON1, R_MON2 | 2 | `C11906` |
| 1 MΩ 0402 | R_DIV1, R_DIV2 | 2 | `C26083` |
| 100 nF 0402 | C_HF | 1 | `C1525` |
| 10 nF 0402 | C_MON | 1 | `C15195` |
| 100 Ω 0402 | R_F1 | 1 | `C25076` |
| BAT54W | D1 | 1 | `C699107` |
| 1×5 2.54 mm header | J_HUB_PV | 1 | `C492404` |
| 1×6 2.54 mm header | J_PROG | 1 | `C492405` |

## 3. What is NOT fitted — 20 sites

Read from the board's own `dnp` / `exclude_from_bom` attributes:

`U_C` (LoRa2021 #2 — **ADR-145**, 2 usable GPIOs for 4 signals), `U2` (F33 2 W PA — unlawful at
10 mW ERP in DE), `U5` (GPS), `U6` (baro), `C_CAP1`, `C_CAP2` (supercaps — charged-handling hazard),
`U_CUT1..4` (cut channel — electrically incomplete), `U_HUB_CVT`, `J_VCC` (solder jumper — the
footprint is the part), plus `H1–H4` and `HW1–HW4` (mechanical).

**`U_C` is DNP on the board, absent from the BOM, and absent from the CPL.** All three agree.

## 4. Hand-fit after delivery — 3 lines

`docs/analysis/bulk-route-20261107/assembly-partial/asm-bom-jlc-handfit.csv`

| part | designator | qty | source |
|---|---|---|---|
| Wing socket 4-pin | J_W1..J_W4 | 4 | custom edge connector — a board feature, nothing to buy |
| LoRa1280 | U_LORA1280 | 1 | NiceRF, no-PA per ADR-139 (~$11, APPROX) |
| LoRa2021 castellated | U3 | 1 | NiceRF (~$12, **APPROX — needs a vendor quote**) |

`U_C` has been **removed** from this list (ADR-145): it cannot be commanded on v10.

## 5. Rework before first flash — 2 wires per board

See `assets/REWORK-two-wires.png` (bench note, drawn at true board coordinates).

| wire | from | to |
|---|---|---|
| 1 | `U1` pad 3 (`/EN`) | `J_PROG` pin 3 |
| 2 | `U1` pad 27 (`/IO0`) | `J_PROG` pin 6 |

30 AWG wire-wrapping wire. Solder to the castellated module pad, tack the other end into the header
hole. Keep runs short and away from the USB D+/D− pair on pads 13/14.

**Do not bridge** `U1.3`→`U1.4` or `U1.27`→`/USB_DN`: those are the exact shorting paths the router
produced on every attempt.

**Why they are wires:** `U1` pads are 1.50 mm wide on a 1.27 mm pitch (0.23 mm overlap); a track
needs 0.600 mm of channel; a flood fill from `U1.3` reaches only a 2.0 × 1.4 mm pocket. See
`FINDING-en-unroutable-flash-blocked.md`.

## 6. Order notes to paste into the JLCPCB remarks field

> 4-layer, 1.6 mm, 1 oz outer / 0.5 oz inner, HASL lead-free, vias tented.
> Do not modify or normalise the drill sizes — the four 2.5 mm holes are mounting holes and the
> 0.2 mm tool is a module thermal pad, not a via.
> The four slots on the board edges are intentional wing-socket cavities — do not remove them.
> Assembly: both sides, 29 placements. Component U_C is intentionally not fitted.

## 7. Cost

From `model_board_cost.py` at quantity 10:

| item | USD |
|---|---|
| Bare PCB | 28.00 |
| Components (JLC) | 6.32 |
| Engineering fee | 8.00 |
| Extended parts (9 × $3) | 27.00 |
| Joints (23 × $0.0017) | 0.39 |
| **JLC total for 10 boards** | **69.71** |
| Hand-fit parts (APPROX) | ~338 |
| **Realistic total** | **~408 for 10 boards (~$41/board)** |

The hand-fit figure carries the LoRa2021/LoRa1280/wing-socket estimates and is **APPROX** — those
are not LCSC prices and should be replaced with vendor quotes.

## 8. Status of this revision — read before ordering

**This is a bring-up board, not a flight board.** It will prove the power path, the MCU and the
`U3` radio. Three things do not work on v10 and need the respin:

1. **Cut channel** — `U_CUT1..4` are unwired (3 of 6 pads each); no cut-drive, nichrome-output,
   arming or gate-drive net exists.
2. **`/F33_VSENSE`** — a 40.9 mm missing trunk; the 2 W PA's current sense never reaches the MCU
   (inert today because `U2` is DNP).
3. **`/EN` and `/IO0`** — no copper; bridged by the two wires above.

DNP gates: `REAL 6` opens, `check_unconnected_exclusions.py --expect-real 6` **PASS**,
0 DRC violations, silk clean.

---

## Reproduce

```
cd docs/analysis/bulk-route-20261107
kicad-cli pcb drc --format json --severity-all -o /tmp/drc.json latest.kicad_pcb
cd ../.. && /usr/bin/python3 -B tracker/hardware/check_unconnected_exclusions.py \
    docs/analysis/bulk-route-20261107/latest.kicad_pcb --drc /tmp/drc.json --expect-real 6
/usr/bin/python3 docs/analysis/make_cpl_from_board.py
```
