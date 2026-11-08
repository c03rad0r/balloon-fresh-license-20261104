"""Route /SPI2_SCK from U1.4 out the +x corridor, now that it is measured as open.

CORRECTION TO MY OWN CONCLUSION: the escape probe reported 0 free directions for this pad because it
sampled only 12 rays from the pad CENTRE and stopped each at the first blocker. The Collide bisection
measurement of the same pad shows the +x side is genuinely open:

    /SPI2_MISO  (12.250, 39.350)->(12.250, 31.750)   0.350 mm from the pad copper  -> CLEAR
    /F33_CS_N   (12.950, 39.650)->(12.950, 32.450)   1.050 mm from the pad copper  -> CLEAR

Both exceed the 0.200 mm requirement. So a 0.200 mm track CAN leave this pad to the right; the 12-ray
probe missed it because its rays at 0 deg and 30 deg ran into /SPI2_MISO at a point that is not the
pad's actual mouth.

Target: J_PROG? No -- this net's other end. /SPI2_SCK is Pad 4 (U1) to Pad 12 (U2) at (33.7289, 30.6).
Route U1.4 -> U2.12 with the real Collide router. Read-only probe first, no board write.
"""
import math
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

NET = '/SPI2_SCK'
A = (11.050, 37.700)     # U1.4
C = (33.7289, 30.600)    # U2.12


def main():
    b = p.LoadBoard(LIVE)
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    f = BR.SeqField(b, box, BR.ROUTE_CLEAR)

    a = (int(round(A[0] * UM)), int(round(A[1] * UM)))
    c = (int(round(C[0] * UM)), int(round(C[1] * UM)))
    margin = 8000000
    rbox = (min(a[0], c[0]) - margin, min(a[1], c[1]) - margin,
            max(a[0], c[0]) + margin, max(a[1], c[1]) + margin)

    print('%s  U1.4 (%.3f,%.3f) -> U2.12 (%.3f,%.3f)  %.2f mm'
          % (NET, A[0], A[1], C[0], C[1], math.hypot(C[0] - A[0], C[1] - A[1])))
    for sr in (2, 4, 6):
        path, why = CR.route(f, a, c, NET, rbox, [p.F_Cu], [p.F_Cu],
                             deadline_steps=1500000, deadline_s=90.0, seed_radius=sr)
        ok = bool(path) and len(path) >= 2
        print('  seed_radius=%-2d %s %s' % (
            sr, 'PATH %d pts' % len(path) if ok else 'NO PATH', '' if ok else (why or '')[:56]))
        if ok:
            # measure the realised length and the first few waypoints so the shape is reviewable
            ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
                     for k in range(1, len(path))) / UM
            print('  realised length %.2f mm, %d points, layers %s'
                  % (ln, len(path), sorted({l for _, _, l in path})))
            print('  first waypoints:', [(round(x / UM, 3), round(y / UM, 3))
                                          for x, y, _ in path[:4]])
            return 0
    print('no path -> the +x corridor measurement needs rechecking')
    return 1


if __name__ == '__main__':
    sys.exit(main())
