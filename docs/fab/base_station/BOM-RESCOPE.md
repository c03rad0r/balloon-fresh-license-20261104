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

---

## Part 2 — inflation domain parts, with verified numbers (2026-11-11)

The section above sizes the combined board. This one names the parts that did **not** exist in the
repo's BOM before, and marks exactly how far each is verified. **Not a shopping list:** ADR-088 keeps
pump actuation disabled and leaves ΔP targets UNKNOWN, so these define what the board must be able to
drive, not permission to inflate.

### Sensors — verified

| item | part | spec | price | source |
|---|---|---|---|---|
| ΔP sensor, internal tap | **MS5611-01BA03** (`MS561101BA03-50`) | 10–1200 mbar, 24-bit ΔΣ, I²C+SPI, **1.8–3.6 V**, QFN 5.0×3.0×1.0 mm | **$11.56–12.25** | DigiKey, **16,892 in stock** |
| ΔP sensor, ambient | same part, **other I²C address** | CSB sets the address LSB, so two sensors share one bus with no mux | same | same |

Chosen because ADR-088 §2 mandates two MS5611 with pair-specific calibration, and because the existing
`tools/balloon_pressure_test` firmware already speaks this part (PROM/CRC verified) — no second driver.

> **Calibration does not transfer.** Same part number ≠ calibrated pair. Offset must be determined at
> equal pressure and validated against an independent manometer (ADR-088 §2).

### Fill valve — CANDIDATE ONLY, three things unverified

| item | candidate | spec | price | state |
|---|---|---|---|---|
| fill valve | **SMC VQZ1121** series (e.g. `VQZ1121-5L1-M5`) | 4/5-port, 2-position single solenoid, 0.35 W, ≤17–25 ms response, 0.1–0.7 MPa, fluid: air/inert gas | **$44.28–58.87** | **candidate** |

1. **Coil voltage is 24 VDC in every listing found.** A 12 V variant exists in the series but the
   suffix must be confirmed against SMC's ordering guide — do not assume the rail fits.
2. **"Normally closed" is not stated.** 2-position single-solenoid *usually* means spring-return,
   which is **not proof**. ADR-150 S1 requires it proven: a valve that fails open is a safety
   defect, not a part substitution.
3. **Helium behaviour is unquantified.** Response time above is specified for **air**. A 0.35 W spool
   valve may be the wrong device for filling a Mylar envelope at a controlled rate.

A small direct-acting 3.3–12 V DC valve would likely suit a pico-balloon better. **That is now
measured, not guessed** — see [`docs/analysis/fill-valve-selection.md`](../../analysis/fill-valve-selection.md)
and its model `valve_fill_flow_model.py`:

| envelope | volume | 120 s fill needs | vs VQZ1121 (~380 L/min air, ESTIMATE) |
|---|---:|---:|---|
| 18" DecoGlee Mylar | 15 L [CITED] | **7.50 L/min** | **51x oversized** |
| 36" latex | 400 L [sphere bound] | 200 L/min | adequate |
| 60" Cymylar | 1853 L [sphere bound] | **927 L/min** | **cannot pass it** |

**The envelope is the decision variable, not the valve.** The same part is grossly oversized for a
pico balloon and inadequate for a 60" — a 123x spread. A grossly oversized valve also makes
controlled ramp harder, which matters because ADR-088's control variable is circumference held by a
tape measure: a valve that fills 15 L in seconds removes the operator's ability to stop in time.

**Second reason to prefer direct-acting:** with no pilot pressure, de-energising removes the only
opening force, so S1's "de-energises closed" is physically easier to **prove** than on a
pilot-operated spool valve, where it is merely usually true.

### Driver stage — deliberately unsized

| block | implementation | why |
|---|---|---|
| low-side switch | logic-level N-channel MOSFET, gate **pulled low** | de-energised = closed = safe (ADR-150 S1) |
| freewheel | diode across the coil | no recirculation path destroys the MOSFET — TI/Nexperia treat as mandatory (S4) |
| pump interlock | pump relay de-energised-off from the same fault line, or valve in series with pump | ADR-150 S2 |
| alarm | separate **latched** output, asserted ON for fault, boot self-test | ADR-150 S3 |
| gate network | 1 kΩ series + 10 kΩ pulldown | a floating gate during MCU reset is a valve that might open |

**No MOSFET or diode part numbers are given.** They follow from coil current and clamp energy, which
follow from the valve. Sizing against a guessed valve is how a driver ends up under-rated.

### Pump — dual-direction required, flow is not the constraint

Measured in [`docs/analysis/pump-selection.md`](../../analysis/pump-selection.md)
(model `pump_sizing_model.py`). **The pump never touches helium** — the protocol is
`[Pump] → [Balloon]` for air pre-stretch and vacuum deflate, then a separate He 4.6 refill from a
cylinder through a regulator. So helium compatibility is a *regulator* requirement, not a pump one.

| criterion | decides? | evidence |
|---|---|---|
| **pressure AND vacuum** | **YES** | protocol C.4 steps 2 and 4; BD-03A is pressure-only, BD-03V is vacuum-only — each fails one step |
| flow ≥ ~3 L/min | as a floor | 0.8–2.2 L/min pumps need 2–6 h to pre-stretch a 32" |
| brushless / duty | YES | brushes ~1000 h; holds run 12–48 h and repeat |
| PWM | YES | 5 L/min at full speed overshoots a fine circumference adjustment |
| helium compatibility | **NO** | pump never sees He |

| candidate | flow | pressure | vacuum | power | state |
|---|---:|---:|---:|---:|---|
| **JSG OD-05TVB-S.1** | 5.5 L/min | 1.0–1.5 bar | −70 kPa | 4 W | **preferred** |
| Boxer 5KS | 5.1 L/min | 0.30 bar | 50 kPa | 1.5–4 W | premium low-noise, thin pressure head |
| BD-04AB-11L | 11 L/min | 2.5 bar | 75 kPa | 7 W | if envelope moves to 60" |
| BD-03A-3L | 3 L/min | 2 bar | **0 kPa** | 5 W | **rejected** — cannot deflate |

**Hold:** with the pump OFF for 12–48 h, an *acceptable* 2 mbar/h leak loses 6.7 L (12 h) to 26.6 L
(48 h) on a 281 L envelope. The **valve** holds that, not the pump — which is why S1's
normally-closed proof carries the safety weight.

### Connectors the inflation half adds

| connector | purpose |
|---|---|
| fill line | valve outlet to balloon neck — barb or threaded |
| ambient pressure tap | MS5611 #2, open to atmosphere and **screened from propwash** |
| internal pressure tap | MS5611 #1, envelope side of the fill path |
| pump power | switched + unswitched, strain-relieved |
| alarm | latched, audible/visible |

### Part-count honesty

The RF retirement saved 18 parts; the inflation half spends all of it. The combined board lands near
its **original 44 footprints**, not below. Stated plainly so nobody budgets for a small board.

### Layout constraint

Valve and pump copper must not sit near the RF module, and the 2.4 GHz antenna keep-out (ADR-150 D5)
must stay clear of the pneumatic connectors. A switching solenoid beside a −137 dBm receiver is an
own-goal, and pump inrush browning out the radio rail is the residual ADR-147 concern (ADR-150 D4).
