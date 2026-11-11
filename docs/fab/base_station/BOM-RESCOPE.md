# Base station BOM — post-ADR-149 (control board)

**Scope:** this record implements [ADR-149](../../../docs/adr/149-base-station-control-board-rescope.md).
The base station stops being an analogue RF instrument and becomes a **control board**; the 433 MHz
receive front end is a purchased SPI module.

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

## Open item that blocks the final BOM

**The RFM96W breakout is 3.3 V logic only.** The RP2040 is 3.3 V, so SPI is compatible — but the
board's 5 V rail and the module's `VIN` tolerance must be reconciled **explicitly in the schematic**.
Applying 5 V to a 3.3 V-only breakout destroys it. This ADR does not assume it away.

---

## What this does NOT do

- No order is placed and no board is re-fabricated.
- The board file still contains the 26 + 18 parts as-is; re-laying out without the RF chain is a
  separate piece of work.
- `J_433_RX` currently expects an antenna; with a module it becomes the module's antenna feed. That
  re-wiring is schematic work, not yet done.
- Nothing here is qualified. No measurement of a purchased module exists.

---

# Part 2 — inflation control, merged onto the same board (ADR-150)

**Scope:** implements [ADR-150](../../adr/150-merge-inflation-control-onto-base-station.md). This
reverses ADR-147's "separate boards" decision on the operator's instruction, and inherits **every**
safety requirement of ADR-088 unchanged.

**This section is not a shopping list.** ADR-088 is explicit that target/ramp/dwell/max ΔP are
**UNKNOWN per envelope** and that pump actuation is currently *disabled*. The parts below define what
the board must be able to drive; they do not authorise inflating anything.

## Added — inflation control domain

### Sensors — 2 × MS5611 (verified)

| item | part | spec | price | source |
|---|---|---|---|---|
| ΔP sensor, internal tap | **MS5611-01BA03** (`MS561101BA03-50`) | 10–1200 mbar, 24-bit, I²C+SPI, **1.8–3.6 V**, QFN 5.0×3.0×1.0 mm | **$11.56–12.25** | DigiKey, **16,892 in stock** |
| ΔP sensor, ambient | same part, **other I²C address** | CSB pin sets the address LSB — two sensors share one bus | same | same |

**Why this part and not BMP280:** ADR-088 §2 mandates two MS5611 with pair-specific offset
calibration. The part is also what the existing `tools/balloon_pressure_test` firmware already
speaks (ESP-IDF, PROM/CRC verified) — reusing it avoids a second driver.

**Calibration does not transfer.** Same part number ≠ calibrated pair. Two units must be offset-
calibrated at equal pressure and validated against an independent manometer (ADR-088 §2).

### Valve — normally-closed, 12 V DC (candidate, NOT verified for helium)

| item | candidate | spec | price | state |
|---|---|---|---|---|
| fill valve | **SMC VQZ1121** series (e.g. `VQZ1121-5L1-M5`) | 4/5-port, 2-position single solenoid, **0.35 W**, 24 VDC coil (12 V variants exist), **≤17–25 ms** response, 0.1–0.7 MPa, fluid: **air, inert gas** | **$44.28–58.87** | **candidate only** |

**THREE THINGS ARE UNVERIFIED AND MUST BE CHECKED BEFORE ANY ORDER:**

1. **Coil voltage.** The listings above are **24 VDC**. A 12 VDC variant exists in the series but the
   exact suffix must be confirmed against SMC's ordering guide — do not assume.
2. **"Normally closed" is not stated in these listings.** They are 2-position single-solenoid valves,
   which *usually* means spring-return, but ADR-088/D3 requires it **proven**, not inferred. A valve
   that fails open is a safety defect, not a part substitution.
3. **Helium compatibility.** "Air, inert gas" is stated; helium is an inert gas but leaks through
   small clearances faster than air, and the response time above is specified for air. A 0.35 W
   25 ms spool valve may be the wrong device for filling a Mylar envelope at controlled rate.

