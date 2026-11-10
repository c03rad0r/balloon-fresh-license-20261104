"""Synthetic numbers exercise logic only; none are envelope recommendations."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PressureContractTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'pressure_contract.py'
        self.assertTrue(path.exists(), 'pump-arm qualification validator is missing')
        spec = importlib.util.spec_from_file_location('pressure_contract', path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.check = module.validate
        self.c = dict(schema_version=1, basis='internal_minus_ambient', unit='Pa',
                      envelope_id='SYNTHETIC-ONLY', qualified=True,
                      target_pa=100, ramp_pa_s=1, dwell_s=10, max_pa=200,
                      max_age_s=1, offset_pa=10,
                      internal_sensor_id='A', ambient_sensor_id='B')
        for key in ('envelope_evidence', 'calibration_evidence', 'manometer_evidence',
                    'relief_evidence', 'shutdown_evidence'):
            self.c[key] = 'synthetic-test-record'
        self.s = {'internal': dict(sensor_id='A', model='MS5611', pressure_pa=100060, timestamp_s=10),
                  'ambient': dict(sensor_id='B', model='MS5611', pressure_pa=100000, timestamp_s=10)}

    def test_qualified_synthetic_case_and_offset(self):
        result = self.check(self.c, self.s, 10)
        self.assertTrue(result['eligible'])
        self.assertEqual(result['delta_pa'], 50)

    def test_every_required_field_missing_rejects(self):
        for key in self.c:
            with self.subTest(key=key):
                c = copy.deepcopy(self.c)
                del c[key]
                self.assertFalse(self.check(c, self.s, 10)['eligible'])

    def test_invalid_values_reject(self):
        for key, value in [('qualified', False), ('qualified', 1), ('target_pa', None),
                           ('target_pa', 200), ('ramp_pa_s', 0), ('dwell_s', -1),
                           ('max_pa', float('nan')), ('max_age_s', float('inf')),
                           ('offset_pa', True), ('unit', 'bar'), ('basis', 'absolute'),
                           ('ambient_sensor_id', 'A'), ('relief_evidence', '')]:
            with self.subTest(key=key, value=value):
                c = dict(self.c, **{key: value})
                self.assertFalse(self.check(c, self.s, 10)['eligible'])

    def test_missing_stale_future_invalid_and_overpressure_reject(self):
        for channel in self.s:
            s = copy.deepcopy(self.s)
            del s[channel]
            self.assertFalse(self.check(self.c, s, 10)['eligible'])
            for key, value in [('timestamp_s', 8), ('timestamp_s', 11),
                               ('pressure_pa', float('nan')), ('pressure_pa', -1),
                               ('sensor_id', 'wrong'), ('model', 'BMP280')]:
                with self.subTest(channel=channel, key=key):
                    s = copy.deepcopy(self.s)
                    s[channel][key] = value
                    self.assertFalse(self.check(self.c, s, 10)['eligible'])
        self.s['internal']['pressure_pa'] = 100210
        self.assertFalse(self.check(self.c, self.s, 10)['eligible'])

    def test_malformed_inputs_reject(self):
        for c, s, now in [(None, self.s, 10), (self.c, None, 10),
                           (self.c, self.s, float('nan'))]:
            self.assertFalse(self.check(c, s, now)['eligible'])

    def test_shipped_contract_cannot_arm(self):
        c = json.loads((ROOT / 'pressure-contract.json').read_text())
        self.assertFalse(self.check(c, self.s, 10)['eligible'])

if __name__ == '__main__':
    unittest.main()
