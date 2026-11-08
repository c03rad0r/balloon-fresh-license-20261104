"""Are the three LONGF33 nets genuinely blocked, or did the router give up early?

The batch reported "no path on any layer pair" after ~40s each against a 420s deadline,
so it exhausted rather than timed out. Before spending more compute, measure
connectivity with the seed-correct flood (pad's OWN copper layers only -- seeding F.Cu at
a B.Cu pad silently assumes drill-in-pad).

Reports, per net: whether a legal path exists at all, at several clearances, so the
blocker (if any) is quantified rather than asserted.
"""
import pcbnew as p
import json, os, sys
from pathlib import Path

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import collide_router as R

BOARD = Path('/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb')
CLEARANCES = [int(x) for x in os.environ.get('CLEARS', '200000,150000,100000').split(',')]
CAP = int(os.environ.get('CAP', '1500000'))

NETS = [
    ('/SPI2_SCK', 'U1', '4', 'U2', '12'),
    ('/F33_VSENSE', 'U1', '21', 'R_MON2', '1'),
    ('/EN', 'U1', '3', 'J_PROG', '3'),
]


def pad_of(b, ref, num, net):
    for f in b.GetFootprints():
        if f.GetReference() == ref:
            for q in f.Pads():
                if q.GetNumber() == num and q.GetNetname() == net:
                    return q
    return None


def flood(field, pad, net, box, cap=CAP):
    x0, y0, x1, y1 = box
    c = pad.GetPosition()
    own = [l for l in (p.F_Cu, p.B_Cu) if pad.IsOnLayer(l)] or [p.F_Cu]
    seeds = []
    for l in own:
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                nx, ny = c.x + dx * R.GRID, c.y + dy * R.GRID
                if x0 <= nx <= x1 and y0 <= ny <= y1 and field.track_ok(nx, ny, l, net):
                    seeds.append((nx, ny, l))
    seen, stack = set(seeds), list(seeds)
    while stack and len(seen) < cap:
        cx, cy, l = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = cx + dx * R.GRID, cy + dy * R.GRID
            if not (x0 <= nx <= x1 and y0 <= ny <= y1):
                continue
            k = (nx, ny, l)
            if k in seen:
                continue
            if field.track_ok(nx, ny, l, net):
                seen.add(k)
                stack.append(k)
        other = p.B_Cu if l == p.F_Cu else p.F_Cu
        k2 = (cx, cy, other)
        if k2 not in seen and field.via_ok(cx, cy, net) and field.track_ok(cx, cy, other, net):
            seen.add(k2)
            stack.append(k2)
    return seen, own


def main():
    b = p.LoadBoard(str(BOARD))
    op = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(op)
    bb = op.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    print('board: %s' % BOARD.name)
    for clear in CLEARANCES:
        field = R.Field(b, box, clear)
        print('\n--- clearance %.3f mm' % (clear / 1e6))
        for net, r1, n1, r2, n2 in NETS:
            pa, pb = pad_of(b, r1, n1, net), pad_of(b, r2, n2, net)
            if not pa or not pb:
                print('  %-13s pad missing' % net)
                continue
            A, own_a = flood(field, pa, net, box)
            Bp, _ = flood(field, pb, net, box)
            same = bool(A & Bp)
            import math
            best = None
            if not same and A and Bp:
                for k in list(A)[:2500]:
                    for k2 in list(Bp)[:2500]:
                        dd = math.hypot(k[0] - k2[0], k[1] - k2[1])
                        if best is None or dd < best:
                            best = dd
            print('  %-13s %s.%s<->%s.%s  seed=%s  connected=%-5s cells %d/%d%s'
                  % (net, r1, n1, r2, n2,
                     ','.join(b.GetLayerName(l) for l in own_a), same,
                     len(A), len(Bp),
                     '' if same or best is None else '  nearest %.4f mm' % (best / 1e6)))


if __name__ == '__main__':
    main()
