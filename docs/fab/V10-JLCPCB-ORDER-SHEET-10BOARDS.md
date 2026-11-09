# JLCPCB order sheet — balloon hub v10, 10 assembled boards

**Generated 2026-11-09.** Every field below is read from the board file or measured, not remembered.
Operator decisions this reflects:

- **10 assembled boards**, not bare. *(operator, 2026-11-09)*
- **`U_C` DNP.** `U3` carries the LoRa2021 function fully; `U_C` would be redundancy, and its four
  control lines have no MCU end. See ADR-145 for the v11 fix.
- **Both `/EN` and `/IO0` wires INCLUDED** in the assembly plan. *(operator, 2026-11-09)*

## Firm order data

| field | value | source |
|---|---|---|
| Dimensions | **72.00 × 80.00 mm** | `Edge.Cuts` extent, measured |
| Layers | **4** | board stack |
| Thickness | **1.6 mm** | board setup |
| Min track | **0.200 mm** | .kicad_dru (fab min 0.09 → 2.2× margin) |
| Min clearance | **0.200 mm** | .kicad_dru (fab min 0.09 → 2.2× margin) |
| Min via | drill **0.300** / pad **0.600** → annulus **0.150** | 161 vias, all identical |
| Via annulus | **0.150 mm = JLC multilayer floor exactly** | why ENIG + 1 oz |
| Drill table | `T1 0.200 ×12`, `T2 0.300 ×161`, `T3 1.000 ×15`, `T4 2.500 ×8` = **196 holes, 0 non-stock** | `board.drl` |
| Surface finish | **ENIG** | 0.150 annulus at floor; HASL adds thickness variance |
| Copper weight | **1 oz outer** | 2 oz shrinks min space to 0.16 and forfeits the margin |
| Edge plating | **No** | |
| Castellated holes | **YES** | 4 wing sockets are edge-launched |
| Board colour / mask / silk | green / white / white | CHOICE |
| Quantity | **10** | operator |
| Assembly | **Top side, economic PCBA** | all placements are top |

## BOM — what JLC places (14 lines, 23 placements)

| ref(s) | value | footprint | qty | LCSC |
|---|---|---|---|---|
| `U1` | ESP32-S3-WROOM-1U-N8R8 | ESP32-S3-WROOM-1U | 1 | `C2980300` |
| `U7` | TPS7A0233DBVR | SOT-23-5 | 1 | `C5142805` |
| `C_BULK` | 100 µF **10 V** X5R | C_1206 | 1 | **`C312983`** ← changed from C15008 (6.3 V) for DC-bias |
| `D_BP1-4`, `D_HUB1-2` | SS24 | D_SMA | 6 | `C50645` |
| `D1` | BAT54W | D_SOD-123 | 1 | `C699107` |
| `C10`, `C4` | 10 µF 6.3 V | C_0402 | 2 | `C15525` |
| `C_HF` | 100 nF | C_0402 | 1 | `C1525` |
| `C_MON` | 10 nF | C_0402 | 1 | `C15195` |
| `R_BAL1`, `R_BAL2` | 10 k | R_0402 | 2 | `C25744` |
| `R_DIV1`, `R_DIV2` | 1 M | R_0402 | 2 | `C26083` |
| `R_F1` | 100 R | R_0402 | 1 | `C25076` |
| `R_MON1`, `R_MON2` | 4.7 M | R_0402 | 2 | `C11906` |
| `J_HUB_PV` | PZ254V 1×5 | PinHeader_1x05 | 1 | `C492404` |
| `J_PROG` | PZ254V 1×6 | PinHeader_1x06 | 1 | `C492405` |

**Parts substitution: OFF.** A substituted part in a first article destroys fault attribution.

## DNP — excluded from BOM and CPL

