"""Host qualification preflight only. No GPIO, no pump control, no hardware safety claim."""
import argparse
import json
import math
from pathlib import Path


def validate(contract, samples, now_s):
    """Return eligibility/reasons; timestamps must share caller's monotonic clock.

    Evidence references are operator attestations, not proof that hardware was tested.
    Eligibility never energizes anything and does not replace runtime interlocks.
    """
    errors = []
    delta = None

    def number(value):
        return type(value) in (int, float) and math.isfinite(value)

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    if not isinstance(contract, dict) or not isinstance(samples, dict) or not number(now_s):
        return dict(eligible=False, delta_pa=None, reasons=['invalid input structure or clock'])
    c = contract
    if type(c.get('schema_version')) is not int or c.get('schema_version') != 1:
        errors.append('unsupported schema_version')
    if c.get('basis') != 'internal_minus_ambient' or c.get('unit') != 'Pa':
        errors.append('requires internal_minus_ambient in Pa')
    if c.get('qualified') is not True:
        errors.append('envelope is not qualified')
    for key in ('envelope_id', 'internal_sensor_id', 'ambient_sensor_id',
                'envelope_evidence', 'calibration_evidence', 'manometer_evidence',
                'relief_evidence', 'shutdown_evidence'):
        if not text(c.get(key)):
            errors.append('missing ' + key)
    if c.get('internal_sensor_id') == c.get('ambient_sensor_id'):
        errors.append('sensor identities must differ')
    numeric = ('target_pa', 'ramp_pa_s', 'dwell_s', 'max_pa', 'max_age_s', 'offset_pa')
    for key in numeric:
        if not number(c.get(key)):
            errors.append('missing/invalid ' + key)
    if all(number(c.get(key)) for key in numeric):
        if not 0 < c['target_pa'] < c['max_pa']:
            errors.append('requires 0 < target_pa < max_pa')
        if any(c[key] <= 0 for key in ('ramp_pa_s', 'dwell_s', 'max_age_s')):
            errors.append('ramp, dwell and freshness bound must be positive')
    readings = {}
    for channel in ('internal', 'ambient'):
        s = samples.get(channel)
        if not isinstance(s, dict):
            errors.append('missing sensor ' + channel)
            continue
        if s.get('model') != 'MS5611' or s.get('sensor_id') != c.get(channel + '_sensor_id'):
            errors.append('sensor identity/model mismatch: ' + channel)
        p, t = s.get('pressure_pa'), s.get('timestamp_s')
        if not number(p) or p <= 0:
            errors.append('invalid absolute pressure: ' + channel)
        else:
            readings[channel] = p
        if (not number(t) or not number(c.get('max_age_s')) or
                not 0 <= now_s - t <= c['max_age_s']):
            errors.append('missing/stale/future sensor timestamp: ' + channel)
    if len(readings) == 2 and number(c.get('offset_pa')):
        # Offset = internal minus ambient measured with both at the same pressure.
        delta = readings['internal'] - readings['ambient'] - c['offset_pa']
        if not math.isfinite(delta) or not number(c.get('max_pa')) or not 0 <= delta < c['max_pa']:
            errors.append('differential outside qualified arm range')
    return dict(eligible=not errors, delta_pa=delta, reasons=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contract', type=Path)
    parser.add_argument('samples', type=Path)
    parser.add_argument('--now-s', required=True, type=float)
    args = parser.parse_args()
    try:
        result = validate(json.loads(args.contract.read_text()),
                          json.loads(args.samples.read_text()), args.now_s)
    except (OSError, ValueError, TypeError) as exc:
        result = dict(eligible=False, delta_pa=None, reasons=[str(exc)])
    print(json.dumps(result))
    return 0 if result['eligible'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
