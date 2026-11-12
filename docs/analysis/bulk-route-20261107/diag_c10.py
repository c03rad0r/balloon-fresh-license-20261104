#!/usr/bin/env python3
"""Diagnose the C10.1 discrepancy: DRC reports +3V3 with ONE open (J_PROG.2 -> R_F1.1),
while the shape graph reports C10.1 as an isolated island. One of the two tools is wrong;
per the repo rule, inter-tool disagreement is a STOP, not a tie to break.

Prints, for the named same-net items, the native effective shape, its bounding box, and
what copper lies within a radius -- so the difference between "shape touches" and "bbox
touches" is visible rather than inferred.
"""
import math
import sys

import pcbnew

UM = 1e6


def bbox_of(s):
    if s is None:
        return None
    bb = s.BBox()
    return (bb.GetX() / UM, bb.GetY() / UM,
            (bb.GetX() + bb.GetWidth()) / UM, (bb.GetY() + bb.GetHeight()) / UM)


def main(board_path):
    b = pcbnew.LoadBoard(board_path)
    for ref, num in (("C10", "1"), ("C10", "2"), ("R_F1", "1"), ("U1", "2")):
        fp = b.FindFootprintByReference(ref)
        p = [x for x in fp.Pads() if x.GetNumber() == num][0]
        pb = p.GetBoundingBox()
        print(f"\n{ref}.{num} net={p.GetNetname()} "
              f"layers={[pcbnew.LayerName(x) for x in p.GetLayerSet().Seq() if x in (0, 31)]} "
              f"rect=({pb.GetX()/UM:.3f},{pb.GetY()/UM:.3f})"
              f"-({(pb.GetX()+pb.GetWidth())/UM:.3f},{(pb.GetY()+pb.GetHeight())/UM:.3f}) "
              f"attr={p.GetAttribute()} shape={p.GetShape()}")
        for ln, lid in (("F.Cu", pcbnew.F_Cu), ("B.Cu", pcbnew.B_Cu)):
            s = p.GetEffectiveShape(lid)
            print(f"   {ln} effective shape {type(s).__name__ if s else None} bbox={bbox_of(s)}")

    for ref in ("C10",):
        fp = b.FindFootprintByReference(ref)
        for p in fp.Pads():
            pb = p.GetBoundingBox()
            px = (pb.GetX() + pb.GetWidth() / 2) / UM
            py = (pb.GetY() + pb.GetHeight() / 2) / UM
            ns = p.GetNetname()
            print(f"\n{ref}.{p.GetNumber()} centre ({px:.3f},{py:.3f}) net={ns}")
            for t in b.GetTracks():
                if t.GetNetname() != ns:
                    continue
                if "VIA" in str(type(t)):
                    q = t.GetPosition()
                    d = math.hypot(q.x / UM - px, q.y / UM - py)
                    what = f"via ({q.x/UM:.3f},{q.y/UM:.3f}) w={t.GetWidth(pcbnew.F_Cu)/UM:.2f}"
                else:
                    a1, b1 = t.GetStart(), t.GetEnd()
                    d = min(math.hypot(a1.x / UM - px, a1.y / UM - py),
                            math.hypot(b1.x / UM - px, b1.y / UM - py))
                    what = (f"trk {pcbnew.LayerName(t.GetLayer())} "
                            f"({a1.x/UM:.2f},{a1.y/UM:.2f})-({b1.x/UM:.2f},{b1.y/UM:.2f}) "
                            f"w={t.GetWidth()/UM:.2f}")
                if d < 3.0:
                    print(f"   {what} centre_dist={d:.3f}")
            # same-net zone polygon coverage
            for z in b.Zones():
                if z.GetNetname() != ns:
                    continue
                for lid in z.GetLayerSet().CuStack():
                    ln = pcbnew.LayerName(lid)
                    ps = z.GetFilledPolysList(lid)
                    if ps.OutlineCount() == 0:
                        continue
                    shp = p.GetEffectiveShape(lid)
                    hit = bool(shp.Collide(ps, 0)) if shp is not None else None
                    print(f"   zone {z.GetZoneName() or '?'} {ln} outlines={ps.OutlineCount()} "
                          f"collides_pad={hit}")


if __name__ == "__main__":
    main(sys.argv[1])
