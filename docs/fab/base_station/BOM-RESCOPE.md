# Base station BOM — post-ADR-149 (control board)

**Scope:** this record implements [ADR-149](../../../docs/adr/149-base-station-control-board-rescope.md).
The base station stops being an analogue RF instrument and becomes a **control board**; the 433 MHz
receive front end is a purchased SPI module.

> **UPDATE — this board is now merged with the inflator.** [ADR-150](../../../docs/adr/150-inflator-and-radio-on-one-board.md)
> supersedes ADR-147 and puts the pressure/inflation controller **on the same PCB** as this control
> board. The 26 parts below remain correct **for the radio/power half**; they are no longer the whole
> board. Combined totals are in §7.

**Measured on:** `tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb`
**Status:** BOM record only. No board re-fabricated, nothing purchased, nothing powered up.

---

## The change in one line

**44 footprints → 26 fitted parts.** 18 parts are retired from the analogue RF chain; one purchased
433 MHz SPI receiver module is added off-board.

| | before | after |
|---|---|---|
| Footprints on board | 44 | **26** |
| 433 MHz BPF | 2 (`FLT_433_A/B` — generic placeholders, never selected) | **0** (module has its own front end) |
| Log detector | 1 (`U_DET`, AD8318) | **0** |
| VGA | 1 (`U_VGA`, ADL5240) | **0** |
| Bias tees | 2 (`TEE1`, `TEE2`) | **0** |
| Load switch | 1 (`Q_LNA_SW`) | **0** |
| Receiver | — | **1 purchased module (off-board)** |

---

## Retired — 18 parts

Every one of these is verified present on the current board, so the retirement list is measured, not
assumed:

| ref | part | why it goes |
|---|---|---|
| `FLT_433_A`, `FLT_433_B` | 433 MHz BPF — **generic package placeholders**, never a selected device | module front end replaces both; these were the only genuinely self-designed RF parts |
| `U_DET` | AD8318 log detector | 75 dB sensitivity shortfall vs a demodulating receiver; cannot serve as a link receiver |
| `U_VGA` | ADL5240 VGA | existed to drive the AGC loop around the detector; the loop is dropped (ADR-149 D4) |
| `TEE1`, `TEE2` | ZFBT-4R2GW+ bias tees | DC-over-coax masthead feed retired with the detector chain |
| `Q_LNA_SW` | load switch / resettable limiter | protected the masthead LNA branch, which is now an inline module |
| `C_DET1`, `C_DET2` | 100 nF detector output filter | belong to `U_DET` |
| `C_VGA1`, `C_VGA2` | 100 nF / 1 µF VGA decoupling | belong to `U_VGA` |
| `C_LNA1`, `C_LNA2` | bias-tee DC injection bypass | belong to `TEE1`/`TEE2` |
| `C_TAP` | directional/coupled tap (was `TODO(unverified)`) | tap existed only to feed the detector |
| `FB_DET`, `FB_VGA` | ferrite beads for the detector/VGA rails | those rails no longer exist |
| `R_LNA_ILIM` | LNA branch current limit | belongs to `Q_LNA_SW` |
| `J_LNA_FEED` | coax feed to the masthead LNA | masthead LNA concept retired; inline LNA replaces it |

**Verify the count:**

```bash
cd tracker/hardware/base_station
/usr/bin/python3 - <<'PY'
import pcbnew
b = pcbnew.LoadBoard('base_station_v1_placed_v2.kicad_pcb')
rf = {'FLT_433_A','FLT_433_B','Q_LNA_SW','TEE1','TEE2','U_DET','U_VGA',
      'C_DET1','C_DET2','C_VGA1','C_VGA2','FB_DET','FB_VGA','R_LNA_ILIM',
      'C_LNA1','C_LNA2','C_TAP','J_LNA_FEED'}
allrefs = {f.GetReference() for f in b.GetFootprints()}
print('total', len(allrefs), '| retiring', len(rf & allrefs), '| keeping', len(allrefs - rf))
print('retiring not found on board:', sorted(rf - allrefs))
PY
```

Expected: `total 44 | retiring 18 | keeping 26` and an empty "not found" list.

---

## Kept — 26 parts

