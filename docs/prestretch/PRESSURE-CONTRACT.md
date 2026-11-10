# Pressure qualification contract (ADR-087)

`tools/balloon_pressure_test/pressure-contract.json` is deliberately unqualified:
all envelope numbers and evidence are null. No usable default pressure is shipped.
`pressure_contract.py` validates a candidate pump-arm preflight; it never accesses
GPIO or enables a pump. Existing firmware remains a logger/idle interlock stub.
This host gate is NOT yet wired into firmware and MUST NOT be treated as hardware
protection. Actuation is disabled pending the roadmap's remaining acceptance gates.

## Contract semantics

- `schema_version: 1`, `basis: internal_minus_ambient`, `unit: Pa` are exact.
- `envelope_id` identifies the specific type/lot; `qualified` must be boolean true.
- Positive `target_pa < max_pa`, `ramp_pa_s`, `dwell_s` are envelope-specific,
  reviewed values, not blog examples. `max_age_s` is an explicitly qualified
  freshness bound, not a built-in timing default.
- `offset_pa` is the same-pressure measured **internal minus ambient** offset.
  Corrected delta = internal absolute Pa − ambient absolute Pa − offset Pa.
- Two distinct `internal_sensor_id`/`ambient_sensor_id` bind calibration to the pair.
- Nonempty `envelope_evidence`, `calibration_evidence`, `manometer_evidence`,
  `relief_evidence`, `shutdown_evidence` refer to operator-reviewed records.
  The validator checks presence, NOT truth or authenticity: invented references
  are not qualification. Review uncertainty, calibration validity and relief
  capacity/setpoint margins against the maximum before approving these records.
- Samples contain `internal` and `ambient` objects, each with `sensor_id`,
  `model: MS5611`, positive absolute `pressure_pa`, and `timestamp_s`. Both
  timestamps and `--now-s` must use the same monotonic clock. Missing, stale,
  future, nonfinite or mismatched data reject. Negative corrected differential
  or differential at/above the maximum rejects. This is not a sensor driver or
  a full runtime ramp/dwell controller; sensor health/range diagnostics and
  continuous stop enforcement remain integration work.

## Run without hardware

```
make -C tools/balloon_pressure_test/test check
python3 tools/balloon_pressure_test/pressure_contract.py \
  tools/balloon_pressure_test/pressure-contract.json samples.json --now-s 10
```

CLI prints JSON and exits 1 on rejection (including missing/unreadable input),
0 on preflight eligibility only. There is no arm command or GPIO path. Never
copy the synthetic test fixture's numbers into an operational contract.
Measurement-only logging and same-pressure characterization may proceed with
pump power disconnected. No physical actuation or purchase is authorized here.

## Verification

RED: before implementation, six tests failed with “pump-arm qualification
validator is missing”. GREEN: the same six tests pass, including per-field
missing checks and invalid/stale/missing sensor cases. Existing C interlock:
33 passed, 0 failed; existing plot analysis: 12 passed, 0 failed.
These are host logic tests, not calibration, relief, hardware or envelope tests.
