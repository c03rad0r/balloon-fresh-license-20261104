"""Can the cross-layer track-track opens actually be CLOSED, not just "a via fits nearby"?

The previous probe answered the wrong question: it found legal via sites in empty copper
within a 1.2 mm halo, which says nothing about whether a legal track can reach both
fragments. This asks the real question with the tested router.

For each net with a cross-layer open:
  1. cluster its track segments into geometrically-touching fragments (2 um tolerance),
  2. find the closest pair of fragments that are on DIFFERENT layers -- that is the open,
  3. route between their nearest points with collide_router.route(), which is allowed to
     change layers via vias at frozen S1 rules,
  4. report ROUTED (with via count and min clearance) or NO PATH with cells explored.

Decision primitive is SHAPE::Collide throughout; SHAPE::Distance is not used anywhere.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json
import math
import time
import collide_router as CR
import batch_run as BR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
OUT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/crosslayer-close.json'
TOL = 2000


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
            self.p[rb] = ra


def fragments(b, net):
    """Group this net's track segments into geometrically touching fragments."""
    segs = [t for t in b.GetTracks()
            if not isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
    vias = [t for t in b.GetTracks()
            if isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
    if not segs:
        return []
    nodes = list(range(len(segs)))
    dsu = DSU()
    for i in nodes:
        dsu.find(i)

    def ends(i):
        t = segs[i]
        return [(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)]

    # join segments whose endpoints coincide on the same layer
    for i in nodes:
        for j in range(i + 1, len(segs)):
            if segs[i].GetLayer() != segs[j].GetLayer():
                continue
            for a in ends(i):
                for c in ends(j):
                    if abs(a[0] - c[0]) <= TOL and abs(a[1] - c[1]) <= TOL:
                        dsu.union(i, j)
    # vias join fragments across layers
    for v in vias:
        c = v.GetPosition()
        hit = []
        for i in nodes:
            for a in ends(i):
                if abs(a[0] - c.x) <= TOL and abs(a[1] - c.y) <= TOL:
                    hit.append(i)
                    break
        for h in hit[1:]:
            dsu.union(hit[0], h)

    groups = {}
    for i in nodes:
        groups.setdefault(dsu.find(i), []).append(i)

    out = []
    for root, idxs in groups.items():
        layers = {segs[i].GetLayer() for i in idxs}
        pts = []
        for i in idxs:
            pts.extend(ends(i))
        out.append({'idx': idxs, 'layers': layers, 'pts': pts,
                    'length_mm': sum(math.hypot(segs[i].GetEnd().x - segs[i].GetStart().x,
                                                segs[i].GetEnd().y - segs[i].GetStart().y) / 1e6
                                     for i in idxs)})
    return out


def main():
    b = p.LoadBoard(BOARD)
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)

    TARGETS = ['/SPI1_MOSI', '/SPI1_SCK', '/W2_SOLAR_N', '/W3_SOLAR_N', '/VSCAP']
    report = {}
    for net in TARGETS:
        frags = fragments(b, net)
        print('\n=== %s : %d fragment(s)' % (net, len(frags)))
        for i, fr in enumerate(frags):
            print('   frag %d: %d segs, %.2f mm, layers %s'
                  % (i, len(fr['idx']), fr['length_mm'],
                     [b.GetLayerName(l) for l in fr['layers']]))

        # closest cross-layer fragment pair
        best = None
        for i in range(len(frags)):
            for j in range(i + 1, len(frags)):
                if frags[i]['layers'] & frags[j]['layers']:
                    if len(frags[i]['layers'] | frags[j]['layers']) < 2:
                        continue
                for (x1, y1) in frags[i]['pts']:
                    for (x2, y2) in frags[j]['pts']:
                        d = math.hypot(x1 - x2, y1 - y2)
                        if best is None or d < best[0]:
                            best = (d, (x1, y1), (x2, y2), i, j)
        if best is None:
            print('   no cross-layer pair')
            report[net] = {'status': 'no-cross-layer-pair'}
            continue
        d, a, c, fi, fj = best
        print('   closest cross-layer pair: %.3f mm between frag %d and frag %d'
              % (d / 1e6, fi, fj))
        print('     from (%.3f, %.3f) to (%.3f, %.3f)'
              % (a[0] / 1e6, a[1] / 1e6, c[0] / 1e6, c[1] / 1e6))

        # route it with the tested, guard-banded router
        t0 = time.time()
        f = BR.SeqField(b, box, BR.ROUTE_CLEAR)
        lstart = sorted(frags[fi]['layers'])
        lgoal = sorted(frags[fj]['layers'])
        margin = 3000000
        rbox = (min(a[0], c[0]) - margin, min(a[1], c[1]) - margin,
                max(a[0], c[0]) + margin, max(a[1], c[1]) + margin)
        try:
            path, why = CR.route(f, a, c, net, rbox, lstart, lgoal,
                                 deadline_steps=900000, deadline_s=180.0)
        except TypeError as e:
            print('   route() signature error: %s' % e)
            report[net] = {'status': 'CALL ERROR: %s' % e}
            continue
        dt = time.time() - t0
        if path:
            vias = sum(1 for k in range(1, len(path)) if path[k][2] != path[k - 1][2])
            ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
                     for k in range(1, len(path))) / 1e6
            print('   ROUTED in %.1fs: %d points, %.2f mm, %d via'
                  % (dt, len(path), ln, vias))
            report[net] = {'status': 'ROUTED', 'length_mm': round(ln, 2),
                           'vias': vias, 'seconds': round(dt, 1),
                           'gap_mm': round(d / 1e6, 3)}
        else:
            print('   NO PATH in %.1fs: %s' % (dt, why))
            report[net] = {'status': 'NO PATH', 'reason': why,
                           'seconds': round(dt, 1), 'gap_mm': round(d / 1e6, 3)}

    json.dump(report, open(OUT, 'w'), indent=2)
    print('\n=== CLOSURE VERDICT (S1 rules, unchanged)')
    for k, v in report.items():
        print('  %-14s %s' % (k, v.get('status')))


if __name__ == '__main__':
    main()
