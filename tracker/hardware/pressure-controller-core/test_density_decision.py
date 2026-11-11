#!/usr/bin/env python3
"""The density rule has to be a gate, not a paragraph.

`AGENTS.md` §1b requires every placement milestone to report the smallest outline BOTH single-sided
and two-sided. A convention that is only prose gets skipped, so this test refuses a density decision
record that does not carry both numbers.

It is a DOCUMENT gate deliberately: the two candidates are produced by different scripts
(`compact/study.py`, `twosided/twosided.py`), and what must never be missing is the *comparison*.
Running it costs no KiCad and no pcbnew, so it runs everywhere.

Run: python3 test_density_decision.py -v
"""
import json
import os
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORD = HERE / 'compact' / 'DENSITY-DECISION.md'
SINGLE = HERE / 'compact' / 'proof.json'
TWO = HERE / 'twosided' / 'proof.json'


class DensityDecision(unittest.TestCase):
    def test_record_exists(self):
        self.assertTrue(RECORD.exists(), 'DENSITY-DECISION.md is required by AGENTS.md 1b')

    def test_both_candidates_are_named_with_areas(self):
        text = RECORD.read_text()
        for area in ('3250', '2392'):
            self.assertIn(area, text, 'record must state both measured board areas')
        self.assertIn('65 × 50', text)
        self.assertIn('52 × 46', text)

    def test_both_sides_are_reported_not_just_claimed(self):
        # Normalise whitespace: a markdown paragraph wraps mid-phrase, and a gate that fails on
        # a line break in correct content is a gate firing on correct input. The CLAIM is what
        # matters, not where the author's margin fell.
        text = ' '.join(RECORD.read_text().split())
        self.assertIn('26 top / 0 bottom', text)
        self.assertIn('12 top / 14 bottom', text)

    def test_percentage_gap_is_stated(self):
        single, two = 3250.0, 2392.0
        gap = (single - two) / single * 100
        text = RECORD.read_text()
        # the record's own number must match the arithmetic, not a remembered figure
        self.assertIn(f'{gap:.1f}', text,
                      f'record states a gap that does not match {gap:.1f} % from the two areas')

    def test_threshold_crossing_is_acknowledged(self):
        """If two-sided wins by more than 10 %, the record must SAY so, not bury it."""
        single, two = 3250.0, 2392.0
        gap = (single - two) / single * 100
        text = RECORD.read_text()
        if gap >= 10.0:
            self.assertIn('10 %', text,
                          'a threshold win must be acknowledged in the record')
            self.assertRegex(text, r'(exception|declined|not adopted)',
                             'a declined threshold win must be recorded as a decision')

    def test_proofs_agree_with_the_record(self):
        for path, area in ((SINGLE, 3250.0), (TWO, 2392.0)):
            if not path.exists():
                self.skipTest(f'{path.name} missing -- run its generator first')
            proof = json.loads(path.read_text())
            if 'board_area_mm2' in proof:
                self.assertAlmostEqual(proof['board_area_mm2'], area, places=1)
            dims = (proof.get('candidate_dimensions_mm') or proof.get('board_mm'))
            if dims:
                self.assertAlmostEqual(dims[0] * dims[1], area, places=1)

    def test_no_routing_is_claimed_for_either_candidate(self):
        """Neither board is routed; a density record must not imply otherwise."""
        text = RECORD.read_text()
        self.assertRegex(text, r'(not routed|Neither board is routed|unrouted)', 'routing status missing')
        for path in (SINGLE, TWO):
            if not path.exists():
                continue
            proof = json.loads(path.read_text())
            if 'tracks' in proof:
                self.assertEqual(proof['tracks'], 0, f'{path} claims copper tracks')


if __name__ == '__main__':
    unittest.main(verbosity=2)
