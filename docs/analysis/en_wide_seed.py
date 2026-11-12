"""Retry /EN with a WIDER terminal seed radius before calling it trapped.

The earlier /EN verdict was NO PATH at 164 steps with seed_radius=2 (a 0.2 mm lattice radius).
For a 1.500 x 0.900 mm pad that radius is smaller than the pad's own copper extent, so every seed
cell can land inside the pad's clearance pocket while the real mouth of the terminal is one step
further out. collide_router.route()'s own docstring warns about exactly this.

/EN also has the most room of the four trapped pads (1.40 mm widest clear run, measured), so it is
the one worth retrying hardest before accepting the enclosure.

Tries seed radii 2, 4, 6, 8 and 10 and reports the best. Read-only: adds nothing.
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

NET = '/EN'
A = (11.050, 36.430)      # U1.3  F.Cu
C = (31.000, 59.780)      # J_PROG.3 PTH


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

    print('%s  U1.3 (%.3f,%.3f) -> J_PROG.3 (%.3f,%.3f)  %.2f mm apart'
          % (NET, A[0], A[1], C[0], C[1],
             ((C[0] - A[0]) ** 2 + (C[1] - A[1]) ** 2) ** 0.5))
    print()
    best = None
    for sr in (2, 4, 6, 8, 10):
        path, why = CR.route(f, a, c, NET, rbox,
                             [p.F_Cu], [p.B_Cu],
                             deadline_steps=1500000, deadline_s=120.0,
                             seed_radius=sr)
        ok = bool(path) and len(path) >= 2
        print('  seed_radius=%-3d %-12s %s' % (
            sr, 'PATH %d pts' % len(path) if ok else 'NO PATH',
            '' if ok else (why or '')[:56]))
        if ok:
            best = (sr, path)
            break
    print()
    if best:
        print('ROUTABLE with seed_radius=%d, %d points' % (best[0], len(best[1])))
        print('=> /EN is NOT trapped; the earlier 164-step verdict was a seed-radius artefact')
        return 0
    print('no path at any seed radius -> the enclosure, not the seed, is the limit')
    return 1


if __name__ == '__main__':
    sys.exit(main())
