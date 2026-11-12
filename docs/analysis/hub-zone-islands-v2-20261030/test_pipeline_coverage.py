"""Safety contracts for the isolated real-pipeline coverage driver."""
import tempfile
from pathlib import Path
import unittest
import pipeline_coverage as driver


class CoverageDriverTests(unittest.TestCase):
    def test_source_pin_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'board.kicad_pcb'
            source.write_text('not the pinned board')
            with self.assertRaisesRegex(RuntimeError, 'Source SHA256'):
                driver.assert_source(source)

    def test_existing_output_is_never_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                driver.reserve_output(Path(tmp))

    def test_missing_output_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'new'
            driver.reserve_output(output)
            self.assertTrue(output.is_dir())


if __name__ == '__main__':
    unittest.main()
