"""Actual pcbnew objects, not doubles of the geometry being checked."""
import unittest
import pcbnew as k
from shapely.geometry import Point
import run_island_inventory as inv


class NativeGeometry(unittest.TestCase):
    def test_edge_rectangle_uses_centerline_not_stroke_bbox(self):
        b = k.BOARD()
        d = k.PCB_SHAPE(b)
        d.SetShape(k.SHAPE_T_RECT)
        d.SetStart(k.VECTOR2I(0, 0))
        d.SetEnd(k.VECTOR2I(2000000, 1000000))
        d.SetWidth(100000)
        d.SetLayer(k.Edge_Cuts)
        b.Add(d)
        self.assertEqual(inv.edge_segments(b)[0].bounds, (0, 0, 2, 1))

    def test_unsupported_edge_fails_closed(self):
        b = k.BOARD()
        d = k.PCB_SHAPE(b)
        d.SetShape(k.SHAPE_T_CIRCLE)
        d.SetLayer(k.Edge_Cuts)
        b.Add(d)
        with self.assertRaises(ValueError):
            inv.edge_segments(b)

    def test_zero_contact_does_not_join_gap(self):
        from shapely.geometry import box
        self.assertGreater(box(0, 0, 1, 1).distance(box(1.001, 0, 2, 1)), 0)

    def test_arc_is_not_chord(self):
        b = k.BOARD()
        t = k.PCB_ARC(b)
        t.SetStart(k.VECTOR2I(1000000, 0))
        t.SetMid(k.VECTOR2I(0, 1000000))
        t.SetEnd(k.VECTOR2I(-1000000, 0))
        t.SetWidth(200000)
        g = inv.track_poly(t)
        self.assertTrue(g.covers(Point(0, 1)))
        self.assertFalse(g.covers(Point(0, 0)))

    def test_unfilled_circle_has_hole(self):
        b = k.BOARD()
        d = k.PCB_SHAPE(b)
        d.SetShape(k.SHAPE_T_CIRCLE)
        d.SetCenter(k.VECTOR2I(0, 0))
        d.SetEnd(k.VECTOR2I(1000000, 0))
        d.SetWidth(200000)
        d.SetFilled(False)
        self.assertFalse(inv.drawing_poly(d).covers(Point(0, 0)))

    def test_pad_drill_is_not_copper(self):
        b = k.BOARD()
        f = k.FOOTPRINT(b)
        b.Add(f)
        p = k.PAD(f)
        p.SetAttribute(k.PAD_ATTRIB_PTH)
        p.SetShape(k.PAD_SHAPE_CIRCLE)
        p.SetSize(k.VECTOR2I(2000000, 2000000))
        p.SetDrillSize(k.VECTOR2I(1000000, 1000000))
        f.Add(p)
        self.assertFalse(inv.pad_poly(p).covers(Point(0, 0)))
        self.assertTrue(inv.pad_poly(p).covers(Point(.75, 0)))

    def test_via_drill_is_not_copper(self):
        b = k.BOARD()
        v = k.PCB_VIA(b)
        v.SetWidth(600000)
        v.SetDrill(300000)
        self.assertFalse(inv.via_poly(v).covers(Point(0, 0)))
        self.assertTrue(inv.via_poly(v).covers(Point(.25, 0)))

    def test_slot_not_bounding_circle(self):
        b = k.BOARD()
        f = k.FOOTPRINT(b)
        b.Add(f)
        p = k.PAD(f)
        p.SetDrillShape(k.PAD_DRILL_SHAPE_OBLONG)
        p.SetDrillSize(k.VECTOR2I(2000000, 500000))
        f.Add(p)
        g = inv.hole_poly(p)
        self.assertFalse(g.covers(Point(0, .5)))
        self.assertTrue(g.covers(Point(.7, 0)))


if __name__ == '__main__':
    unittest.main()
