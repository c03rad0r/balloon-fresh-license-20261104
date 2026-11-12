# ADR-086 — Base-station fixed 5 V source correction

Status: Proposed — bounded implementation authorized by operator; review/merge pending.

## Decision

Correct the D14 freeze's **part identity**, not its RF voltage intent: use
TPS62163DSGR (fixed 5 V), not TPS62162 (fixed 3.3 V). This explicitly supersedes
the TPS62162-as-5-V statements in `docs/BASE-STATION-PCBA-D14-FREEZE.md` and its
historical transcription `tracker/hardware/base_station/spec.json`.

The implementation is limited to the legacy logical generator/netlist: EN to
protected VIN, FB to AGND, PG through 100 kΩ to the MCU 3.3 V domain, and selected
input/output filter parts. Remove the obsolete divider and output-powered EN
pull-up. Preserve RP2040 3.3 V I/O and 1.1 V core domains. No PCB changes/routing.

## Evidence and alternatives

[Source proof, load calculation, tests and unsupported corners](../analysis/base-station-bringup/5v-supply.md).
TI SLVSAM2E §5 and §6 prove voltage and identical DSG pins. ADL5240 requires
4.75–5.25 V; keeping a 3.3 V converter and renaming the rail is rejected.
An adjustable converter/divider adds unnecessary parts; a wider-input redesign
is deferred rather than misrepresented as a pin-compatible correction.

The 9–18 V system requirement is **not waived**: >17 V at the converter remains
unsupported and release-blocking. Passive DC-bias/thermal/transient qualification,
RF supply accuracy, LDO startup, fault isolation and ERC remain open. Proposed
component selections are not a production BOM approval.

A read-only pre-decision consultant supported the correction but highlighted
input, PG threshold, voltage accuracy and load-budget limitations; all are recorded.
The delegation service reports `tier/delegation`, not a served family identifier:
this is **not claimed as cross-family review**. Independent parent review required.

## MCU branch follow-up decision (proposed, bounded implementation)

Select AP2112K-3.3TRG1 SOT25, EN tied to +5V_PCBA, pin4 NC, with
input/output capacitance and per-power-pin RP2040 bypass. The intended MCU
allowance is 50 mA, not the ESP32 pressure-controller load. This supersedes
the unspecified-LDO/startup/decoupling implementation gap above, not the
18 V requirement or thermal/analog qualification blockers. No PCB change.
[Exact source citations, alternatives, thermal sensitivities and RED/GREEN
netlist evidence](../analysis/base-station-bringup/mcu-supply.md).
Capacitor MPN/bias selection and actual firmware/flash current are not closed.
This is a proposed topology milestone pending review, not fab authorization.

## For future sessions

Read the linked report; do not route or release this netlist. The native base PCB
is still rejected and intentionally not synchronized. A landed ADR and an
ERC-clean authoritative schematic must precede board regeneration.
