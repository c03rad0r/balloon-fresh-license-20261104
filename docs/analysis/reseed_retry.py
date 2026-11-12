"""Last routing question: are the pad-pair opens trapped, or did the router under-seed?

Known on this board: route() defaults to seed_radius=2 (0.2 mm), which has already produced
a false NO PATH here -- open 31 /W3_SOLAR_N read "516 steps NO PATH" while a radius-3 flood
found 2724 connected cells. So a NO PATH from the default seed is not proof of blockage.

Two opens remain as genuine pad-pair routes:
  /SPI2_SCK   U1.4  <-> U2.12    (measured 166-cell pocket at the pad)
  /EN         U1.3  <-> J_PROG.3 (both ends reach ~850k cells but never meet)

This retries both with seed_radius 3..6 and a generous budget, and reports whether a path
appears. If one does, it is real routing work that should be done. If none does, the
blockage claim is sound and those two are assembly/placement decisions.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import math
import time
import collide_router as CR
import batch_run as BR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'

TARGETS = {
    '/SPI2_SCK': ('U1', '4', 'U2', '12'),
    '/EN': ('U1', '3', 'J_PROG', '3'),
}


def pad_xy(b, ref, num):
    for f in b.GetFootprints():
        if f.GetReference() != ref:
            continue
        for q in f.Pads():
            if q.GetNumber() == num:
                c = q.GetPosition()
                layers = [l for l in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu) if q.IsOnLayer(l)]
                return ((c.x, c.y), layers)
    return (None, None)


def main():
    b = p.LoadBoard(BOARD)
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)

    for net, (r1, n1, r2, n2) in TARGETS.items():
        (s, ls) = pad_xy(b, r1, n1)
        (g, lg) = pad_xy(b, r2, n2)
        print('\n=== %s  %s.%s (%s) -> %s.%s (%s)'
              % (net, r1, n1,
                 None if s is None else '%.3f,%.3f' % (s[0] / 1e6, s[1] / 1e6),
                 r2, n2,
                 None if g is None else '%.3f,%.3f' % (g[0] / 1e6, g[1] / 1e6)))
        if s is None or g is None:
            print('   pad not found')
            continue
        print('   start layers %s   goal layers %s'
              % ([b.GetLayerName(l) for l in ls], [b.GetLayerName(l) for l in lg]))
        span = math.hypot(g[0] - s[0], g[1] - s[1]) / 1e6
        print('   straight-line %.2f mm' % span)

        found = None
        for radius in (3, 4, 5, 6):
            margin = 5000000
            rbox = (min(s[0], g[0]) - margin, min(s[1], g[1]) - margin,
                    max(s[0], g[0]) + margin, max(s[1], g[1]) + margin)
            f = BR.SeqField(b, box, BR.ROUTE_CLEAR)
            t0 = time.time()
            try:
                path, why = CR.route(f, s, g, net, rbox, ls, lg,
                                     deadline_steps=1500000, deadline_s=150.0,
                                     seed_radius=radius)
            except Exception as e:
                print('   radius %d: ERROR %s' % (radius, e))
                continue
            dt = time.time() - t0
            if path:
                vias = sum(1 for k in range(1, len(path)) if path[k][2] != path[k - 1][2])
                ln = sum(math.hypot(path[k][0] - path[k - 1][0],
                                    path[k][1] - path[k - 1][1])
                         for k in range(1, len(path))) / 1e6
                print('   radius %d: ROUTED %.2f mm, %d via (%.1fs)'
                      % (radius, ln, vias, dt))
                found = (radius, ln, vias)
                break
            print('   radius %d: NO PATH (%.1fs) %s' % (radius, dt, why))

        print('   ==> %s' % ('ROUTABLE at radius %d -- real work remains'
                             % found[0] if found else
                             'trapped at every seed radius 3-6: blockage is real'))


if __name__ == '__main__':
    main()
