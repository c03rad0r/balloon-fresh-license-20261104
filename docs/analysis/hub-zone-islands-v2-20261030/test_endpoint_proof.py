"""Fault injection for polygon identity, component joins and false aggregate positives."""
import copy
import unittest
from shapely.geometry import box
from endpoint_proof import correspondence, prove, partition


def record(uid, root, geom=None, kind='pad', layer='F.Cu'):
    return dict(root=root, geom=box(0,0,1,1) if geom is None else geom,
                item=dict(kind=kind, net='GND', layers=[layer], meta=dict(uuid=uid)))


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.before = dict(target=record('zone',1,kind='island'), main=record('main',2), other=record('other',3))
        self.after = copy.deepcopy(self.before)
        self.after['target']['root']=2
        self.after['via']=record('via',2,kind='via')

    def proof(self):
        return prove(self.before,self.after,self.before,'target','main','via',1)

    def test_real_join(self):
        self.assertTrue(self.proof()['geometric_proven'])

    def test_wrong_main_despite_same_count(self):
        self.after['target']['root']=3
        self.after['via']['root']=3
        self.assertFalse(self.proof()['geometric_proven'])

    def test_via_not_in_component(self):
        self.after['via']['root']=4
        self.assertFalse(self.proof()['geometric_proven'])

    def test_native_disagreement(self):
        self.assertFalse(prove(self.before,self.after,self.before,'target','main','via',99)['geometric_proven'])

    def test_unrelated_topology_reassignment(self):
        # A no-via refill must preserve the complete old partition.
        no_via=copy.deepcopy(self.before)
        no_via['other']['root']=2
        self.assertFalse(prove(self.before,self.after,no_via,'target','main','via',1)['geometric_proven'])

    def test_extra_join(self):
        self.after['other']['root']=2
        self.assertFalse(prove(self.before,self.after,self.before,'target','main','via',0)['geometric_proven'])

    def test_index_reordered_but_geometry_stable(self):
        self.after['outline99']=self.after.pop('target')
        no_via=copy.deepcopy(self.before)
        no_via['outline99']=no_via.pop('target')
        self.assertTrue(prove(self.before,self.after,no_via,'target','main','via',1)['geometric_proven'])

    def test_split(self):
        self.after['target']['geom']=box(0,0,.5,1)
        self.after['split']=record('zone',2,box(.5,0,1,1),kind='island')
        with self.assertRaisesRegex(ValueError,'Non-bijective'):
            self.proof()

    def test_merged_outlines(self):
        self.before['second']=record('zone',4,box(1,0,2,1),kind='island')
        self.after['target']['geom']=box(0,0,2,1)
        with self.assertRaisesRegex(ValueError,'Non-bijective'):
            self.proof()

    def test_missing_hard_copper(self):
        del self.after['other']
        with self.assertRaisesRegex(ValueError,'Non-bijective'):
            self.proof()

    def test_hard_geometry_changed(self):
        self.after['main']['geom']=box(0,0,2,2)
        with self.assertRaisesRegex(ValueError,'Hard copper'):
            self.proof()

    def test_retention(self):
        self.after['target']['geom']=box(0,0,.98,1)
        with self.assertRaisesRegex(ValueError,'retention'):
            self.proof()

    def test_disappeared_island(self):
        self.after['target']['geom']=box(3,3,4,4)
        with self.assertRaisesRegex(ValueError,'Non-bijective'):
            self.proof()

    def test_layer_mismatch(self):
        self.after['target']['item']['layers']=['B.Cu']
        with self.assertRaisesRegex(ValueError,'Non-bijective'):
            self.proof()

    def test_extra_copper(self):
        self.after['unexpected']=record('extra',4)
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            self.proof()

    def test_root_relabel_is_not_topology(self):
        relabeled=copy.deepcopy(self.before)
        for r in relabeled.values():
            r['root']+=100
        self.assertEqual(partition(relabeled), partition(self.before))


if __name__ == '__main__':
    unittest.main()
