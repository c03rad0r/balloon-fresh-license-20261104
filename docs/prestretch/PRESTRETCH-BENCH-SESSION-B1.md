# Bench Session B1 — measurement chain and independent protection

Status: SPEC, NOT RUN. No physical calibration, interlock or balloon test has been performed.
Authority: [Differential pressure basis](DIFFERENTIAL-PRESSURE-BASIS.md), operator-approved 2026-11-10, supersedes the previous combined balloon/threshold session.

## Scope

B1 now covers Gate M (measurement) and Gate S (protection) WITHOUT a balloon. Envelope qualification is a separate Gate E; do not derive a safe ceiling from a single circumference-pressure trace. The old instruction to apply Yokohama 88–105 inch targets to a discardable DecoGlee 18-inch balloon is withdrawn.

## Equipment

- ESP32-S3 rig; existing C3 firmware must be ported and paired acquisition verified before use.
- Two MS5611 sensors: internal tap and ambient, distinct addresses verified on actual modules. Same model does not transfer calibration.
- Independent calibrated low-pressure reference/manometer, rated air fixture/tubing, independent passive relief and liquid-backflow protection where applicable.
- Pump whose flow, supply, startup/stall current and duty cycle are documented; independent pump-off enforcement and latched alarm.
- Means to measure actual pump current/flow and capture both sensor readings, temperatures, reference pressure and fault state.

## Execute

Follow Gate M and Gate S in DIFFERENTIAL-PRESSURE-BASIS.md without substituting older thresholds. Record fixture/sensor bounds and bench pressure maximum BEFORE applying air. No lifting gas. No balloon attached.

1. Establish ambient zero and per-pair offset; preserve raw values. No re-zero under pressure.
2. Sweep declared calibration range up/down against the independent reference; repeat after power cycling and at planned temperature limits. Record uncertainty, repeatability, hysteresis and drift.
3. Demonstrate independently detected missing/stale/invalid readings for EACH sensor.
4. Verify physical pump-off on boot/reset/power loss, threshold trip and timeout; fault reset alone must not restart filling.
5. Prove protection with stalled control software and simulated stuck-on drive using the rated fixture. Verify the independent relief's worst-case peak pressure at maximum flow; no reliance on natural balloon leaks.
6. Record evidence and failures; do not mark the chain qualified merely because firmware self-tests pass.

## Acceptance and handoff

All numerical accuracy, drift and trip margins require a written error budget and predeclared criteria. Withdraw the old blanket ±2 mbar criterion and 10-minute-to-hour drift extrapolation. Leak-rate interpretation requires ambient/temperature/volume control and a sufficiently long stability baseline.

Deliver signed/raw/corrected paired-pressure CSV, reference calibration information, sensor identities, firmware hash, fixture diagram, pressure/temperature bounds, fault response/overshoot observations and pass/fail against each criterion. Use the schema in DIFFERENTIAL-PRESSURE-BASIS.md.

Gate M/S acceptance qualifies only the tested rig range. Gate E remains required before balloon inflation; no Kconfig placeholders become approved merely by completing B1. No PCB, firmware deployment or flight approval is implied.
