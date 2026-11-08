"""Sanity-check the island overlap primitive before trusting its null result.

stitch_overlap.py reports "no stitch site" for both accessible islands. A null result is
only meaningful if the primitive would have said YES for a point that obviously overlaps.

Control: take the island polygon and test its OWN CENTRE, which is inside the island by
construction. isl.Collide(land, 0) must be True there. If it is False, the primitive is
wrong (SHAPE_POLY_SET.Collide on a polygon vs a shape has its own semantics) and every
"no site" conclusion from that script is void.

Also reports, per island, how many candidate points PASS the overlap test alone, so the
strictness of the overlap gate and the strictness of via_ok can be told apart.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import math
import collide_router as CR
import batch_run as BR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
NET = 'GND'


def main():
    b = p.LoadBoard(BOARD)
    vias = [t for t in b.GetTracks() if isinstance(t, p.PCB_VIA) and t.GetNetname() == NET]
    pth = [q for f in b.GetFootprints() for q in f.Pads()
           if q.GetNetname() == NET and q.HasHole()]

    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    field = BR.SeqField(b, box, BR.ROUTE_CLEAR)

    for z in b.Zones():
        if z.GetNetname() != NET:
            continue
        ln = b.GetLayerName(z.GetLayer())
        if ln == 'In1.Cu':
            continue
        filled = z.GetFilledPolysList(z.GetLayer())
        for i in range(filled.OutlineCount()):
            pl = filled.COutline(i)
            if any(pl.PointInside(v.GetPosition()) for v in vias):
                continue
            if any(pl.PointInside(q.GetPosition()) for q in pth):
                continue

            area = abs(pl.Area()) / 1e12
            bbx = pl.BBox()
            cx = (bbx.GetLeft() + bbx.GetRight()) // 2
            cy = (bbx.GetTop() + bbx.GetBottom()) // 2
            cv = p.VECTOR2I(cx, cy)
            land = field.disc(cv, CR.VIA_R)
            isl = p.SHAPE_POLY_SET()
            isl.AddOutline(pl)

            inside_centre = pl.PointInside(cv)
            collide_centre = isl.Collide(land, 0)
            # distance-to-outline style: does the land edge reach the island?
            edge_contact = isl.Collide(land, 0)

            print('\n=== %s island %d  %.3f mm2  bbox %.2f x %.2f'
                  % (ln, i, area,
                     (bbx.GetRight() - bbx.GetLeft()) / 1e6,
                     (bbx.GetBottom() - bbx.GetTop()) / 1e6))
            print('   centre PointInside : %s' % inside_centre)
            print('   isl.Collide(land,0): %s   <- MUST be True at the island centre'
                  % collide_centre)
            if inside_centre and not collide_centre:
                print('   *** PRIMITIVE BROKEN: overlap test rejects a point inside the '
                      'island. Every "no site" result from stitch_overlap.py is void.')

            # how many ring points pass overlap alone vs overlap+via_ok
            ov = 0
            ovok = 0
            for r in range(0, 600001, 50000):
                for ang in range(0, 360, 10):
                    x = cx + int(r * math.cos(math.radians(ang)))
                    y = cy + int(r * math.sin(math.radians(ang)))
                    L = field.disc(p.VECTOR2I(x, y), CR.VIA_R)
                    if not isl.Collide(L, 0):
                        continue
                    ov += 1
                    if field.via_ok(x, y, NET):
                        ovok += 1
            print('   ring points overlapping island: %d   of those legal: %d' % (ov, ovok))


if __name__ == '__main__':
    main()
