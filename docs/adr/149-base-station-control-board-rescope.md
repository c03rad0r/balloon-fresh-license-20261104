# ADR-149 — base station becomes a control board; the analogue RF chain is bought, not built

- **Status:** **Accepted by operator** (2026-11-11) — the operator directed *"Yes please write the
  superseding record and re-scope. Yes please make it a control board and please update the bill of
  materials accordingly."*
- **Date:** 2026-11-11
- **Supersedes (in part):** the analogue-RF-chain design basis carried by ADR-072 (band-split duplex),
  ADR-073 (FLRC-max downlink), ADR-079 (owned TQP3M9037 LNA), and ADR-084 (AGC loop) **as they apply
  to the base station's receive front end**. Those records remain authoritative for the *radio
  system*; this ADR changes only *how the ground end is realised*.
- **Related:** ADR-034 (band split), ADR-087 (per-sensor calibration, unrelated but same discipline),
  ADR-145/146/148 (v11), `tracker/hardware/base_station/spec.json`,
  `tracker/hardware/base_station/READINESS-MEASUREMENTS.md`.
- **New BOM:** `docs/fab/base_station/BOM-RESCOPE.md`

---

## Context — why this is a superseding record and not a tuning exercise

The base station was designed as a **discrete analogue RF instrument**: two 433 MHz bandpass filters
(`FLT_433_A`, `FLT_433_B`), a masthead LNA fed by two bias tees, a load switch, a directional tap,
an ADL5240 VGA driven by three gain lines, and an AD8318 log detector on its output.

Two independent problems make that the wrong architecture.

### 1. A sensitivity wall, not a price trade-off

The chain's job was to measure received signal strength. Measured requirement versus device physics:

| device | sensitivity | basis |
|---|---|---|
| AD8318 log detector | roughly **−55 to −65 dBm** usable | detector dynamic range, part datasheet |
| SX1276 LoRa receiver (SF12) | **−137 dBm** demodulating | module datasheet |

The gap is about **75 dB — a factor of 30 million in power**. A power detector cannot register a
signal that a LoRa receiver decodes comfortably. With ADR-009's link budget targeting ~300 km, the
detector-based chain **cannot serve as a link receiver at any price**. It is only meaningful as a
short-range proximity meter.

This is a hard physical limit, so no amount of careful layout, better filters or a lower-noise LNA
recovers it.

### 2. The RF work was ours, and only ours

Measured on the board: `FLT_433_A` and `FLT_433_B` are **generic package placeholders, not selected
devices** (`READINESS-MEASUREMENTS.md` records this explicitly). Those were the two places where the
project would have been designing filters from scratch. Everything else in the chain is an IC or a
catalog part — but the whole chain still has to be *laid out as RF copper*, which is the expensive,
error-prone part.

### 3. The operator's standing preference

*"I want to buy the RF parts as modules that connect via SMA so that we don't need to do any RF
engineering."* — recorded 2026-11-11.

---

## Decision

**D1 — The base station is a CONTROL BOARD.** It keeps the digital core, the power tree, the
connectors and the firmware. It is no longer an RF instrument.

**D2 — The 433 MHz receive front end is a purchased SPI module.** An SX1276-class 433 MHz breakout
(Adafruit RFM96W or equivalent) delivers packets **plus RSSI plus SNR**, connected by SPI. This
replaces the entire analogue chain and, critically, actually demodulates — which the detector never
could.

**D3 — Every part of the RF path becomes an SMA-connected module.** No RF copper is laid out on this
board. Any filtering or gain added later is an inline SMA part, not a PCB feature.

**D4 — The AGC loop as designed is dropped, not deferred.** The ADL5240 + AD8318 loop existed to
automate gain on the detector chain. With the detector gone there is nothing to control. ADR-084
already recorded that the AGC loop was an *enhancement* and that manual/commanded gain was the
baseline; this ADR removes the enhancement because its sensor no longer exists. The SX1276's own RSSI
and SNR telemetry supersede it.

**D5 — Purchased modules carry their own risk statement.** Buying removes RF *layout* risk. It does
not remove integration risk: logic levels, supply sequencing, current budget, and connector torque.
Those are now the base station's real engineering content.

**D6 — Nothing about this ADR claims qualification.** No board is re-fabricated, nothing is powered
up, and no module has been bought, mounted or measured.

---

## What the operator specifically accepted

1. The sensitivity wall (D2's justification) — the detector chain is retired rather than built.
2. The re-scope from RF instrument to control board (D1).
3. The BOM consequence recorded in `docs/fab/base_station/BOM-RESCOPE.md`.

---

## Consequences

### Positive

- **RF layout risk on this board goes to zero.** No controlled-impedance traces, no filter
  compensation, no gain-stage stability work.
- **The board gets simpler.** The RF chain contributes ~18 of 44 footprints and a large majority of
  the signal-integrity concerns.
- **The receiver works at the ranges the project targets**, which the detector chain could not.
- **Board dimensions can shrink** once the RF area is released — the current 60 × 45 mm was sized
  with the RF chain present.

### Negative / accepted costs

- **The RSSI is coarser and packet-free no longer.** The detector gave a continuous analogue level;
  the SX1276 gives RSSI/SNR per packet. For link characterisation that is a different, and in some
  ways better, measurement — but it is not continuous.
- **Sensitivity now depends on a module's own RF design**, which the project does not control.
- **The masthead-LNA concept changes.** With no bias tee, an inline LNA must be powered locally; the
  existing `J_LNA_FEED`/`TEE1`/`TEE2` DC-over-coax arrangement is retired.
- **Some earlier evidence no longer applies.** Any measurement or analysis whose subject was the
  detector chain (`U_DET`, `U_VGA`) describes hardware that will not exist. Those documents are
  superseded for the base station, not deleted.

### Neutral

- The 2.45 GHz TX port (`J_2450_TX`, no PA on the PCBA) is **untouched** by this ADR — it is a
  separate band and a separate function.

---

## What this ADR does NOT do

- It does not change the balloon/flight board, the hub, the wing, or the pressure controller.
- It does not amend ADR-072/073 for the *radio system* — those still govern what is transmitted.
- It does not authorise a fabrication order.
- It does not choose the final module. A shortlist with measured requirements is in the BOM record;
  the selection needs the operator's confirmation on one open question (below).

---

## Open question that blocks the final BOM

**The SX1276 breakout is 3.3 V logic only.** The `RP2040` is 3.3 V, so the SPI interface is
compatible — but the board's 5 V rail and the module's `VIN` tolerance must be reconciled explicitly.
Feeding 5 V to a 3.3 V-only breakout destroys it. This must be settled in the schematic, not assumed.

---

## Reproduce the part classification

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

`pcbnew` lives in the distro python (`/usr/bin/python3`), not the project venv.