| block | refs |
|---|---|
| MCU core | `U_MCU` (RP2040), `U_FLASH`, `Y1`, `C_X1`, `C_X2`, `R_RUN` |
| Power tree | `U_REG` (buck), `L1`, `R_FB1`, `R_FB2`, `R_EN`, `C_IN`, `C_OUT`, `U_LDO`, `C_LDO1`, `C_LDO2` |
| MCU decoupling | `C_MCU1`, `C_MCU2` |
| Protection | `D_REV`, `D_TVS` |
| Connectors | `J_PWR` (9–18 V in), `J_SWD`, `J_433_RX` (SMA, now the module's antenna port), `J_2450_TX` (2.45 GHz TX, separate band, untouched) |
| Test | `TP_5V`, `TP_GND` |

**`J_2450_TX` is deliberately kept.** It is a different band and a different function; ADR-149 is
scoped to the 433 MHz receive front end only.

---

## Added — purchased module (off-board)

| item | part | interface | indicative price | state |
|---|---|---|---|---|
| 433 MHz receiver | **Adafruit RFM96W breakout** — SX1276, 433 MHz | **SPI**, 3.3 V logic | ~$19.95 | **not purchased** |
| *(optional)* preselector | GPIO Labs 433 MHz BPF, 5 MHz BW, SMA-F | inline SMA | ~$29.10 | not purchased |
| *(optional)* inline LNA | GPIO Labs 433 MHz filtered LNA, 20 dB, SMA-F | inline SMA | ~$54.00 | not purchased |

### Why the receiver needs no detector at all

| device | sensitivity |
|---|---|
| AD8318 (retired) | ~−55 to −65 dBm usable |
| SX1276 (chosen) | **−137 dBm** demodulating (SF12) |

The module returns **packets + RSSI + SNR**, so it provides link telemetry as a by-product of
receiving. The detector's only function was measuring level, which is now derived per packet.

### Optional parts — and the ordering constraint

Both optional parts are inline SMA and sit **before** the module.

**The LNA must come after the filter, not before it.** Its maximum input is around **−10 to −15 dBm**;
a nearby transmitter reaching it unfiltered will saturate it. Filter first, then LNA, then module.

---

## Open item — RESOLVED 2026-11-11

~~**The RFM96W breakout is 3.3 V logic only.**~~ **That was wrong.**

Measured from Adafruit's own product page (`adafruit.com/product/3073`):

> *"Each radio comes with some header, a **3.3V voltage regulator and levelshifter** that can handle
> **3-5V DC power and logic** so you can use it with 3V or 5V devices."*

The breakout is **3–5 V tolerant on both supply and logic**. It runs from the board's 5 V rail and talks
SPI to the RP2040 with **no interface circuitry** — and **no level translator is added to the BOM**.

The error was generalising from the bare RFM96/SX1276 *chip* (3.3 V only) to the Adafruit *breakout*,
which adds the regulator and shifter. The chip-level statement is true; applying it to the breakout was not.

---

## What this does NOT do

- No order is placed and no board is re-fabricated.
- The board file still contains the 26 + 18 parts as-is; re-laying out without the RF chain is a
  separate piece of work.
- `J_433_RX` currently expects an antenna; with a module it becomes the module's antenna feed. That
  re-wiring is schematic work, not yet done.
- Nothing here is qualified. No measurement of a purchased module exists.

---

## §7 — Combined board (ADR-150)

The inflator joins this board. This section is the BOM consequence; the decision and its risks are in
[ADR-150](../../../docs/adr/150-inflator-and-radio-on-one-board.md).

| | footprints | body area |
|---|---|---|
| Radio/power half (this document, post-ADR-149) | **26** | 562 mm² |
| Pressure/inflation half (`compact.kicad_pcb`) | **26** | 2407 mm² |
| **Combined** | **52** | **2970 mm²** |

At the ~60 % packing the compact pressure board achieved, 2970 mm² of body implies roughly
**5000 mm² of board — about 70 × 70 mm**. That is an area estimate from body bounding boxes, **not a
placement**, and it will move once real placement runs.

**The pressure half dominates (81 % of area)** because it carries two MS5611 breakouts, USB-C, the
buck, and the pneumatic port keep-outs.

### What the combination costs in the BOM

| item | consequence |
|---|---|
| MCUs | **two, not one** — RP2040 (radio/host) and ESP32-S3 (pressure/inflation). ADR-150 D2. |
| Power tree | one input rail feeds both; pump inrush sizing and bulk capacitance are now board-wide, not local |
| Debug access | both `J_SWD` (RP2040) and USB (ESP32-S3) must remain reachable after assembly |
| Interlock | stays entirely inside the ESP32-S3; the inter-MCU link is **telemetry only** (ADR-150 D3) |
| Pneumatics | the pressure half's sealed-tap port keep-outs now share a board with the radio and its 2.4 GHz antenna keep-out |

### Still open before a combined BOM can be finalised

1. ~~**The 3.3 V / 5 V reconciliation for the RF module.**~~ **RESOLVED** — the Adafruit breakout has
   its own 3.3 V regulator and level shifter and is 3–5 V tolerant. No translator in the BOM.
2. ~~**Pump current and inrush** — not specified anywhere in the repo.~~ **RESOLVED as a decision by
   [ADR-151](../../../docs/adr/151-pump-rail-and-actuation-power.md):** the pump rail is fed from
   `VIN_GS` upstream of the 5 V buck and sized to an explicit **2.0 A continuous / 5.0 A inrush (10 ms)**
   envelope with ≥220 µF bulk. No pump is selected — the envelope sits above the plausible pump range so
   the rail is not the binding constraint; if the real pump exceeds it, the ADR is superseded and re-sized.
3. **Which pneumatic interface** the combined board presents.
4. **Whether both functions ship in one enclosure** — decides connector placement.
