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

class OriginTest(unittest.TestCase):
    def test_native_origin_and_asymmetric_pad_anchor(self):
        import pcbnew
        import csv
        board = pcbnew.LoadBoard(wing.INTERCON)
        # Asymmetric pad geometry must not silently move the placement datum.
        fp = board.FindFootprintByReference('D1')
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(13.25), pcbnew.FromMM(7.75)))
        pad = next(iter(fp.Pads()))
        pad.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(10), pcbnew.FromMM(5)))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'cpl.csv'
            wing.write_cpl(str(out), board, 999, wing.JLC_PARTS)
            with out.open() as fh:
                rows = {r['Designator']: r for r in csv.DictReader(fh)}
            self.assertAlmostEqual(float(rows['D1']['Mid X']), 13.25)
            self.assertAlmostEqual(float(rows['D1']['Mid Y']), -7.75)
            self.assertAlmostEqual(float(rows['D2']['Mid Y']), -6)

class PolarityTest(unittest.TestCase):
    def test_native_bypass_polarity(self):
        import pcbnew
        wing.verify_bypass_polarity(pcbnew.LoadBoard(wing.INTERCON))

    def test_each_reversed_diode_fails(self):
        import pcbnew
        for ref in ('D1', 'D2', 'D3'):
            with self.subTest(ref=ref):
                board = pcbnew.LoadBoard(wing.INTERCON)
                pads = {p.GetNumber(): p for p in board.FindFootprintByReference(ref).Pads()}
                k, a = pads['1'].GetNet(), pads['2'].GetNet()
                pads['1'].SetNet(a)
                pads['2'].SetNet(k)
                with self.assertRaisesRegex(ValueError, ref + ': bypass polarity'):
                    wing.verify_bypass_polarity(board)

if __name__ == '__main__':
    unittest.main()
