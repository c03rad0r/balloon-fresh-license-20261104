"""For a net with more than two fragments, find the CLOSEST legal connection, not the largest pair.

bridge_halves.py always joins the two biggest fragments. When that fails it says NO PATH and the
whole net is written off -- but the two biggest fragments may be far apart on purpose, while two
other fragments (or two points on different layers of the same fragment) sit millimetres apart.

This enumerates every pair of fragment endpoints across the net, sorts by distance, and asks the
Collide-only router about each in order until one succeeds. Read-only: it does NOT modify the
board, it only reports which gap is closable and where.

Why this matters: /SPI1_MOSI's two largest halves are 26.800 mm apart and NO PATH in 0.4 s. That
says nothing about the 0.05 mm-scale gaps a fragment pair may actually have.
"""
import itertools
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

NET = os.environ.get('PROBE_NET', '/SPI1_MOSI')
TOP = int(os.environ.get('PROBE_TOP', '12'))


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def key(x, y):
    return (round(x), round(y))


def main():
    b = p.LoadBoard(LIVE)
    dsu = DSU()
    ends = {}          # endpoint -> list of (layer)
    segs = []
    for t in b.GetTracks():
        if t.Type() != p.PCB_TRACE_T:
            continue
        if str(t.GetNetname()) != NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        a, c = key(s.x, s.y), key(e.x, e.y)
        dsu.union(a, c)
        segs.append((a, c, t.GetLayer()))
        for q in (a, c):
            ends.setdefault(q, set()).add(t.GetLayer())

    # also union endpoints that touch the same pad (a pad joins layers through its own copper)
    for f in b.GetFootprints():
        for pad in f.Pads():
            if str(pad.GetNetname()) != NET:
                continue
            pos = pad.GetPosition()
            k = key(pos.x, pos.y)
            # pads are single nodes joining whatever tracks reach them
            for q in list(ends):
                if math.hypot(q[0] - k[0], q[1] - k[1]) < 3000:
                    dsu.union(q, k)

    roots = {}
    for q in ends:
        roots.setdefault(dsu.find(q), []).append(q)
    frags = sorted(roots.values(), key=lambda v: -len(v))
    print('%s: %d fragment(s), sizes %s' % (NET, len(frags), [len(f) for f in frags]))
    if len(frags) < 2:
        print('only one fragment -- nothing to join')
        return 0

    pairs = []
    for i, j in itertools.combinations(range(len(frags)), 2):
        for a in frags[i]:
            for c in frags[j]:
                d = math.hypot(a[0] - c[0], a[1] - c[1])
                pairs.append((d, i, j, a, c))
    pairs.sort()
    print('candidate gaps: %d, closest %.4f mm' % (len(pairs), pairs[0][0] / UM))
    print()

    # one collision field over the whole board, exactly as the bridge runner builds it
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    f = BR.SeqField(b, box, BR.ROUTE_CLEAR)

    tried = 0
    for d, i, j, a, c in pairs[:TOP]:
        tried += 1
        la = [sorted(ends[a])[0]]
        lc = [sorted(ends[c])[0]]
        margin = 4000000
        rbox = (min(a[0], c[0]) - margin, min(a[1], c[1]) - margin,
                max(a[0], c[0]) + margin, max(a[1], c[1]) + margin)
        path, why = CR.route(f, a, c, NET, rbox, la, lc,
                             deadline_steps=400000, deadline_s=20.0)
        # CONTRACT: a real route has at least 2 points. A 1-point "path" is the search returning
        # its start cell unchanged -- it joins nothing, and treating it as ROUTABLE is how a
        # degenerate result gets mistaken for a finding.
        ok = path is not None and len(path) >= 2
        print('  A=(%.4f,%.4f) la=%s  C=(%.4f,%.4f) lc=%s' % (
            a[0] / UM, a[1] / UM, la, c[0] / UM, c[1] / UM, lc))
        print('  gap %-4d-%4d  %.4f mm  %-5s->%-5s  %s %s' % (
            i, j, d / UM,
            'F' if la[0] == p.F_Cu else 'B', 'F' if lc[0] == p.F_Cu else 'B',
            'ROUTABLE' if ok else 'no', ('' if ok else why or '')[:48]))
        if ok:
            print()
            print('CLOSEST ROUTABLE GAP: fragments %d and %d, %.4f mm, %d points'
                  % (i, j, d / UM, len(path)))
            return 0
    print()
    print('no routable gap among the closest %d pairs' % tried)
    return 1


if __name__ == '__main__':
    sys.exit(main())
