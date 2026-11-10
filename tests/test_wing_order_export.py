"""Native export regression: assembly paste must not depend on saved plot selection."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wing_order', ROOT / 'tracker/hardware/build_wing_order.py')
wing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wing)

class ExportTest(unittest.TestCase):
    def test_front_paste_has_six_diode_pads(self):
        with tempfile.TemporaryDirectory() as directory:
            wing.export(wing.INTERCON, directory, 'interconnect')
            paste = list(Path(directory).glob('*.gtp'))
            self.assertEqual(len(paste), 1, 'missing front paste for fitted D1-D3')
            flashes = [line for line in paste[0].read_text().splitlines() if line.endswith('D03*')]
            self.assertEqual(len(flashes), 6)
            holes, tools = wing.parse_drill(str(next(Path(directory).glob('*.drl'))))
            self.assertEqual(len(holes), 2, 'both vias must be drilled')

if __name__ == '__main__':
    unittest.main()
