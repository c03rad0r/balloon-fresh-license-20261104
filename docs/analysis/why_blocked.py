"""Why can't two same-net fragments 0.0707 mm apart on one layer be joined?

If two 0.200 mm tracks of the SAME net are 0.0707 mm apart at their nearest points, their copper
already overlaps -- so DRC should not report them as separate fragments at all. Either the
fragments are separated by a real obstacle, or the "gap" is between two points that cannot legally
carry a track because a third object sits between them.

This measures, for the closest point pair of every fragment pair of a net:
  - which FOREIGN objects block a 0.200 mm track between the two points (Collide at the S1 guard)
  - the nearest foreign copper to each endpoint
  - whether the obstacle also separates them on the OTHER layer (so a via cannot help)

Read-only. No board mutation.
"""
import itertools
import math
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
sys.path.insert(0, '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107')

import pcbnew as p
import batch_run as BR

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
NET = os.environ.get('PROBE_NET', '/F33_VSENSE')
GUARD = 200_000 + 70_711


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
    return (round(x, 3), round(y, 3))


def main():
    b = p.LoadBoard(LIVE)
    dsu = DSU()
    ends = {}
    for t in b.GetTracks():
        if t.Type() != p.PCB_TRACE_T:
            continue
        if str(t.GetNetname()) != NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        a, c = key(s.x, s.y), key(e.x, e.y)
        dsu.union((a, t.GetLayer()), (c, t.GetLayer()))
        for q in (a, c):
            ends.setdefault((q, t.GetLayer()), set()).add(t.GetLayer())

    roots = {}
    for q in ends:
        roots.setdefault(dsu.find(q), []).append(q)
    frags = sorted(roots.values(), key=lambda v: -len(v))
    print('%s: %d fragment(s), sizes %s' % (NET, len(frags), [len(f) for f in frags]))

    # nearest foreign object to a point on a layer
    def nearest_foreign(x, y, layer):
        # stored fragment points are RAW NANOMETRES (key() rounds the pcbnew ints directly).
        # Multiplying by UM again overflows SWIG's int32.
        pt = p.SHAPE_CIRCLE(p.VECTOR2I(int(round(x)), int(round(y))), 1000)
        best = None
        who = ''
        for t in b.GetTracks():
            if str(t.GetNetname()) == NET:
                continue
            if t.Type() != p.PCB_VIA_T and t.GetLayer() != layer:
                continue
            shp = t.GetEffectiveShape(0)
            lo, hi = 0, 600_000
            if not p.SHAPE.Collide(shp, pt, lo):
                continue
            for _ in range(20):
                mid = (lo + hi) // 2
                if p.SHAPE.Collide(shp, pt, mid):
                    lo = mid
                else:
                    hi = mid
            gap = hi / UM
            if best is None or gap < best:
                best, who = gap, 'track %s on %s' % (
                    t.GetNetname(), b.GetLayerName(t.GetLayer()))
        for f in b.GetFootprints():
            for pad in f.Pads():
                if str(pad.GetNetname()) == NET:
                    continue
                if not pad.IsOnLayer(layer):
                    continue
                shp = pad.GetEffectiveShape(layer)
                lo, hi = 0, 600_000
                if not p.SHAPE.Collide(shp, pt, lo):
                    continue
                for _ in range(20):
                    mid = (lo + hi) // 2
                    if p.SHAPE.Collide(shp, pt, mid):
                        lo = mid
                    else:
                        hi = mid
                gap = hi / UM
                if best is None or gap < best:
                    best, who = gap, 'pad %s.%s' % (f.GetReference(), pad.GetNumber())
        return (best, who) if best is not None else (999.0, 'none')

    def blockers_between(ax, ay, la, cx, cy, lc):
        """Foreign objects a 0.200 mm track between the points would hit."""
        hits = []
        seg = p.SHAPE_SEGMENT(p.VECTOR2I(int(round(ax)), int(round(ay))),
                              p.VECTOR2I(int(round(cx)), int(round(cy))), 100_000)
        for t in b.GetTracks():
            if str(t.GetNetname()) == NET:
                continue
            if t.Type() != p.PCB_VIA_T and t.GetLayer() != la:
                continue
            if p.SHAPE.Collide(t.GetEffectiveShape(0), seg, GUARD):
                hits.append('track %s/%s' % (t.GetNetname(), b.GetLayerName(t.GetLayer())))
        for f in b.GetFootprints():
            for pad in f.Pads():
                if str(pad.GetNetname()) == NET:
                    continue
                if not pad.IsOnLayer(la):
                    continue
                if p.SHAPE.Collide(pad.GetEffectiveShape(la), seg, GUARD):
                    hits.append('pad %s.%s' % (f.GetReference(), pad.GetNumber()))
        return hits

    pairs = []
    for i, j in itertools.combinations(range(len(frags)), 2):
        for (a, la) in frags[i]:
            for (c, lc) in frags[j]:
                pairs.append((math.hypot(a[0] - c[0], a[1] - c[1]), a, la, c, lc, i, j))
    pairs.sort()
    print('closest pair %.4f mm' % (pairs[0][0] / UM))
    print()
    for d, a, la, c, lc, i, j in pairs[:4]:
        print('gap %.4f mm  frag%d((%.3f,%.3f) @%s) -> frag%d((%.3f,%.3f) @%s)' % (
            d / UM, i, a[0] / UM, a[1] / UM, b.GetLayerName(la),
            j, c[0] / UM, c[1] / UM, b.GetLayerName(lc)))
        for lbl, q, l in (('A', a, la), ('C', c, lc)):
            g, who = nearest_foreign(q[0], q[1], l)
            print('   nearest foreign to %s: %.4f mm  (%s)' % (lbl, g, who))
        bl = blockers_between(a[0], a[1], la, c[0], c[1], lc)
        print('   blockers on a direct track: %s' % (bl if bl else 'NONE'))
        print()


if __name__ == '__main__':
    main()