**Cheaper alternative not yet evaluated:** a small 3.3–12 V DC direct-acting solenoid valve with a
fraction of this flow would likely suit a pico-balloon better. It is left unevaluated rather than
guessed, because the flow and pressure range depend on the **UNKNOWN** ΔP targets of ADR-088.

### Driver stage — the safety-critical part

| block | implementation | why |
|---|---|---|
| low-side switch | N-channel MOSFET, logic-level, **pulled DOWN hard at the gate** | de-energised = closed = safe (ADR-150 D3) |
| freewheel | **diode across the coil** (Schottky or PN) | an inductive kick with no path destroys the MOSFET — TI/Nexperia both treat this as mandatory, not optional |
| pump interlock | pump relay de-energised-off from the **same fault line** as the valve, or valve in series with the pump | ADR-150 D4; the pump must not run with the valve closed unless plumbing forbids a path |
| alarm | separate **latched** output, asserted ON for fault | a dead alarm must not read as "healthy" — boot self-test required (ADR-150 D5) |
| gate resistor + pulldown | 1 kΩ series, 10 kΩ pulldown | prevents floating gate during MCU reset |

**No specific MOSFET/flyback part numbers are given here on purpose.** They follow from the valve
choice (coil current, clamp energy), which is unverified. Sizing them against a guessed valve is how
a driver ends up under-rated.

### Interlock MCU (ADR-150 D1/D3)

| item | part | why |
|---|---|---|
| interlock MCU | **ESP32-S3** module (same family as `tools/balloon_pressure_test`) | reuses the written interlock state machine + **33 host assertions**; independent of the RP2040 tracking domain |
| interlock SWD/access | own header | a hung telemetry MCU must not block reflashing the guard |

**The two MCUs must not share a bus, crystal or reset** (ADR-150 D2). They may share a ground plane
only if that common-mode path is written down as a known limitation.

## Kept from Part 1

Nothing from Part 1 is removed by this merge. The board now carries **both** domains:

| domain | parts |
|---|---|
| tracking (Part 1) | 26 kept parts + off-board RFM96W module |
| inflation (Part 2) | 2 × MS5611, valve, MOSFET + flyback + pulldowns, pump relay, alarm, ESP32-S3 + decoupling, plus connectors: fill line, ambient tap, internal tap |

**Rough part count: 26 + ~18–22 = ~44–48 parts** — i.e. the inflation half returns the board close
to the *original* 44-footprint size, because the RF chain's 18-part saving is spent on pneumatics.
This is stated plainly so nobody expects a small board.

## Connectors — physical access matters as much as copper

| connector | purpose |
|---|---|
| fill line | valve outlet to balloon neck; barb or threaded |
| ambient pressure tap | MS5611 #2, must stay open to atmosphere and be **screened** from propwash |
| internal pressure tap | MS5611 #1, to the envelope side of the fill path |
| pump power | switched + unswitched, strain-relieved |
| alarm | latched, audible/visible |

## Layout constraint (ADR-150 §4)

**Valve and pump copper does not go near the RF module.** A switching solenoid beside a −137 dBm
receiver is an own-goal; the two domains are separated on the board, not only in the schematic.

## Still open — blocks the final BOM

1. **Valve selection** — coil voltage, proven normally-closed, helium/flow suitability (above).
2. **ΔP targets remain UNKNOWN** (ADR-088 §3) — flow rating cannot be finalised without them.
3. **RFM96W is 3.3 V logic only** — 5 V rail must not reach it (carried from Part 1).
4. **Board outline** — no longer 60 × 45 mm; must be measured from the merged part list, not guessed.
5. **Hardware fail-safe direction is NOT verified.** Per `PRESTRETCH-OVERPRESSURE-INTERLOCK.md`, that
   *"needs the operator's hands"*: the valve must be proven to de-energise closed, and the pump proven
   to share the path.

