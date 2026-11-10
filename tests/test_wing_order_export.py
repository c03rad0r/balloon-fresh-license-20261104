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

class ReproducibilityTest(unittest.TestCase):
    """The package must be a function of the source, not of the wall clock.

    Without stamp normalisation two builds of an unchanged board differ in 11 of
    12 files (CreationDate only), so hashing cannot answer "is the committed
    bundle still the design?".  Both directions are asserted: two builds agree,
    and the no-normalisation control does NOT agree (so the test can fail).
    """

    def _build_twice(self):
        import tempfile
        from pathlib import Path
        hashes = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as directory:
                wing.build('interconnect', wing.INTERCON, wing.JLC_PARTS, 'x', outroot=directory)
                hashes.append({p.name: wing.sha256(str(p))
                               for p in sorted(Path(directory, 'interconnect').iterdir())})
        return hashes

    def test_two_builds_are_byte_identical(self):
        a, b = self._build_twice()
        self.assertTrue(a, 'build emitted nothing')
        self.assertEqual(a, b, 'rebuild of an unchanged board changed the package')

    def test_stamp_normalisation_is_what_makes_it_reproducible(self):
        original = wing.normalise_stamps
        wing.normalise_stamps = lambda *a, **k: False   # the control: no normalisation
        try:
            a, b = self._build_twice()
        finally:
            wing.normalise_stamps = original
        differ = [k for k in a if a.get(k) != b.get(k)]
        self.assertTrue(differ, 'control failed to differ: the test cannot detect a wall-clock stamp')

    def test_committed_package_matches_fresh_build(self):
        self.assertEqual(0, wing.check(None, ['interconnect']),
                         'docs/fab/wing-order is stale against the current source')

if __name__ == '__main__':
    unittest.main()
