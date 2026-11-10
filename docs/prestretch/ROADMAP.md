# Pressure-rig roadmap

Updated 2026-11-10. Authority: [ADR-087](../adr/087-pressure-rig-differential-basis.md).
This is the current pressure-track roadmap; older work-split/schedule entries are historical where they conflict. No physical qualification has run.

## Settled design basis

- [x] Differential pressure: internal absolute minus ambient absolute, in Pa.
- [x] Two MS5611 sensors and ESP32-S3 retained; pair-specific calibration required.
- [x] Withdraw ambiguous 1.05 bar target and >=100 kPa pump recommendation.
- [x] Require independent passive relief plus verified pump-off protection.
- [x] Separate measurement/protection qualification from envelope testing.

These checks mean decisions/documentation exist, NOT that hardware is implemented.
[ADR-088](../adr/088-prestretch-differential-pressure-qualification.md) supplements
ADR-087 with the [fail-closed host qualification contract](PRESSURE-CONTRACT.md).
That host validator is tested; firmware integration and physical qualification
remain open in item 1 below.

## Next deliverables, in dependency order

1. [ ] **Firmware acquisition and safety implementation** — verify two distinct sensor readings, timestamps, raw/corrected differential logging, unit conversion, no re-zero under pressure, and fail-closed missing/stale/invalid input handling. Port/build for S3; regression tests first. Exit: host tests plus hardware evidence; current single-sensor/legacy logger is not sufficient.
2. [ ] **Pneumatic/electrical protection design** — select pump using pressure/flow and startup/stall-current evidence; design passive relief and independently enforced timeout/cutoff. Exit: reviewed circuit/fixture specification and declared component limits, not a shopping recommendation based on the withdrawn target.
3. [ ] **Gate M — measurement qualification, no balloon** — independent reference, offset/span, repeated ascending/descending calibration, temperature effects, repeatability/hysteresis and long-duration drift. Exit: predeclared error budget/criteria and raw evidence for the tested range. Owner: bench operator, with agent analysis support.
4. [ ] **Gate S — independent protection, no balloon** — demonstrate actual pump-off, fault latching, no automatic restart, stalled software and stuck-on-drive protection; measure relief peak/overshoot at maximum flow. Exit: physical fault-injection records on a rated fixture. Owner: bench operator.
5. [ ] **Gate E — envelope-specific limits** — supplier/batch evidence and reviewed sacrificial-sample plan; distinguish DecoGlee from Yokohama. Establish target/ramp/dwell, operating ceiling and trip/relief margins including uncertainty/overshoot. Exit: documented numerical limits supported by batch evidence. M/S must pass before rig-driven envelope tests.
6. [ ] **Integrated leak/prestretch validation** — apply approved envelope procedure, log circumference/temperature/ambient pressure, distinguish creep from leaks, then perform separate flight fill/free-lift checks. Exit: reviewed records; not automatic flight approval.

## Explicit blockers / non-blockers

- Numerical balloon limits: **UNKNOWN**; no approved inflation pressure exists.
- Physical rig/calibration/reference availability: required for M/S; software tests cannot replace it.
- Absolute-vs-gauge clarification: **RESOLVED**, not a user blocker.
- Sensor choice: **RESOLVED**, not a user blocker.
- M/S do not require a balloon pressure limit if their separate rated-fixture calibration range is justified in advance.
- No manufacturing order, purchase, firmware flash or flight authorisation is implied by this roadmap.

## Procedure and evidence

- [Detailed basis and log schema](DIFFERENTIAL-PRESSURE-BASIS.md)
- [Revised bench session B1](PRESTRETCH-BENCH-SESSION-B1.md)
- Existing software check: `make -C tools/balloon_pressure_test/test check` — 33 interlock assertions and 12 analysis tests passed during documentation update; no claim of paired-sensor or hardware qualification.
