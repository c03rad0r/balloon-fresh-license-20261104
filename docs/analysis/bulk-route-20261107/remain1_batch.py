"""Connectivity-based routing for the remaining pad-to-track / track-to-track opens.

CUTSENSE2 proved the method: cluster the net's copper into electrically touching fragments,
find the fragment holding one endpoint, route to the nearest point in a DIFFERENT fragment.
Distance-to-nearest-same-net-copper closed 0 opens; this closed 3.

Targets here are the opens in the same class that were previously written off as
"needs drill-in-pad, not routable":
  2  Pad 21 [/F33_VSENSE] of U1 on F.Cu   || Track on B.Cu 3.8000 mm
  3  Track [/SPI1_MOSI] on B.Cu 1.8000    || Track on F.Cu 16.6000 mm
  5  Track [/VSCAP] on F.Cu 1.0687        || Pad 1 [/VSCAP] of R_BAL1 on F.Cu
 17  Pad 3 [/EN] of U1 on F.Cu            || PTH pad 3 [/EN] of J_PROG
  0  Pad 3 [/CUT_SENSE_W1] of J_W1 B.Cu   || Track on F.Cu 0.8500 mm (retry, different seeds)

Open 5 is same-layer track-to-pad, so it needs no via at all -- the cheapest possible fixed.
Gated by adopt_batch.py: opens must fall, no per-type regression.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json
import math
import os
import subprocess
import collide_router as CR
import batch_run as BR

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
REL = 'docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, REL, 'latest.kicad_pcb')
NAME = 'REMAIN1'
TOL = 3000

# net -> (kind, ref, pin) or ('track',) meaning: pick the net's own fragments
TARGETS = [
    ('/VSCAP', 'pad', 'R_BAL1', '1'),        # open 5, same-layer track->pad
    ('/F33_VSENSE', 'pad', 'U1', '21'),      # open 2
    ('/EN', 'pad', 'U1', '3'),               # open 17
    ('/CUT_SENSE_W1', 'pad', 'J_W1', '3'),   # open 0 retry
    ('/SPI1_MOSI', 'track', None, None),     # open 3, track->track
]


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
    tracks = [t for t in b.GetTracks()
              if t.GetNetname() == net and not isinstance(t, p.PCB_VIA)]
    vias = [t for t in b.GetTracks()
            if t.GetNetname() == net and isinstance(t, p.PCB_VIA)]
    pads = [(f.GetReference(), q) for f in b.GetFootprints() for q in f.Pads()
            if q.GetNetname() == net]
    nodes = [('T', t) for t in tracks] + [('P', (r, q)) for (r, q) in pads]
    dsu = DSU()
    for i in range(len(nodes)):
        dsu.find(i)

    def pts_of(node):
        k, o = node
        if k == 'T':
            return [(o.GetStart().x, o.GetStart().y, o.GetLayer()),
                    (o.GetEnd().x, o.GetEnd().y, o.GetLayer())]
        r, q = o
        c = q.GetPosition()
        return [(c.x, c.y, l) for l in (p.F_Cu, p.B_Cu) if q.IsOnLayer(l)]

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            for (x1, y1, l1) in pts_of(nodes[i]):
                for (x2, y2, l2) in pts_of(nodes[j]):
                    if l1 == l2 and abs(x1 - x2) <= TOL and abs(y1 - y2) <= TOL:
                        dsu.union(i, j)
    for v in vias:
        c = v.GetPosition()
        hit = [i for i in range(len(nodes))
               if any(abs(x - c.x) <= TOL and abs(y - c.y) <= TOL
                      for (x, y, _) in pts_of(nodes[i]))]
        for h in hit[1:]:
            dsu.union(hit[0], h)

    groups = {}
    for i in range(len(nodes)):
        groups.setdefault(dsu.find(i), []).append(i)
    out = []
    for root, idxs in groups.items():
        pts, pads_in = [], []
        for i in idxs:
            pts.extend(pts_of(nodes[i]))
            if nodes[i][0] == 'P':
                pads_in.append(nodes[i][1][0] + '.' + nodes[i][1][1].GetNumber())
        out.append({'pts': pts, 'pads': pads_in, 'n': len(idxs)})
    return out


def apply_path(b, path, net):
    n = b.FindNet(net)
    ns = nv = 0
    for k in range(1, len(path)):
        x1, y1, l1 = path[k - 1]
        x2, y2, l2 = path[k]
        if l1 != l2:
            v = p.PCB_VIA(b)
            v.SetNet(n)
            v.SetPosition(p.VECTOR2I(int(round(x1)), int(round(y1))))
            v.SetWidth(int(BR.VIA_R * 2))
            v.SetDrill(int(CR.DRILL_R * 2))
            b.Add(v)
            nv += 1
        elif (int(x1), int(y1)) != (int(x2), int(y2)):
            t = p.PCB_TRACK(b)
            t.SetNet(n)
            t.SetLayer(l1)
            t.SetWidth(int(BR.TRACK_R * 2))
            t.SetStart(p.VECTOR2I(int(round(x1)), int(round(y1))))
            t.SetEnd(p.VECTOR2I(int(round(x2)), int(round(y2))))
            b.Add(t)
            ns += 1
    return ns, nv


def main():
    B = os.path.join(ROOT, REL, 'batches', NAME)
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in ('kicad_pro', 'kicad_dru', 'fp-lib-table'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    b = p.LoadBoard(src)
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)

    done, rep = [], {}
    for (net, kind, ref, pin) in TARGETS:
        frags = fragments(b, net)
        label = '%s:%s' % (net, ref + '.' + pin if ref else 'auto')
        print('\n%-22s fragments=%d sizes=%s' % (label, len(frags), [f['n'] for f in frags]))
        if len(frags) < 2:
            print('    single fragment -- nothing to bridge')
            rep[label] = {'status': 'single-fragment'}
            continue

        # start fragment: the one holding the named pad, or (for track targets) the fragment
        # with the most track nodes
        mi = None
        if ref:
            for i, fr in enumerate(frags):
                if ('%s.%s' % (ref, pin)) in fr['pads']:
                    mi = i
        else:
            mi = max(range(len(frags)), key=lambda i: frags[i]['n'])
        if mi is None:
            print('    target pad not in the net')
            rep[label] = {'status': 'pad-missing'}
            continue

        start = None
        if ref:
            for f in b.GetFootprints():
                if f.GetReference() == ref:
                    for q in f.Pads():
                        if q.GetNumber() == pin:
                            c = q.GetPosition()
                            start = (c.x, c.y)
        if start is None:
            # pick a point in the start fragment
            start = (frags[mi]['pts'][0][0], frags[mi]['pts'][0][1])

        best = None
        for j, fr in enumerate(frags):
            if j == mi:
                continue
            for (x2, y2, l2) in fr['pts']:
                # the start layer(s): the pad's own faces, or the start fragment's layers
                for l1 in {l for (_, _, l) in frags[mi]['pts']}:
                    d = math.hypot(start[0] - x2, start[1] - y2)
                    if best is None or d < best[0]:
                        best = (d, start, (x2, y2), l1, l2, j)
        if best is None:
            print('    no other fragment')
            continue
        d, s, g, l1, l2, j = best
        print('    goal frag %d: %.3f mm  (%.3f,%.3f)[%s]->(%.3f,%.3f)[%s]'
              % (j, d / 1e6, s[0] / 1e6, s[1] / 1e6, b.GetLayerName(l1),
                 g[0] / 1e6, g[1] / 1e6, b.GetLayerName(l2)))

        field = BR.SeqField(b, box, BR.ROUTE_CLEAR)
        margin = 3000000
        rbox = (min(s[0], g[0]) - margin, min(s[1], g[1]) - margin,
                max(s[0], g[0]) + margin, max(s[1], g[1]) + margin)
        ok = False
        for radius in (5, 6):
            path, why = CR.route(field, s, g, net, rbox, [l1], [l2],
                                 deadline_steps=1200000, deadline_s=150.0,
                                 seed_radius=radius)
            if path:
                ok = True
                break
        if not ok:
            print('    NO PATH: %s' % why)
            rep[label] = {'status': 'NO PATH', 'reason': why, 'gap_mm': round(d / 1e6, 3)}
            continue
        ns, nv = apply_path(b, path, net)
        ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
                 for k in range(1, len(path))) / 1e6
        print('    ROUTED %.2f mm, %d seg, %d via' % (ln, ns, nv))
        done.append(label)
        rep[label] = {'status': 'ROUTED', 'gap_mm': round(d / 1e6, 3),
                      'length_mm': round(ln, 2), 'segments': ns, 'vias': nv}

    json.dump(rep, open(os.path.join(B, 'report.json'), 'w'), indent=2)
    if not done:
        print('\nnothing routed -- tree untouched')
        return 1
    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    del b
    subprocess.run(['/usr/bin/python3', '-B',
                    '/home/c08r4d0r/.hermes/cache/scratch/refill_one.py', out],
                   capture_output=True, timeout=900)
    for ext in ('kicad_pro', 'kicad_dru', 'fp-lib-table'):
        s = src.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, out.replace('.kicad_pcb', '.' + ext)], check=False)
    print('\nrouted %d/%d: %s' % (len(done), len(TARGETS), done))
    return 0


if __name__ == '__main__':
    sys.exit(main())
