"""Why does a 2.249 mm2 GND island refuse a 0.600 mm via?

A 0.6 mm land is ~0.283 mm2 of copper; a 2.249 mm2 island has room on paper. So either the
island is a long thin sliver, or foreign copper crowds it, or the predicate is too strict.
This reports, for the best candidate points, WHICH constraint fails:

  (a) centre not inside the island
  (b) land not fully inside the island (island is thin / the land would overhang)
  (c) via_ok false -- and names the blocking object

That separates "physically impossible" from "my check is wrong", which is the difference
between reporting a blocker and shipping a bug.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import collide_router as CR
import batch_run as BR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
NET = 'GND'
RING = ((-0.3, 0), (0.3, 0), (0, -0.3), (0, 0.3),
        (-0.21, -0.21), (0.21, -0.21), (-0.21, 0.21), (0.21, 0.21))


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
        print('   bbox %.2f x %.2f mm'
              % ((bbx.GetRight() - bbx.GetLeft()) / 1e6,
                 (bbx.GetBottom() - bbx.GetTop()) / 1e6))
        # scan a coarse grid inside the bbox and classify failures
        reasons = {}
        best = None
        step = 50000
        x = bbx.GetLeft()
        while x <= bbx.GetRight():
            y = bbx.GetTop()
            while y <= bbx.GetBottom():
                if not pl.PointInside(p.VECTOR2I(x, y)):
                    y += step
                    continue
                # (b) land fully inside?
                overhang = [d for d in RING
                            if not pl.PointInside(p.VECTOR2I(int(x + d[0] * 1e6),
                                                             int(y + d[1] * 1e6)))]
                if overhang:
                    reasons['land_overhangs_island'] = reasons.get('land_overhangs_island', 0) + 1
                else:
                    ok = field.via_ok(x, y, NET)
                    if ok:
                        if best is None:
                            best = (x, y)
                    else:
                        # name the blocker
                        land = field.disc(p.VECTOR2I(x, y), CR.VIA_R)
                        who = None
                        for l in CR.CU_ALL:
                            for o in field.buckets[l].query(x, y, CR.VIA_R + field.clear):
                                if o.net == NET:
                                    continue
                                if p.SHAPE.Collide(land, o.sh, field.clear):
                                    who = '%s %s' % (o.kind, o.name)
                                    break
                            if who:
                                break
                        key = 'foreign: %s' % who if who else 'via_ok false (other)'
                        reasons[key] = reasons.get(key, 0) + 1
                y += step
            x += step

        if best:
            print('   LEGAL SITE FOUND at (%.3f, %.3f)' % (best[0] / 1e6, best[1] / 1e6))
        else:
            print('   no legal site. failure reasons:')
            for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:6]:
                print('     %-44s %d points' % (k, v))


if __name__ == '__main__':
    main()