| ref | what | why |
|---|---|---|
| `U_C` | LoRa2021 | 4 control nets have no MCU end; only 2 usable GPIOs free (ADR-145) |
| `U2` | LoRa2021F33 2 W PA | +33 dBm not licence-free in Germany |
| `U5` | MAX-M10S GPS | hand-fit, 4 loose units |
| `U6` | MS5611 barometer | DNP by decision; NTC chain measures the cold |
| `C_CAP1`, `C_CAP2` | 3.3 F supercaps | DNP |
| `U_CUT1-4` | cut drivers | trigger mode undecided |
| `U_HUB_CVT` | hub PV converter | output net does not exist on v10 |
| `J_VCC` | solder jumper | left open, hand-select |

## Hand-fit after delivery (LCSC does not stock)

| ref | what | qty/board | approx |
|---|---|---|---|
| `U3` | LoRa2021 castellated (NiceRF) | 1 | ~$12 |
| `U_LORA1280` | LoRa1280 (NiceRF) | 1 | ~$11 |
| `J_W1-4` | wing sockets | 4 | $0 (board feature) |

**`U_C` is NOT on this list** — it is dropped entirely, saving one LoRa2021 (~$12).

## The two wires to add during assembly

Both are flash-time only; neither affects flight.

| wire | from | to | length | buys |
|---|---|---|---|---|
| `/EN` | `U1.3` | `J_PROG.3` | **30.7 mm** | hard reset from the header instead of power-cycling |
| `/IO0` | `U1.27` (GPIO0) | `J_PROG.6` | **17.2 mm** | force download mode if firmware disables the USB console |

Neither net has copper on the board — `/EN` was never routed, `/IO0` is now netlisted (netlist
fixed 2026-11-09) but unrouted because the router shorts it to `/USB_DN` on every attempt.

Solder 30 AWG wire-wrap or 0.2 mm enamel wire, tack to the pad, strain-relieve with a dot of
UV-cure or hot glue.

## Cost at 10

| item | per board | for 10 |
|---|---|---|
| components (measured LCSC ladders) | $6.32 | $63.19 |
| bare PCB | $2.80 | $28.00 |
| JLC fees (eng + extended + joints) | $3.54 | $35.39 |
| **JLC total** | **$12.66** | **$126.58** |
| hand-fit modules (APPROX) | $23.00 | $230.00 |
| **all-in** | **$35.66** | **$356.58** |

Hand-fit is **$23/board** here, not the earlier $35 — `U_C` is dropped. The module prices remain
**APPROX**; NiceRF has not been quoted.

## Files to upload

```
docs/analysis/bulk-route-20261107/assembly-partial/asm-bom-jlc.csv    (14 lines, 23 placements)
docs/analysis/bulk-route-20261107/assembly-partial/asm-cpl-jlc.csv    (30 rows, coords to <0.001 mm)
docs/analysis/bulk-route-20261107/fab-11opens/board-*.g*             (gerbers)
docs/analysis/bulk-route-20261107/fab-11opens/board.drl               (drill, 196 holes)
```

## What these boards will and will not prove

**Will prove:** 4-layer stack, 0.150 mm via annulus at JLC's floor, castellation wing cavities,
196-hole drill, 0.200 mm clearance at scale, and whether the ESP32/LoRa subsystem boots.

**Will NOT prove:** the hub PV charger (output net does not exist), the cut channel
(`U_CUT1-4` net-less), `F33_VSENSE` (41 mm gap), or `U_C`.

**Flash on arrival:** a blank board enumerates on the ESP32-S3's native USB-Serial-JTAG and
`esptool` can flash it **without `/EN` or `/IO0`**. The two wires are for reliability on reflash.
See `docs/analysis/FLASHING-V10.md`.

## Remaining unconnected records: 12

`/SPI2_SCK` (U2 DNP) · `/F33_VSENSE` (41 mm gap, U2 DNP) · `/VSCAP` ×2 (C_CAP1 DNP) ·
`/W2_SOLAR_N` · `/W3_SOLAR_N` ×2 (two-face lands, complete in assembly) ·
3 GND zones (anchors) · `/EN` · `/IO0` (the two wires).

**This order is placed by the operator, not by the agent** — AGENTS.md §STANDING AUTHORITY
excludes purchase orders.
