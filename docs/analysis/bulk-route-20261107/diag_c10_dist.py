#!/usr/bin/env python3
"""Find the bug in the shape graph, using KiCad's own distance predicate.

Established by control experiment (ctrl_c10_move.py): moving C10.1 away ADDS an open, so
C10.1 IS connected at its real position. ctrl_c10.py's "38 -> 38" on deletion was ambiguous
(the net loses a pad AND an island simultaneously). Native DRC is authoritative.

So the shapely graph in connectivity.py is the wrong tool here. This file measures WHY:
it prints, for every same-net item near C10.1, KiCad's own effective-shape DISTANCE and
COLLIDE result, next to the shapely polygon distance the graph used. The disagreement is
then a named, measurable defect in my checker rather than a mystery.
"""
import sys

import pcbnew
from shapely.geometry import Polygon

UM = 1e6


def shapely_poly(q, layer):
    ps = pcbnew.SHAPE_POLY_SET()
    q.TransformShapeToPolygon(ps, layer, 0, 100, pcbnew.ERROR_INSIDE)

    def coords(c):
        return [(v.x / UM, v.y / UM) for v in c.CPoints()]
    if ps.OutlineCount() == 0:
        return None
    return Polygon(coords(ps.COutline(0)))


def main(board_path):
    b = pcbnew.LoadBoard(board_path)
    fp = b.FindFootprintByReference("C10")
    pad = [x for x in fp.Pads() if x.GetNumber() == "1"][0]
    net = pad.GetNetname()
    ref_shape = pad.GetEffectiveShape(pcbnew.F_Cu)
    ref_poly = shapely_poly(pad, pcbnew.F_Cu)
    print(f"C10.1 net={net} effective-shape type={type(ref_shape).__name__}")
    print(f"   shapely polygon: {ref_poly}")

    print("\nall same-net items, KiCad distance vs shapely distance:")
    rows = []
    for f in b.GetFootprints():
        for q in f.Pads():
            if q is pad or q.GetNetname() != net:
                continue
            if not q.GetLayerSet().Contains(pcbnew.F_Cu):
                continue
            s = q.GetEffectiveShape(pcbnew.F_Cu)
            d = ref_shape.Distance(s)
            if d < 3.0:
                rows.append((d, 0.0, f"PAD {f.GetReference()}.{q.GetNumber()}"))
    for t in b.GetTracks():
        if t.GetNetname() != net:
            continue
        isvia = isinstance(t, pcbnew.PCB_VIA)
        layers = [pcbnew.F_Cu, pcbnew.B_Cu] if isvia else [t.GetLayer()]
        if pcbnew.F_Cu not in layers:
            continue
        s = t.GetEffectiveShape(pcbnew.F_Cu)
        d = ref_shape.Distance(s)
        if d < 3.0:
            sp = shapely_poly(t, pcbnew.F_Cu)
            sd = (sp.distance(ref_poly) if sp is not None else float("nan"))
            if isvia:
                p = t.GetPosition()
                tag = f"VIA ({p.x/UM:.3f},{p.y/UM:.3f})"
            else:
                a, c = t.GetStart(), t.GetEnd()
                tag = (f"TRK {pcbnew.LayerName(t.GetLayer())} "
                       f"({a.x/UM:.3f},{a.y/UM:.3f})-({c.x/UM:.3f},{c.y/UM:.3f}) "
                       f"w={t.GetWidth()/UM:.3f}")
            rows.append((d, sd, tag))
    for d, sd, tag in sorted(rows):
        flag = ""
        if (d == 0) != (sd == 0 or (sd is not None and sd < 1e-6)):
            flag = "   <-- TOOLS DISAGREE ON CONTACT"
        print(f"   kicad_dist={d:.6f}  shapely_dist={sd:.6f}  {tag}{flag}")


if __name__ == "__main__":
    main(sys.argv[1])
