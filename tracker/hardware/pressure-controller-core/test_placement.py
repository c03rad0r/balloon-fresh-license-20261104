#!/usr/bin/env python3
"""Clean control plus real mutation regressions; requires distro pcbnew/shapely."""
import unittest
import placement as m
import pcbnew as pcb
class Placement(unittest.TestCase):
    def setUp(self):
        self.c,self.e=m.inputs(m.OUT/'core.xml')
        self.b=m.build(m.OUT/'core.xml')
        self.f={f.GetReference():f for f in self.b.GetFootprints()}
    def check(self): return m.validate(self.b,self.c,self.e)
    def test_clean(self): self.assertEqual(self.check()['unique_endpoints'],125)
    def test_wrong_net(self):
        self.f['U3'].Pads()[0].SetNetCode(0)
        with self.assertRaisesRegex(ValueError,'mapping mismatch'): self.check()
    def test_duplicate_reference(self):
        self.f['U4'].SetReference('U3')
        with self.assertRaisesRegex(ValueError,'duplicate/missing'): self.check()
    def test_missing_pad(self):
        self.f['U3'].Remove(self.f['U3'].Pads()[0])
        with self.assertRaisesRegex(ValueError,'missing endpoint'): self.check()
    def test_courtyard_collision(self):
        self.f['U4'].SetPosition(self.f['U3'].GetPosition())
        with self.assertRaisesRegex(ValueError,'pad overlap|courtyard overlap'): self.check()
    def test_reservation(self):
        self.f['U4'].SetPosition(pcb.VECTOR2I(pcb.FromMM(60),pcb.FromMM(40)))
        with self.assertRaisesRegex(ValueError,'motor reservation'): self.check()
    def test_antenna_datum(self):
        self.f['U1'].SetPosition(pcb.VECTOR2I(pcb.FromMM(28),pcb.FromMM(7)))
        with self.assertRaisesRegex(ValueError,'antenna edge datum'): self.check()
if __name__=='__main__': unittest.main(verbosity=2)
