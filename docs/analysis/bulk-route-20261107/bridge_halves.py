"""Bridge the ACTUAL disconnection in /SPI1_SCK: the 28.9 mm gap between frag0 and frag1.

BRIDGE1/BRIDGE2 both failed for the same reason and it was my bug, not the board's: the
fragment finder picked the globally minimum gap (0.050 mm between two small stubs near a
pad) instead of the gap that separates the net's two substantial halves. Bridging those two
stubs left the open count unchanged (22 -> 22) both times, correctly.

Measured fragment map for /SPI1_SCK on the live board:
  frag0  12 segs  F.Cu+B.Cu
  frag1  17 segs  F.Cu+B.Cu
  frag2   1 seg   F.Cu       (a 1.90 mm stub)
  frag3   1 seg   B.Cu       (a 2.75 mm stub)
  frag1-frag3  0.100 mm   (stub-to-half, not the open)
  frag2-frag3  0.050 mm   (stub-to-stub, not the open)
  frag0-frag1 28.939 mm   <-- THE OPEN

So: bridge frag0 to frag1, the two halves that carry 39.60 mm and 46.23 mm of the net.
Same two hard gates as every accepted batch: opens decrease, no connected pair broken.
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
NET = os.environ.get('BRIDGE_NET', '/SPI1_SCK')
NAME = os.environ.get('BRIDGE_TAG', 'BRIDGE3')


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
    segs = [t for t in b.GetTracks()
            if not isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
    vias = [t for t in b.GetTracks()
            if isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
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
    out = []
    for root, idxs in groups.items():
        pts = []
        ln = 0.0
        for i in idxs:
            pts.extend(ends(segs[i]))
            ln += math.hypot(segs[i].GetEnd().x - segs[i].GetStart().x,
                             segs[i].GetEnd().y - segs[i].GetStart().y) / 1e6
        pts3 = []
        for i in idxs:
            for q in ends(segs[i]):
                pts3.append((q[0], q[1], segs[i].GetLayer()))
        out.append({'idx': idxs, 'pts': pts, 'pts3': pts3, 'length_mm': ln,
                    'layers': sorted({segs[i].GetLayer() for i in idxs})})
    return out


def add_path(b, path, net, stub_from=None, stub_to=None):
    n = b.FindNet(net)
    if n is None:
        b.Add(p.NETINFO_ITEM(b, net))
        n = b.FindNet(net)
    nseg = nvia = 0
    # Close the lattice-snap gap: the router's first and last points sit on its grid, not on the
    # exact endpoints it was asked to join. Add a stub from each exact endpoint to the path end on
    # the same layer, only when they differ. Measured failure this fixes: W3BRIDGE and MOSIB3 both
    # left exactly 0.2828 mm (one diagonal lattice step) unconnected after a successful route.
    if stub_from is not None and path:
        ex, ey, el = stub_from
        if (ex, ey) != (path[0][0], path[0][1]) and el == path[0][2]:
            t = p.PCB_TRACK(b)
            t.SetNet(n)
            t.SetLayer(el)
            t.SetWidth(int(BR.TRACK_R * 2))
            t.SetStart(p.VECTOR2I(int(round(ex)), int(round(ey))))
            t.SetEnd(p.VECTOR2I(int(round(path[0][0])), int(round(path[0][1]))))
            b.Add(t)
            nseg += 1
    if stub_to is not None and path:
        ex, ey, el = stub_to
        if (ex, ey) != (path[-1][0], path[-1][1]) and el == path[-1][2]:
            t = p.PCB_TRACK(b)
            t.SetNet(n)
            t.SetLayer(el)
            t.SetWidth(int(BR.TRACK_R * 2))
            t.SetStart(p.VECTOR2I(int(round(path[-1][0])), int(round(path[-1][1]))))
            t.SetEnd(p.VECTOR2I(int(round(ex)), int(round(ey))))
            b.Add(t)
            nseg += 1
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


def drc(board, out):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', out, board],
                   capture_output=True, timeout=1200)
    d = json.load(open(out))
    errs = [v for v in d.get('violations', []) if v.get('severity') == 'error']
    return len(d['unconnected_items']), len(d.get('violations', [])), len(errs)


def main():
    B = os.path.join(ROOT, 'batches', NAME)
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in ('kicad_pro', 'kicad_dru'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    ob, vb, eb = drc(src, os.path.join(B, 'before-drc.json'))
    print('batch %s from live: opens=%d viol=%d errors=%d' % (NAME, ob, vb, eb))

    b = p.LoadBoard(src)
    frags = fragments(b, NET)
    print('\n%s fragments:' % NET)
    for i, f in enumerate(frags):
        print('  frag%d  %2d segs  %6.2f mm  layers %s'
              % (i, len(f['idx']), f['length_mm'],
                 [b.GetLayerName(l) for l in f['layers']]))

    # Pick the CLOSEST pair of endpoints BETWEEN the two substantial halves, preferring pairs
    # that sit on the SAME layer. Measured failure this fixes: taking the bare minimum distance
    # chose an F.Cu endpoint on one side and a B.Cu endpoint on the other, 26.800 mm apart, and
    # the router correctly reported NO PATH in 0.4 s. The genuinely closable pair was
    # B.Cu->B.Cu at (11.050,42.250)-(10.950,15.450) -- the same net, same layer, 26.8 mm, and
    # routing it as a single-layer run is legal. Preferring same-layer pairs finds that without
    # needing a via, and only falls back to mixed-layer when no same-layer pair exists.
    substantial = sorted(frags, key=lambda f: -f['length_mm'])[:2]
    same_layer = []
    mixed_layer = []
    lay_of = {}
    for f in substantial:
        for (x, y, l) in f['pts3'] if 'pts3' in f else []:
            lay_of[(x, y)] = l
    for (x1, y1) in substantial[0]['pts']:
        for (x2, y2) in substantial[1]['pts']:
            d = math.hypot(x1 - x2, y1 - y2)
            l1 = lay_of.get((x1, y1))
            l2 = lay_of.get((x2, y2))
            rec = (d, (x1, y1), (x2, y2), l1, l2)
            if l1 is not None and l1 == l2:
                same_layer.append(rec)
            else:
                mixed_layer.append(rec)
    same_layer.sort()
    mixed_layer.sort()
    cands = same_layer + mixed_layer
    if not cands:
        print('NO candidate endpoints between the two halves')
        return 2
    d, a, c, l1, l2 = cands[0]
    print('\nBRIDGING the two substantial halves: %.3f mm%s'
          % (d / 1e6, ' (same layer %s)' % b.GetLayerName(l1) if l1 == l2 else ''))
    print('  from (%.3f, %.3f) to (%.3f, %.3f)'
          % (a[0] / 1e6, a[1] / 1e6, c[0] / 1e6, c[1] / 1e6))

    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    f = BR.SeqField(b, box, BR.ROUTE_CLEAR)

    la = [l for l in substantial[0]['layers']]
    lc = [l for l in substantial[1]['layers']]
    margin = 4000000
    rbox = (min(a[0], c[0]) - margin, min(a[1], c[1]) - margin,
            max(a[0], c[0]) + margin, max(a[1], c[1]) + margin)
    t0 = time.time()
    path, why = CR.route(f, a, c, NET, rbox, la, lc,
                         deadline_steps=900000, deadline_s=300.0)
    dt = time.time() - t0
    if not path:
        print('NO PATH in %.1fs: %s' % (dt, why))
        json.dump({'status': 'NO PATH', 'gap_mm': d / 1e6, 'reason': why},
                  open(os.path.join(B, 'report.json'), 'w'), indent=2)
        print('batch %s: NOTHING ROUTED -- tree untouched' % NAME)
        return 1

    # pass the EXACT endpoints so the lattice-snap gap is closed with stubs
    _la = l1 if l1 is not None else (substantial[0]['layers'][0])
    _lc = l2 if l2 is not None else (substantial[1]['layers'][0])
    nseg, nvia = add_path(b, path, NET,
                          stub_from=(a[0], a[1], _la),
                          stub_to=(c[0], c[1], _lc))
    ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
             for k in range(1, len(path))) / 1e6
    print('BRIDGED %.2f mm, %d seg, %d via (%.1fs)' % (ln, nseg, nvia, dt))

    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    b2 = p.LoadBoard(out)
    p.ZONE_FILLER(b2).Fill(b2.Zones())
    p.SaveBoard(out, b2)
    print('refilled %d zone(s)' % len(list(b2.Zones())))

    # The AFTER DRC must see the PROJECT rules, not KiCad's defaults. DRC resolves the ruleset
    # from a same-stem .kicad_dru; without it an identical board scored 16 phantom
    # copper_edge_clearance errors on pads the project explicitly allows on Edge.Cuts.
    # fp-lib-table matters too: without it lib_footprint_issues jumps (library registration).
    for ext in ('kicad_pro', 'kicad_dru'):
        s = os.path.join(B, 'board.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, out.replace('.kicad_pcb', '.' + ext)], check=True)
    ft = os.path.join(B, 'fp-lib-table')
    if not os.path.exists(ft):
        live_ft = os.path.join(ROOT, 'fp-lib-table')
        if os.path.exists(live_ft):
            subprocess.run(['cp', live_ft, ft], check=True)
    print('sidecars staged onto the routed candidate')

    oa, va, ea = drc(out, os.path.join(B, 'drc.json'))
    print('\nnative opens: %d -> %d  (delta %+d)' % (ob, oa, oa - ob))
    print('violations: %d -> %d   errors: %d -> %d' % (vb, va, eb, ea))
    ok = oa < ob and va <= vb
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    json.dump({'status': 'BRIDGED' if ok else 'FAIL', 'gap_mm': round(d / 1e6, 3),
               'length_mm': round(ln, 2), 'segments': nseg, 'vias': nvia,
               'opens_before': ob, 'opens_after': oa,
               'viol_before': vb, 'viol_after': va, 'errors_after': ea,
               'verdict': 'PASS' if ok else 'FAIL'},
              open(os.path.join(B, 'report.json'), 'w'), indent=2)
    if ok:
        subprocess.run(['cp', out, LIVE], check=True)
        for ext in ('kicad_pro', 'kicad_dru'):
            s = out.replace('.kicad_pcb', '.' + ext)
            if os.path.exists(s):
                subprocess.run(['cp', s, LIVE.replace('.kicad_pcb', '.' + ext)], check=True)
        print('batch %s: ACCEPTED -> latest.kicad_pcb' % NAME)
        return 0
    print('batch %s: REJECTED -- tree untouched' % NAME)
    return 2


if __name__ == '__main__':
    sys.exit(main())
