"""Verify a claimed route by MEASURING its clearance, not by trusting the router's own verdict.

collide_router.route() returns a path it believes is legal. This campaign has been burned by
routers reporting success at 0.19995 mm (0.05 um under the rule) and by verdicts that could not be
reproduced. So a claimed path is only a candidate until every segment is independently measured
against every foreign copper shape on its layer.

Method: for each consecutive pair of path points, build the actual 0.200 mm segment shape and
Collide it against every foreign obstacle with the S1 guard band. Report the MINIMUM measured gap,
not just pass/fail, so a near-miss is visible rather than rounded away.

SHAPE::Collide only. SHAPE::Distance is unreliable on this board's pads (measured 0.335 mm reported
where the true gap was 0.100 mm).
"""
import math
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
sys.path.insert(0, '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107')

import pcbnew as p

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')

NET = os.environ.get('VERIFY_NET', '/SPI1_MOSI')
TRACK = 200_000
CLEAR = 200_000


def min_gap_to(b, seg_shape, layer, netname):
    """Smallest centre-to-edge clearance from seg_shape to any foreign copper on layer."""
    best = None
    who = ''
    for t in b.GetTracks():
        if t.Type() == p.PCB_VIA_T:
            if t.GetLayer() not in (p.F_Cu, p.B_Cu):
                pass
            shp = t.GetEffectiveShape(0)
            on = True
        else:
            if t.GetLayer() != layer:
                continue
            shp = t.GetEffectiveShape(0)
            on = True
        if not on:
            continue
        if str(t.GetNetname()) == netname:
            continue
        lo, hi = 0, 900_000
        if not p.SHAPE.Collide(shp, seg_shape, lo):
            continue
        # bisect the smallest separation at which they stop colliding
        for _ in range(22):
            mid = (lo + hi) // 2
            if p.SHAPE.Collide(shp, seg_shape, mid):
                lo = mid
            else:
                hi = mid
        gap = hi / UM
        if best is None or gap < best:
            best = gap
            who = 'track %s' % t.GetNetname()
    for f in b.GetFootprints():
        for pad in f.Pads():
            if not pad.IsOnLayer(layer):
                continue
            if str(pad.GetNetname()) == netname:
                continue
            shp = pad.GetEffectiveShape(layer)
            if not p.SHAPE.Collide(shp, seg_shape, 0):
                continue
            lo, hi = 0, 900_000
            for _ in range(22):
                mid = (lo + hi) // 2
                if p.SHAPE.Collide(shp, seg_shape, mid):
                    lo = mid
                else:
                    hi = mid
            gap = hi / UM
            if best is None or gap < best:
                best = gap
                who = 'pad %s.%s' % (f.GetReference(), pad.GetNumber())
    return (best, who) if best is not None else (999.0, 'none')


def main():
    b = p.LoadBoard(LIVE)
    print('verifying a claimed path for %s' % NET)
    # the claimed path from closest_gap: (10.95,15.45) -> (11.05,42.25) on B.Cu
    A = (10.95, 15.45)
    C = (11.05, 42.25)
    print('straight-line gap %.3f mm' % math.hypot(A[0] - C[0], A[1] - C[1]))
    print()
    print('measuring the STRAIGHT segment A->C at 0.200 mm width on B.Cu:')
    seg = p.SHAPE_SEGMENT(p.VECTOR2I(int(A[0] * UM), int(A[1] * UM)),
                          p.VECTOR2I(int(C[0] * UM), int(C[1] * UM)),
                          TRACK // 2)
    gap, who = min_gap_to(b, seg, p.B_Cu, NET)
    print('  min clearance: %.6f mm  against %s' % (gap, who))
    print('  rule requires %.3f mm  -> %s' % (CLEAR / UM, 'PASS' if gap >= CLEAR / UM else 'FAIL'))
    print()
    print('NOTE: a straight A->C is the shortest possible path. If it fails, the router must')
    print('      detour, and a 273-point detour over 26.8 mm is plausible only if the corridor')
    print('      is genuinely open. A ROUTABLE verdict with a straight-line FAIL is not proof.')


if __name__ == '__main__':
    main()
