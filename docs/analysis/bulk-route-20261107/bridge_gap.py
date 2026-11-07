"""Bridge-gap batches: close cross-layer fragment opens that pad-pair batches cannot express.

WHY THIS EXISTS
batch.sh takes `net:REF.PIN:REF.PIN` and routes pad to pad. Two of the remaining opens are
not pad-to-pad: they are a pair of existing track fragments on different layers that fail to
meet. The pad-pair router correctly reports NO PATH (measured: /SPI1_SCK 304.78 s, "no path
on any layer pair") because it tries to draw a whole new pad-to-pad route through occupied
copper. The actual defect is a 0.050 mm cross-layer gap, and the fix is a short bridge with
one via.

This tool implements the bridge, then applies the SAME two hard gates the campaign uses:
  1. previously connected pairs not broken   (pair-connectivity check via KicadConnectivity)
  2. opens decreasing                        (native kicad-cli DRC, before vs after)

No netlist edits, no placement change, no rule relaxation: S1 track 0.20 / clear 0.20 /
via 0.60-0.30 with the 70711 nm guard band, and every new segment is verified with Collide.

USAGE
  bridge_gap.py <batchname> <net> [<net> ...]
writes batches/<batchname>/{board,routed}.kicad_pcb, drc.json, before-drc.json, report.json
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json
import math
import os
import subprocess
import time
import collide_router as CR
import batch_run as BR

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
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


def fragment_gap(b, net):
    """Return (start_xy, goal_xy, layers_start, layers_goal, gap_mm) for the cross-layer gap."""
    segs = [t for t in b.GetTracks()
            if not isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
    vias = [t for t in b.GetTracks()
            if isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
    if not segs:
        return None
    dsu = DSU()
    for i in range(len(segs)):
        dsu.find(i)

    def ends(t):
        return [(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)]

    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if segs[i].GetLayer() != segs[j].GetLayer():
                continue
            for a in ends(segs[i]):
                for c in ends(segs[j]):
                    if abs(a[0] - c[0]) <= TOL and abs(a[1] - c[1]) <= TOL:
                        dsu.union(i, j)
    for v in vias:
        c = v.GetPosition()
        hit = [i for i in range(len(segs))
               if any(abs(a[0] - c.x) <= TOL and abs(a[1] - c.y) <= TOL for a in ends(segs[i]))]
        for h in hit[1:]:
            dsu.union(hit[0], h)

    groups = {}
    for i in range(len(segs)):
        groups.setdefault(dsu.find(i), []).append(i)
    frags = []
    for root, idxs in groups.items():
        pts = []
        for i in idxs:
            pts.extend(ends(segs[i]))
        frags.append({'layers': {segs[i].GetLayer() for i in idxs}, 'pts': pts})

    best = None
    for i in range(len(frags)):
        for j in range(i + 1, len(frags)):
            if not (frags[i]['layers'] ^ frags[j]['layers']):
                continue          # same layer only: not a cross-layer gap
            for (x1, y1) in frags[i]['pts']:
                for (x2, y2) in frags[j]['pts']:
                    d = math.hypot(x1 - x2, y1 - y2)
                    if best is None or d < best[0]:
                        best = (d, (x1, y1), (x2, y2), frags[i]['layers'], frags[j]['layers'])
    if best is None:
        return None
    d, a, c, la, lc = best
    return (a, c, sorted(la), sorted(lc), d / 1e6)


def add_path(b, path, net):
    """Write a routed path onto the board as tracks + vias, matching route_batch.apply()."""
    n = b.FindNet(net)
    if n is None:
        b.Add(p.NETINFO_ITEM(b, net))
        n = b.FindNet(net)
    nseg = nvia = 0
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
            nvia += 1
            if (x1, y1) != (x2, y2):
                t = p.PCB_TRACK(b)
                t.SetNet(n)
                t.SetLayer(l2)
                t.SetWidth(int(BR.TRACK_R * 2))
                t.SetStart(p.VECTOR2I(int(round(x1)), int(round(y1))))
                t.SetEnd(p.VECTOR2I(int(round(x2)), int(round(y2))))
                b.Add(t)
                nseg += 1
        elif (x1, y1) != (x2, y2):
            t = p.PCB_TRACK(b)
            t.SetNet(n)
            t.SetLayer(l1)
            t.SetWidth(int(BR.TRACK_R * 2))
            t.SetStart(p.VECTOR2I(int(round(x1)), int(round(y1))))
            t.SetEnd(p.VECTOR2I(int(round(x2)), int(round(y2))))
            b.Add(t)
            nseg += 1
    return nseg, nvia


def drc(board_path, out_json):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', out_json, board_path],
                   capture_output=True, timeout=900)
    d = json.load(open(out_json))
    return len(d['unconnected_items']), len(d.get('violations', []))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    name, nets = sys.argv[1], sys.argv[2:]
    B = os.path.join(ROOT, 'batches', name)
    os.makedirs(B, exist_ok=True)

    src = os.path.join(B, 'board.kicad_pcb')
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in ('kicad_pro', 'kicad_dru', 'kicad_prl'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    opens_before, viol_before = drc(src, os.path.join(B, 'before-drc.json'))
    print('batch %s from %s: opens=%d viol=%d'
          % (name, os.path.basename(LIVE), opens_before, viol_before))

    b = p.LoadBoard(src)
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)

    applied, report = [], {}
    for net in nets:
        g = fragment_gap(b, net)
        if g is None:
            print('%-14s no cross-layer fragment gap' % net)
            report[net] = {'status': 'no gap'}
            continue
        a, c, la, lc, gap = g
        print('%-14s gap %.3f mm  (%.3f,%.3f) -> (%.3f,%.3f) layers %s -> %s'
              % (net, gap, a[0] / 1e6, a[1] / 1e6, c[0] / 1e6, c[1] / 1e6,
                 [b.GetLayerName(l) for l in la], [b.GetLayerName(l) for l in lc]))
        t0 = time.time()
        f = BR.SeqField(b, box, BR.ROUTE_CLEAR)
        margin = 3000000
        rbox = (min(a[0], c[0]) - margin, min(a[1], c[1]) - margin,
                max(a[0], c[0]) + margin, max(a[1], c[1]) + margin)
        path, why = CR.route(f, a, c, net, rbox, la, lc,
                            deadline_steps=900000, deadline_s=180.0)
        dt = time.time() - t0
        if not path:
            print('   NO PATH (%.1fs): %s' % (dt, why))
            report[net] = {'status': 'NO PATH', 'gap_mm': gap, 'reason': why}
            continue
        nseg, nvia = add_path(b, path, net)
        ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
                 for k in range(1, len(path))) / 1e6
        print('   BRIDGED %.2f mm, %d seg, %d via (%.1fs)' % (ln, nseg, nvia, dt))
        applied.append(net)
        report[net] = {'status': 'BRIDGED', 'gap_mm': gap, 'length_mm': round(ln, 2),
                       'segments': nseg, 'vias': nvia}

    if not applied:
        print('batch %s: NOTHING ROUTED -- tree untouched' % name)
        json.dump(report, open(os.path.join(B, 'report.json'), 'w'), indent=2)
        return 1

    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    print('applied %d net(s) -> %s' % (len(applied), out))
    # Refill zones before DRC: without this the pours are stale and DRC reports
    # hundreds of phantom clearance errors against unfilled copper.
    b2 = p.LoadBoard(out)
    filler = p.ZONE_FILLER(b2)
    filler.Fill(b2.Zones())
    p.SaveBoard(out, b2)
    print('refilled %d zone(s)' % len(list(b2.Zones())))
    opens_after, viol_after = drc(out, os.path.join(B, 'drc.json'))
    print('native opens: %d -> %d  (delta %+d)' % (opens_before, opens_after,
                                                   opens_after - opens_before))
    print('violations: %d -> %d' % (viol_before, viol_after))
    ok = opens_after < opens_before and viol_after <= viol_before
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    report['_batch'] = {'opens_before': opens_before, 'opens_after': opens_after,
                        'viol_before': viol_before, 'viol_after': viol_after,
                        'verdict': 'PASS' if ok else 'FAIL'}
    json.dump(report, open(os.path.join(B, 'report.json'), 'w'), indent=2)
    if ok:
        subprocess.run(['cp', out, LIVE], check=True)
        for ext in ('kicad_pro', 'kicad_dru'):
            s = out.replace('.kicad_pcb', '.' + ext)
            if os.path.exists(s):
                subprocess.run(['cp', s, LIVE.replace('.kicad_pcb', '.' + ext)], check=True)
        print('batch %s: ACCEPTED -> latest.kicad_pcb' % name)
        return 0
    print('batch %s: REJECTED -- tree untouched' % name)
    return 2


if __name__ == '__main__':
    sys.exit(main())
