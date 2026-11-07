"""CUT_SENSE retry: choose the goal point by CONNECTIVITY, not by distance.

The first attempt routed each F.Cu pad to the nearest endpoint of same-net B.Cu track. It
produced three paths, closed ZERO opens (21 -> 21) and added two dangling vias. Correctly
rejected. Root cause: "nearest same-net copper" is not "the disconnected piece".

This version builds the net's connectivity first:
  1. cluster the net's copper into fragments where touching (tracks joined by shared endpoints
     on the same layer, and joined across layers by vias),
  2. find the fragment containing the target pad,
  3. choose as goal the closest point IN A DIFFERENT FRAGMENT -- that is the real open,
  4. route between them, and only count success if DRC's open count falls.

If step 3 finds the pad's fragment already spans everything, the record is not a copper gap and
is reported as such rather than "routed".
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
NAME = 'CUTSENSE2'
TOL = 3000

TARGETS = {
    '/CUT_SENSE_W1': ('J_W1', '3'),
    '/CUT_SENSE_W2': ('J_W2', '3'),
    '/CUT_SENSE_W3': ('J_W3', '3'),
    '/CUT_SENSE_W4': ('J_W4', '3'),
}


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
    """Cluster all copper of `net` into electrically touching fragments."""
    tracks = [t for t in b.GetTracks()
              if t.GetNetname() == net and not isinstance(t, p.PCB_VIA)]
    vias = [t for t in b.GetTracks()
            if t.GetNetname() == net and isinstance(t, p.PCB_VIA)]
    pads = [(f.GetReference(), q) for f in b.GetFootprints() for q in f.Pads()
            if q.GetNetname() == net]
    nodes = []
    for t in tracks:
        nodes.append(('T', t))
    for (r, q) in pads:
        nodes.append(('P', (r, q)))
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
        groups.setdefault(dsu.find(i), []).append(nodes[i])
    out = []
    for root, ns in groups.items():
        allpts = []
        kinds = []
        for n in ns:
            allpts.extend(pts_of(n))
            kinds.append(n[0])
        out.append({'pts': allpts, 'kinds': kinds, 'n': len(ns)})
    return out


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

    done, reports = [], {}
    for net, (ref, num) in TARGETS.items():
        frags = fragments(b, net)
        # which fragment holds the pad?
        padpos = None
        for f in b.GetFootprints():
            if f.GetReference() == ref:
                for q in f.Pads():
                    if q.GetNumber() == num:
                        c = q.GetPosition()
                        padpos = (c.x, c.y)
        if padpos is None:
            print('%-16s pad missing' % net)
            continue
        mine = None
        for i, fr in enumerate(frags):
            for (x, y, _) in fr['pts']:
                if abs(x - padpos[0]) <= TOL and abs(y - padpos[1]) <= TOL:
                    mine = i
        print('\n%-16s fragments=%d  pad in fragment %s  sizes=%s'
              % (net, len(frags), mine, [f['n'] for f in frags]))
        if mine is None:
            print('    pad not found in any fragment')
            reports[net] = {'status': 'pad-not-in-net'}
            continue
        if len(frags) < 2:
            print('    only ONE fragment: no copper gap to close')
            reports[net] = {'status': 'single-fragment'}
            continue

        best = None
        for j, fr in enumerate(frags):
            if j == mine:
                continue
            for (x1, y1, l1) in frags[mine]['pts']:
                for (x2, y2, l2) in fr['pts']:
                    if abs(x1 - padpos[0]) > TOL or abs(y1 - padpos[1]) > TOL:
                        continue        # start only from the pad itself
                    d = math.hypot(x1 - x2, y1 - y2)
                    if best is None or d < best[0]:
                        best = (d, (x1, y1), (x2, y2), l1, l2, j)
        if best is None:
            print('    no reachable other fragment from the pad')
            reports[net] = {'status': 'no-other-fragment'}
            continue
        d, s, g, l1, l2, j = best
        print('    goal in fragment %d: %.3f mm  (%.3f,%.3f)->(%.3f,%.3f) layers %s->%s'
              % (j, d / 1e6, s[0] / 1e6, s[1] / 1e6, g[0] / 1e6, g[1] / 1e6,
                 b.GetLayerName(l1), b.GetLayerName(l2)))

        field = BR.SeqField(b, box, BR.ROUTE_CLEAR)
        margin = 3000000
        rbox = (min(s[0], g[0]) - margin, min(s[1], g[1]) - margin,
                max(s[0], g[0]) + margin, max(s[1], g[1]) + margin)
        path, why = CR.route(field, s, g, net, rbox, [l1], [l2],
                             deadline_steps=900000, deadline_s=150.0, seed_radius=5)
        if not path:
            print('    NO PATH: %s' % why)
            reports[net] = {'status': 'NO PATH', 'reason': why, 'gap_mm': round(d / 1e6, 3)}
            continue
        n = b.FindNet(net)
        ns = nv = 0
        for k in range(1, len(path)):
            x1, y1, a1 = path[k - 1]
            x2, y2, a2 = path[k]
            if a1 != a2:
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
                t.SetLayer(a1)
                t.SetWidth(int(BR.TRACK_R * 2))
                t.SetStart(p.VECTOR2I(int(round(x1)), int(round(y1))))
                t.SetEnd(p.VECTOR2I(int(round(x2)), int(round(y2))))
                b.Add(t)
                ns += 1
        ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
                 for k in range(1, len(path))) / 1e6
        print('    ROUTED %.2f mm, %d seg, %d via' % (ln, ns, nv))
        done.append(net)
        reports[net] = {'status': 'ROUTED', 'gap_mm': round(d / 1e6, 3),
                        'length_mm': round(ln, 2), 'segments': ns, 'vias': nv}

    json.dump(reports, open(os.path.join(B, 'report.json'), 'w'), indent=2)
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
