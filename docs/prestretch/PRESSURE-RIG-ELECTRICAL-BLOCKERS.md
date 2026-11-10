# Pressure rig: electrical quarantine and remaining blockers

Inspected master `2449ad8a`, feature commit `053daa966af2353ed0b35726104a94538350359a`,
and merged PR #521 (`5472f614`). PR #521 changed only RIG-ELECTRONICS-SPEC.md;
it did NOT deliver a schematic. Master contains neither the feature generator nor
its PCB. No existing sound replacement schematic was found. Consequently this is
containment of an unsafe unmerged scaffold, **not a validated electrical replacement**.
The old entrypoint now exits 2 without producing geometry. Do not cherry-pick the
old board/spec into an order. The feature branch is left intact for provenance.

## Observed defects in 053daa96 (not merely unrouted nets)

- U1 invents seven pads and uses GPIO labels as module pad numbers; even supply
  assignments are not a proven module pin map. Missing module pads cannot be repaired
  by routing. Full manufacturer land pattern and package-pin mapping are required.
- U2 BMP280 has only four invented pads, not the eight-terminal package including
  supply/interface-selection pins. Current specification instead requests two MS5611.
- Q1 IRLML6344 assigns pin 2 to PUMP_SW and pin 3 to GND; source/drain mapping must be
  checked against the exact ordered package. D1 assigns pad 1 to switched return and
  pad 2 to positive load rail: verify cathode to positive rail, anode to switched return
  against the chosen diode datasheet and actual KiCad pad convention before any reuse.
- TPS7A0233 is a 200 mA-class choice, below the current specification's >=500 mA logic
  supply requirement. Package suffix, peak current, dropout, thermal dissipation,
  stability capacitors and pump-induced transients remain unvalidated.
- D2 BAT54 bridges 12 V and USB 5 V without a justified power-path design and uses an
  unverified package. Remove this architecture from the new design unless a reviewed
  source-isolation circuit demonstrates no backfeed/overvoltage in every power state.
- USB-C is a fabricated six-pad approximation, not a connector footprint. Real connector
  selection, CC resistors, duplicate contacts, shielding, protection and mounting remain.
- Gate default-OFF resistor, EN/boot biasing, decoupling, sensor pullups and alarm circuit
  must exist in the actual schematic; prose cannot substitute for components.

## Required source basis before layout resumes

Use complete pinned KiCad library footprints, not hand-generated rectangles. Record
manufacturer datasheet revision and package for every ordered MPN, then independently
check symbol pin -> footprint pad -> net. Include all power, ground and exposed pads.
Regression tests must reject GPIO-as-package-pad mapping, missing pins and reversed
motor suppression. No new footprints or pin mappings are claimed validated by this PR.

Sources to pin and read for the replacement: Espressif ESP32-S3-WROOM-1/-1U datasheet
and hardware design guidelines; Bosch BMP280 datasheet if retained; TE MS5611-01BA03
interface/pin tables for the differential pair; manufacturer datasheets for the exact
MOSFET, diode, regulator and USB connector. In particular recheck the specification's
MS5611 CSB address polarity rather than copying its assertion.

## Safety hold (overrides conflicting older prose)

Natural leakage is NOT guaranteed overpressure protection. Pump OFF prevents further
powered filling but does not relieve trapped pressure or protect against a failed-short
FET. A GPIO pull-down does not defeat an actively HIGH output during a hung task.
Require pump default OFF through boot/reset/brownout and fault shutdown for stale/invalid
sensors, timeout and manual abort; define and verify watchdog/independent shutdown and
latched alarm/self-test. Motor inductive suppression remains necessary without a solenoid.
The existing PRESTRETCH-OVERPRESSURE-INTERLOCK design is still DESIGN + STUB, not
hardware safety evidence. Reconcile its valve/relief assumptions with the pump-only
proposal before approving operation; this PR neither adds a valve requirement nor
certifies its removal safe.

Protocol B.2's 1.05 bar remains unresolved: absolute versus gauge MUST be clarified;
no target, purchase or inflation follows from it. A 100 kPa pump does not cover a
105 kPa gauge requirement by arithmetic alone. Circumference remains the protocol's
primary control variable. No physical actuation was performed or authorized here.

## Scope preserved / verification

ESP32-S3, JLC assembly, an external chassis pump and combined shipment of separate
boards remain the plan. V10 order untouched. No purchasing, flashing or board access.

Regression: `python3 tools/balloon_pressure_test/test/test_scaffold_quarantine.py`.
Observed RED: missing quarantine entrypoint. GREEN requires exit 2, explicit quarantine
message and absence of the old generated PCB. This proves containment only, not ERC,
DRC, pin correctness, fault shutdown or manufacturability. Remaining release blockers:
all electrical items above, reviewed schematic/ERC, BOM/MPN/stock checks, complete real
footprints, layout/DRC, S3 firmware integration, and verified hardware safety behavior.
