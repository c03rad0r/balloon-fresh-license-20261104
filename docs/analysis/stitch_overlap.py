"""A stitching via does not have to fit INSIDE an island -- it has to touch it.

My previous test required the whole 0.600 mm circular land to lie inside the island polygon,
which rejected 581/626 candidate points on the 2.249 mm2 island (bbox only 1.80 x 1.26 mm).
That requirement is wrong. A stitching via stitches an island when:

  (a) its land OVERLAPS the island's copper  (touch, not containment), and
  (b) the via is on the GND net so it is electrically the same node, and
  (c) it is clear of every FOREIGN net at S1 clearance, and
  (d) drill/hole rules hold.

Containment was my invention, not the physics. This tests overlap instead, using the
island polygon as a solid and asking whether the via land collides WITH it (any overlap),
while the same land must not collide with foreign copper.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import collide_router as CR
import batch_run as BR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
NET = 'GND'
FROZEN = (39.5, 43.0, 43.5, 46.0)


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

    targets = []
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
            targets.append((ln, i, pl, abs(pl.Area()) / 1e12))

    for (ln, idx, pl, area) in targets:
        print('\n=== %s island %d   %.3f mm2' % (ln, idx, area))
        bbx = pl.BBox()
        cx0 = (bbx.GetLeft() + bbx.GetRight()) // 2
        cy0 = (bbx.GetTop() + bbx.GetBottom()) // 2

        # build a poly-set of the island so we can ask "does the land touch this copper?"
        isl = p.SHAPE_POLY_SET()
        isl.AddOutline(pl)

        best = None
        tried = 0
        # search outward from the island centre: the land may sit partly or wholly outside
        for r in range(0, 1200001, 50000):
            if best:
                break
            for ang in range(0, 360, 15):
                import math
                x = cx0 + int(r * math.cos(math.radians(ang)))
                y = cy0 + int(r * math.sin(math.radians(ang)))
                if (FROZEN[0] <= x / 1e6 <= FROZEN[2]
                        and FROZEN[1] <= y / 1e6 <= FROZEN[3]):
                    continue
                tried += 1
                land = field.disc(p.VECTOR2I(x, y), CR.VIA_R)
                # (a) must actually overlap the island copper
                if not isl.Collide(land, 0):
                    continue
                # (c)(d) must be legal against everything else
                if field.via_ok(x, y, NET):
                    best = (x, y)
                    break
            if r == 0:
                continue

        if best:
            print('   STITCHABLE: via at (%.3f, %.3f) -- land overlaps island, clear of '
                  'foreign nets  (tried %d)' % (best[0] / 1e6, best[1] / 1e6, tried))
        else:
            print('   no stitch site found in a 1.2 mm search ring (tried %d)' % tried)


if __name__ == '__main__':
    main()
