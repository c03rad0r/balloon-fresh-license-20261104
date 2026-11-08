"""Can Pad 21 of U1 (/F33_VSENSE) reach the B.Cu fragment that already exists?

Measured state of the net:
  - the B.Cu copper forms a CLOSED LOOP: (21.850,8.350) -> (18.750,8.350) -> (18.750,10.250)
    -> (14.950,10.250) -> (14.950,6.650), every segment end-to-end, touching NO pad
  - Pad 21 of U1 sits at (20.435, 51.650) on F.Cu only, 41.434 mm from the nearest loop point
  - the two F33VIA vias were rejected because they added no connectivity

So the open is a genuine 41 mm pad fanout: the pad is isolated, the loop is isolated, and the two
need a real route between them. This probe asks ONLY whether such a corridor exists at S1. It does
not add anything.

The target is any point on the existing loop, not a specific one; the router is pointed at the loop
corner nearest the pad, and a second attempt targets the loop corner most reachable from the pad's
side of the board.
"""
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
sys.path.insert(0, '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107')

import pcbnew as p
import collide_router as CR
import batch_run as BR

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')

NET = '/F33_VSENSE'
PAD = (20.435, 51.650)
# corners of the existing B.Cu loop
TARGETS = [(18.750, 10.250), (21.850, 8.350), (14.950, 10.250), (18.750, 8.350)]


def main():
    b = p.LoadBoard(LIVE)
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    f = BR.SeqField(b, box, BR.ROUTE_CLEAR)

    print('pad %s at (%.3f, %.3f) on F.Cu' % (NET, PAD[0], PAD[1]))
    for (tx, ty) in TARGETS:
        a = (int(round(PAD[0] * UM)), int(round(PAD[1] * UM)))
        c = (int(round(tx * UM)), int(round(ty * UM)))
        margin = 6000000
        rbox = (min(a[0], c[0]) - margin, min(a[1], c[1]) - margin,
                max(a[0], c[0]) + margin, max(a[1], c[1]) + margin)
        path, why = CR.route(f, a, c, NET, rbox,
                             [p.F_Cu], [p.B_Cu],
                             deadline_steps=1200000, deadline_s=90.0)
        ok = path is not None and len(path) >= 2
        print('  -> (%6.3f,%6.3f)  %s %s' % (
            tx, ty, 'PATH %d pts' % len(path) if ok else 'NO PATH',
            '' if ok else (why or '')[:60]))
        if ok:
            print()
            print('ROUTABLE: pad to loop corner (%.3f, %.3f)' % (tx, ty))
            return 0
    print()
    print('no corridor found from the pad to any loop corner at S1')
    return 1


if __name__ == '__main__':
    sys.exit(main())
