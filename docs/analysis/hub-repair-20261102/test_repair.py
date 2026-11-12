import unittest
from pathlib import Path
from repair import canonical_non_target, identities, OUT, STEM

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.before = (OUT/'before'/(STEM+'.kicad_pcb')).read_text()
        self.after = (OUT/'after'/(STEM+'.kicad_pcb')).read_text()
    def test_graphic_layer_only(self):
        self.assertEqual(canonical_non_target(self.before), canonical_non_target(self.after))
    def test_reject_copper_mutation(self):
        self.assertIn('(width 0.2)', self.after)
        changed = self.after.replace('(width 0.2)', '(width 0.21)', 1)
        self.assertNotEqual(canonical_non_target(self.before), canonical_non_target(changed))
    def test_reject_graphic_geometry_mutation(self):
        changed = self.after.replace('(start -8 8)', '(start -8.1 8)', 1)
        self.assertNotEqual(self.after, changed)
        self.assertNotEqual(canonical_non_target(self.before), canonical_non_target(changed))
    def test_missing_target_fails_closed(self):
        with self.assertRaises(AssertionError):
            canonical_non_target(self.after.replace('1faf3492-15b9-4f0b-9396-c5d97f87f506','missing'))
    def test_multiset_not_set(self):
        v = dict(type='clearance',severity='error',description='test',items=[dict(uuid='one',description='pad')])
        self.assertEqual(sum(identities({'violations':[v,v]}).values()),2)

if __name__ == '__main__':
    unittest.main()
