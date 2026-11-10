"""Prevent the rejected pressure-rig scaffold from silently becoming a PCB."""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]


class QuarantineTest(unittest.TestCase):
    def test_obsolete_entrypoint_refuses_without_output(self):
        script = ROOT / 'tracker/hardware/build_pressure_rig.py'
        self.assertTrue(script.exists(), 'missing explicit quarantine entrypoint')
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('QUARANTINED', result.stderr)
        self.assertFalse((ROOT / 'tracker/hardware/pressure_rig/pressure_rig_v1.kicad_pcb').exists())


if __name__ == '__main__':
    unittest.main()
