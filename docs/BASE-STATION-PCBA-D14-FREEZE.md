# Base-station PCBA v1 — D14 part and bias/rail freeze

> **STATUS: DESIGN FREEZE NOTE — not a KiCad layout and not an operator purchasing authorization.**

Date: 2026-10-09  
Scope: base-station control/bias/telemetry PCBA v1, gap-analysis D14  
Related decisions: [ADR-084](adr/084-ground-station-automatic-level-control.md), [ADR-079](adr/079-amplifier-led-receive-chain-owned-tqp3m9037-lna.md), [ADR-072](adr/072-band-split-duplex-two-antennas-no-circulator.md)

## CORRECTION — fixed-voltage part identity (ADR-086, proposed follow-up)

The TPS62162-as-5-V statements and 15 mA detector allowance below are preserved
as historical freeze text, not valid electrical specifications.
[ADR-086](adr/086-base-station-fixed-5v-correction.md) selects TPS62163DSGR fixed
5 V in the logical source and records the corrected 465.625 mA conditional budget.
The 18 V input corner and full rail qualification remain unsupported; this does
not waive the frozen system requirement or authorize layout/purchase.

## Decision

The board-own parts and network below are frozen for schematic capture. Every selected active part has a manufacturer datasheet URL. The board implements the 433 MHz receive AGC and telemetry controller; it does not add a 2.4 GHz PA, and it does not attempt to put the masthead LNA on the PCBA.

| Checklist row | Frozen selection | Status / rationale | Datasheet |
|---:|---|---|---|
| 7 | Analog Devices **AD8318ACPZ-R7** log detector | TO-BUY; 1 MHz–8 GHz log detector, used only on the filtered 433 MHz coupler tap | https://www.analog.com/media/en/technical-documentation/data-sheets/AD8318.pdf |
| 8 | Raspberry Pi **RP2040** (QFN-56) + external decoupling | TO-BUY; MCU, SPI control, ADC input, watchdog and telemetry in one board-owned device. ADC input is used for the detector voltage; no separate ADC is fitted. | https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf |
| 11 | **DNP / no PA or FEM** | CLOSED BY D9/ADR-072: ISM uplink is attenuation-only. Reserve no powered PA footprint in v1; a higher-legal-footing PA is a future respin, not an open v1 BOM row. | N/A — no part selected by design |
| 14 | Mini-Circuits **ZFBT-4R2GW+** bias tee for the masthead ZX60-P103LN+ feed; TI **TPS62162** 5 V buck regulator; local 5 V load switches and decoupling | TO-BUY. The bias tee is at the masthead/feed boundary, not in series with the 433 PCBA receive path. The board provides protected 5 V and switched LNA bias. | https://www.minicircuits.com/WebStore/dashboard.html?model=ZFBT-4R2GW%2B ; https://www.ti.com/lit/ds/symlink/tps62162.pdf |
| 18 | **DNP on PCBA; external weatherproof enclosure and mast clamp** | CLOSED AS MECHANICAL OUT-OF-SCOPE. No enclosure footprint or mechanical BOM is frozen on this electronics board; mechanical selection remains under ADR-076/077/078. | N/A — no PCBA part |

## Frozen network

### 5 V rail and current budget

`VIN_GS (9–18 V nominal, protected)` → reverse-polarity/TVS protection → **TPS62162** buck, configured for **5.00 V** → `+5V_PCBA`.

The TPS62162 is rated for a 3–17 V input and 1 A output; the 18 V upper system input is therefore a system-level limit for this regulator selection and must be enforced by the upstream protection/entry specification. If the actual source can exceed 17 V, use the same footprint only after replacing the regulator with a rated variant.

| Load | Budget |
|---|---:|
| ADL5240 VGA, row 5 | 93 mA @ 4.75–5.25 V (ADR-084/checklist) |
| ZX60-P103LN+ bias, masthead feed | 95 mA @ 5 V (ADR-079/checklist) |
| AD8318 detector | 15 mA design allowance (datasheet operating-current limit to be checked during schematic review) |
| RP2040, digital + ADC + SPI | 50 mA design allowance |
| 25% transient / regulator margin | 63 mA |
| **Design total** | **316 mA** |

The 5 V converter and PCB copper are consequently budgeted for **at least 0.5 A continuous and 1 A peak**. The LNA bias branch is separately switchable so an LNA fault cannot collapse the MCU rail.

### LNA bias tee

The masthead chain is:

`433 antenna → 433 MHz BPF → ZFBT-4R2GW+ RF/DC port → ZX60-P103LN+ → feed coax → ZFBT-4R2GW+ RF/DC port → ADL5240/VGA path`.

Use the bias tee DC port to source **+5V_LNA_SW** through a resettable current limiter or load switch. Place a 100 nF + 10 µF local bypass at the tee/DC injection point. The RF path remains 50 Ω and the tee is not used as a 2.4 GHz duplexer; ADR-072 still requires separate 433 RX and 2.45 GHz TX antennas and a 433 BPF ahead of the LNA.

### ADL5240 VGA rail

`+5V_PCBA` feeds the ADL5240 through a ferrite bead or π filter, with 100 nF and 1 µF at the IC. The ADL5240 supply window is **4.75–5.25 V** and its budget is **93 mA**. Do not feed it from the switched masthead LNA branch. Its serial/parallel gain control is owned by the RP2040; the default firmware gain is the known manual/commanded setting from ADR-084.

### Detector tap

A directional/coupled tap after the 433 BPF/LNA feeds a **second 433 MHz BPF** before AD8318 input. This is mandatory: AD8318 is broadband and unfiltered 2.45 GHz leakage could falsely reduce RX gain. The detector output goes to RP2040 ADC; detector ground and the ADC reference return to the quiet analog ground region.

## Watchdog, bounds, and bypass

The RP2040 AGC state machine is bounded to the ADL5240's legal gain-control range and has a deadband of at least one 0.5 dB step plus hysteresis. It uses fast attack and slow decay as specified in ADR-084. A downlink-failure watchdog is independent of the TX attenuation LUT: if detector/packet telemetry indicates loss or the controller stops servicing the watchdog, hardware/firmware returns the ADL5240 to a known fixed manual gain and reports the fault. A front-panel or commanded **MANUAL/BYPASS** path selects that fixed gain without relying on the last AGC register state. TX range→attenuation remains operational even if RX AGC is bypassed or faulted.

## Verification gates before layout release

1. Confirm the exact ZFBT-4R2GW+ insertion loss/current rating from the delivered unit or current manufacturer datasheet; do not substitute a circulator.
2. Measure the 433 BPF and detector-tap BPF: pass 433.92 MHz with the planned insertion-loss budget and reject 2.45 GHz sufficiently for the AGC false-level test.
3. Confirm the ZX60-P103LN+ lower band edge (ADR-079 open contradiction) with a 400–500 MHz S21 sweep before masthead assembly.
4. Schematic ERC must show separate `+5V_LNA_SW`, `+5V_VGA`, `+5V_DET`, and `+3V3_MCU` domains; no single LNA fault may remove MCU power.

This note freezes the selection and intended network; it does not claim those bench gates have already passed.
