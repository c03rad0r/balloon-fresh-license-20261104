"""Regression tests; intentionally not a full geometry coverage claim."""
import copy
import json
from pathlib import Path
import unittest
from validate_stitching import identities


class EvidenceTests(unittest.TestCase):
    def test_identity_order(self):
        v = dict(type='clearance', severity='error', description='F.Cu',
                 items=[dict(uuid='a', description='pad'), dict(uuid='b', description='via')])
        w = copy.deepcopy(v)
        w['items'].reverse()
        self.assertEqual(identities({'violations':[v]}), identities({'violations':[w]}))

    def test_equal_counts_do_not_hide_replacement(self):
        v = dict(type='clearance', severity='error', description='F.Cu',
                 items=[dict(uuid='a', description='pad')])
        w = copy.deepcopy(v)
        w['items'][0]['uuid'] = 'different'
        self.assertTrue(identities({'violations':[w]}) - identities({'violations':[v]}))

    def test_duplicate_identity_is_counted(self):
        v = dict(type='edge', severity='error', description='edge', items=[])
        self.assertEqual(sum((identities({'violations':[v,v]})-
                              identities({'violations':[v]})).values()), 1)

    def test_inventory_and_native_evidence(self):
        root = Path(__file__).parent
        inv = json.loads((root/'islands.json').read_text())
        native = json.loads((root/'native_validation.json').read_text())
        self.assertEqual((inv['island_total'], inv['isolated_total'],
                          inv['graph_sigma_components_minus_1'],inv['affected_nets']), (35,29,86,22))
        self.assertTrue(inv['refill']['refill_byte_noop'])
        self.assertEqual(len(native['arms']), 29)
        self.assertTrue(native['source_unchanged'])
        for island in inv['islands']:
            if island['stitch']:
                st = island['stitch']
                self.assertEqual(st['required_edge_clearance_mm'], .5)
                if st['legal']:
                    self.assertTrue(st['lands_on_main_component'])
                    self.assertGreaterEqual(st['minimum_modeled_margin_mm'], 0)
        self.assertFalse(any(a['connectivity_proven'] for a in native['arms']))


if __name__ == '__main__':
    unittest.main()
