#!/usr/bin/env python3
"""AGENTS.md and ADR-120 must not disagree about population sides.

THE DEFECT THIS PREVENTS (measured 2026-11-10): `AGENTS.md` §1b said "start single-sided, use a
second side only if it earns ≥10 % of board area" while the v10 directives in the same file said
"Two-sided population is the default", and ADR-120 R1 said parts go on both sides unconditionally.
Three records, two rules, no winner named. The repo's own AGENTS.md calls that a **DEFECT, not an
ambiguity** — and it was live: an agent reading the directive could pick either rule and be
"compliant".

A textual/structural check is the right instrument here because the failure mode is *prose drift*,
not geometry. It asserts three things a future edit could break:

  1. §1b exists and carries the ≥10 % threshold.
  2. The v10 directive defers to §1b BY NAME (so precedence is explicit, not implied).
  3. ADR-120 R1 carries the same precedence pointer, so the ADR and AGENTS.md agree.

It also fails if the retired unconditional phrasing comes back.

Run: python3 test_density_precedence.py -v
"""
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root(start):
    """Walk UP until AGENTS.md is found.

    A fixed `parents[N]` index is how this gate first went vacuously green: every test skipped
    because the index pointed above the repo, and a skip reads as OK. Walking until the marker
    file is found makes a misplacement FAIL LOUDLY instead of skipping.
    """
    for cand in [start, *start.parents]:
        if (cand / 'AGENTS.md').is_file():
            return cand
    return None


ROOT = _repo_root(HERE)
AGENTS = ROOT / 'AGENTS.md' if ROOT else None
ADR120 = ROOT / 'docs/adr/120-v10-placement-process.md' if ROOT else None


def norm(text):
    return ' '.join(text.split())


class Precedence(unittest.TestCase):
    def setUp(self):
        if AGENTS is None or not AGENTS.exists():
            self.fail(f'AGENTS.md not reachable from {HERE} -- the precedence gate cannot run, '
                      'and a gate that cannot run is NOT a pass')
        self.text = norm(AGENTS.read_text())

    def test_density_rule_exists_with_threshold(self):
        self.assertIn('§1b Board density', self.text,
                      'the §1b density rule was removed or renamed')
        self.assertRegex(self.text, r'≥10 ?%',
                         'the measurable adoption threshold is gone')

    def test_v10_directive_defers_to_the_density_rule(self):
        # The directive must NAME §1b so precedence is explicit; an implicit rule is what
        # produced two competing "defaults" in the first place.
        # Capture the WHOLE directive including its bold header: the precedence claim lives in
        # the header ("per §1b ... which governs"), and a regex that starts after the closing **
        # cannot see it -- which made this gate fail on a correct file.
        m = re.search(r'(1\. \*\*Population sides.{0,1400}?)2\. \*\*Four RF sites',
                      self.text)
        self.assertIsNotNone(m, 'the v10 population directive is missing or restructured -- '
                                're-check that it still defers to §1b')
        assert m is not None
        directive = m.group(1)
        self.assertIn('§1b', directive,
                      'the v10 directive no longer names §1b; precedence is ambiguous again')
        self.assertRegex(directive, r'(governs|per `?§1b|resolved by measurement)',
                         'the directive does not state that §1b governs')

    def test_retired_unconditional_phrasing_is_gone(self):
        self.assertNotIn('Two-sided population is the default', self.text,
                         'the unconditional two-sided default is back -- it contradicts §1b')
        self.assertNotIn('Parts go on both sides; the outline shrinks',
                         self.text,
                         'the unconditional two-sided phrasing is back')

    def test_adr120_r1_agrees_with_agents_md(self):
        if ADR120 is None or not ADR120.exists():
            self.fail(f'ADR-120 not reachable from {HERE}; the ADR/AGENTS agreement is unchecked')
        adr = norm(ADR120.read_text())
        self.assertIn('AGENTS.md', adr,
                      'ADR-120 R1 does not reference the AGENTS.md density rule')
        self.assertIn('§1b', adr, 'ADR-120 R1 does not name §1b')
        self.assertRegex(adr, r'≥10 ?%', 'ADR-120 R1 omits the measurable threshold')

    def test_both_records_allow_a_recorded_exception(self):
        """Neither record may imply a threshold win is mandatory against operator judgement --
        the pressure controller is a live exception and the rule must permit it."""
        self.assertRegex(self.text, r'recorded operator decision',
                         'AGENTS.md no longer permits a recorded single-sided exception')
        if ADR120 is not None and ADR120.exists():
            self.assertRegex(norm(ADR120.read_text()), r'recorded operator decision',
                             'ADR-120 no longer permits a recorded single-sided exception')


if __name__ == '__main__':
    unittest.main(verbosity=2)
