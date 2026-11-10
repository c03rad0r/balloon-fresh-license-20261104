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
        """The normaliser must actually rewrite stamps.

        The previous version of this control built twice with normalisation
        disabled and required the two builds to differ. That is a wall-clock race:
        if both builds land in the same second the stamps match and the control
        fails - which is exactly what happened in CI, where the control reported
        "failed to differ: the test cannot detect a wall-clock stamp" against a
        correct builder. It now tests the mechanism directly and deterministically:
        a file carrying a known stamp must be rewritten to the frozen epoch, and
        the frozen epoch must be what appears afterwards.
        """
        import tempfile
        from pathlib import Path
        epoch = wing.export_epoch()
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory, 'probe.gbr')
            probe.write_text(
                'G04 #@! TF.CreationDate,2026-01-02T03:04:05+01:00*\n'
                'G04 Created by KiCad (PCBNEW 9.0.9) date 2026-01-02 03:04:05*\n')
            changed = wing.normalise_stamps(directory, epoch=epoch)
            self.assertTrue(changed, 'normaliser did not touch a file with a wall-clock stamp')
            text = probe.read_text()
            self.assertNotIn('2026-01-02', text, 'wall-clock stamp survived normalisation')
            import datetime
            iso = datetime.datetime.fromtimestamp(
                epoch, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
            self.assertIn(iso, text, 'normalised stamp is not the frozen epoch')

    def test_epoch_does_not_depend_on_git_history(self):
        """The epoch must be identical in a worktree and in CI's checkout.

        A git-derived epoch made the same builder emit different bytes per
        machine: `git log -1 -- <board>` returns different times locally and in
        CI's checkout. Pin the frozen constant unless SOURCE_DATE_EPOCH overrides.
        """
        self.assertEqual(1762300000, wing.export_epoch(),
                         'epoch is not the frozen constant; reproducibility will differ per machine')
        # and the override must still work, so a caller can pin a build explicitly
        import os
        os.environ['SOURCE_DATE_EPOCH'] = '1600000000'
        try:
            self.assertEqual(1600000000, wing.export_epoch(),
                             'SOURCE_DATE_EPOCH override is not honoured')
        finally:
            del os.environ['SOURCE_DATE_EPOCH']

    def test_committed_package_matches_fresh_build(self):
        """Byte-reproducible, OR provably built by a different exporter version.

        `check` returns 2 when the committed package carries a different
        export_toolchain: 9.0.8 and 9.0.9 emit different gerber bytes for
        identical geometry, so a byte diff across versions proves nothing. In
        that case the artwork comparison still has to hold, and `check` says so.
        """
        rc = wing.check(None, ['interconnect'])
        self.assertIn(rc, (0, 2),
                      'docs/fab/wing-order is stale against the current source')

if __name__ == '__main__':
    unittest.main()