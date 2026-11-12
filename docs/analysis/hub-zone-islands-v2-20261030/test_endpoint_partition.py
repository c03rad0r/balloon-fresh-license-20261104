"""Regression guards for full membership, not just the chosen main anchor."""
import copy
import unittest
from endpoint_proof import prove
from test_endpoint_proof import record


class FullPartitionTests(unittest.TestCase):
    def setUp(self):
        self.before = dict(target=record('target', 1), main=record('main', 2),
                           main_tail=record('main_tail', 2), other=record('other', 3))
        self.after = copy.deepcopy(self.before)
        self.after['target']['root'] = 2
        self.after['via'] = record('via', 2, kind='via')

    def test_all_original_main_members_are_required(self):
        self.after['main_tail']['root'] = 3
        result = prove(self.before, self.after, self.before, 'target', 'main', 'via', 1)
        self.assertFalse(result['geometric_endpoint_to_pinned_main'])
        self.assertFalse(result['exact_two_component_join'])
        self.assertFalse(result['geometric_proven'])

    def test_no_via_control_cannot_reassign_members_with_same_counts(self):
        control = copy.deepcopy(self.before)
        control['main_tail']['root'] = 3
        result = prove(self.before, self.after, control, 'target', 'main', 'via', 1)
        self.assertFalse(result['no_refill_partition_reassignment'])
        self.assertFalse(result['geometric_proven'])

    def test_target_already_on_main_is_not_a_new_join(self):
        before = copy.deepcopy(self.before)
        before['target']['root'] = 2
        result = prove(before, self.after, before, 'target', 'main', 'via', 1)
        self.assertFalse(result['exact_two_component_join'])
        self.assertFalse(result['geometric_proven'])


if __name__ == '__main__':
    unittest.main()
