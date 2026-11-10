# Differential-pressure basis and qualification gates

Status: operator-approved design basis, 2026-11-10; physical qualification NOT RUN.
Canonical decision: [ADR-087](../adr/087-pressure-rig-differential-basis.md). Remaining implementation: [roadmap](ROADMAP.md).
This decision supersedes the ambiguous 1.05 bar instruction, the >=100 kPa pump recommendation, and ADR-147 Decision 5's reliance on leakage/pump-off as sufficient pressure protection. Other ADR-147 decisions remain unchanged.

## DECISIONS

- Define positive overpressure as `dp_raw_pa = p_internal_abs_pa - p_ambient_abs_pa`. Log both absolute readings. Use Pa internally; 1 kPa = 1000 Pa; 1 mbar = 100 Pa. Never silently reinterpret an absolute pressure as a gauge setpoint.
- Retain two independently addressed MS5611 sensors (internal and ambient). Same model does NOT transfer calibration between individual units. BMP280 is optional ground instrumentation, not a replacement for the required pair.
- With both ports vented to the same ambient, measure a signed differential offset. Record `dp_corrected_pa = dp_raw_pa - zero_offset_pa`, the raw data, temperature, sensor identity/address, calibration ID and timestamp. Never automatically re-zero while pressurised: that could hide a fault.
- Qualify the measurement chain without a balloon; balloon limits remain UNKNOWN. No automatic filling with placeholder limits. A sensor-range limit is not a balloon pressure limit.
- Withdraw 1.05 bar as either a launch or test setting. Withdraw buying a >=100 kPa pump to cover its two interpretations. Select pump maximum pressure, flow, startup/stall current, supply and duty cycle only against the qualified test range and relief capacity.
- Retain a single electrically controlled pump; add an independent passive relief path. Pump-off prevents further commanded flow but does not vent trapped pressure or protect against a shorted driver. Natural leakage is not safety protection. A GPIO pull-down does not guarantee shutdown when hung firmware actively holds the pin high; require an independently enforced timeout/cutoff and test it.
- Circumference remains the Yokohama process endpoint; differential pressure is the measurement/control basis for pressure functions and the safety ceiling. This decision does not authorise replacing circumference with a pressure-only stretching recipe.

## Source evidence, NOT operating limits

SF-HAB reports about 0.5 psi differential (3.45 kPa) for particular clear Chinese balloons, held for days, with screening failures. TT7 describes a particular 12-litre test envelope ramped to 7 kPa over ten hours. Neither is a certified limit for our DecoGlee or Yokohama envelopes. No numeric setpoint, trip, reset, or relief pressure is approved here.

- https://sf-hab.org/2021/10/12/preparation-of-the-clear-chinese-balloons
- https://tt7hab.blogspot.com/2019/07/the-pre-stretching-rig.html

## Gate M — measurement chain, NO balloon

Use air, a calibrated low-pressure reference/manometer, pressure-rated fixture/tubing and independent relief. Before applying pressure, document the fixture/sensor rated absolute and differential ranges, reference uncertainty and a bench-only pressure maximum that respects every connected part. Keep liquid out of sensor ports. Sensor absolute pressure must remain within its datasheet range throughout.

1. Verify two distinct devices/readings; disconnect each independently and require a fault. Check address strapping against the exact module/datasheet, not assumed address polarity.
2. Warm up at common ambient; collect at least 10 minutes of timestamped raw readings and temperatures. Record offset, noise and drift. Repeat after power cycling and reseating tubing.
3. At a minimum, apply zero and four distributed reference pressures across the declared bench calibration range, ascending and descending, three cycles. Record reference, both absolute readings, corrected differential, temperature, repeatability, hysteresis and uncertainty. Negative-differential checks only within validated sensor/fixture limits.
4. Repeat at the planned bench temperature extremes with both sensors thermally equilibrated; separately test mismatched sensor temperatures. A hand-warming sign test is not calibration.
5. Run a common-pressure stability check over the intended leak-test duration. A 10-minute trace cannot qualify an hourly leak-rate threshold. Do not infer gas loss from pressure alone without accounting for ambient, gas temperature and envelope creep/volume.
6. Set pass/fail tolerances BEFORE testing, from required trip/reset margin and leak-rate resolution, reference uncertainty and the combined two-sensor error budget. No automatic ±2 mbar acceptance based on a single sensor's absolute accuracy.
7. Mark PASS only for the tested range and temperature interval with recorded evidence. Measurement-chain PASS does not authorise balloon inflation.

## Gate S — independent protection, NO flight balloon

Demonstrate pump OFF on boot, reset, power loss, missing/stale/invalid sensor data, timeout and over-threshold input. Verify physical flow/current, not only software flags. Verify fault latching and explicit recovery; reset alone must not restart filling. Test stalled control software and simulated stuck-on pump-drive condition with a rated fixture: independent protection must still cap pressure.

A passive water-column bubbler is one candidate, not an approved design. Test at maximum pump flow and supply, including overshoot, obstructed tubing, tipping/empty reservoir and liquid-backflow risks. Size/route it so ordinary isolation cannot disconnect the relief from the protected volume. Record worst-case relief pressure and pressure overshoot, not merely nominal water depth. No lifting gas in these tests.

## Gate E — envelope/batch qualification, separate session

Record exact envelope type, dimensions, material/seam construction, lot, humidity, temperature and test history. Establish a conservative initial bound from applicable supplier data or a separately reviewed sacrificial-sample test plan BEFORE inflation. Do not discover a safe ceiling by blindly pumping until visible distress. Different types/batches need separate evidence; an 18-inch foil balloon must not be subjected to the Yokohama circumference targets.

Derive target, ramp, dwell, maximum pressure, software trip/reset and passive relief tolerances with allowance for measurement error and dynamic overshoot. Demonstrate that the highest possible protected pressure is below the qualified envelope limit. A single circumference-pressure trace is not a burst margin or batch qualification. Keep prestretch, leak testing and flight fill/free-lift procedures distinct.

## Required evidence record

CSV fields: timestamp, sensor_internal_id, sensor_ambient_id, p_internal_abs_pa, p_ambient_abs_pa, t_internal_c, t_ambient_c, zero_offset_pa, dp_raw_pa, dp_corrected_pa, reference_dp_pa, pump_command, fault_state, calibration_id.
Envelope tests add envelope_id, lot, circumference_mm, ambient_rh_percent, dwell/ramp state. Retain raw logs; do not overwrite them with corrected values.

Current state: Gate M NOT RUN; Gate S NOT RUN; Gate E NOT RUN. Firmware, schematic and pneumatic implementation are not changed or qualified by this document.
