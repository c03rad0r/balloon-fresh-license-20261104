"""Can the 5 remaining cross-layer fragment opens be closed with a legal via?

These are the opens DRC reports as track-vs-track or pad-vs-track across layers. Each needs
a plated transition. Earlier work found "no legal 0.600/0.300 via site" for the R_DIV2
region, but that was one pocket; these five have never been tested individually on the live
board.

For each open: take the endpoints of the two reported fragments, search a halo around each
for a legal via site at frozen S1 rules (0.600 mm land, 0.300 mm drill, 0.200 mm clearance),
and report the best site plus the exact blocking obstacle. Decision primitive is
SHAPE::Collide per project rule -- SHAPE::Distance is not trusted on this board.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
DRC = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/batches/SOLARPAIR/drc.json'
CLEAR = 200000
VIA_LAND = 600000
VIA_DRILL = 300000
HALO = 2500000        # 2.5 mm search halo
STEP = 50000          # 50 um lattice

# the five cross-layer fragment opens, by net
TARGETS = ['/SPI1_MOSI', '/SPI1_SCK', '/W2_SOLAR_N', '/W3_SOLAR_N']


def main():
    b = p.LoadBoard(BOARD)
    d = json.load(open(DRC))

    # gather every copper object once
    objs = []          # (netname, shape, layer, kind)
    for t in b.GetTracks():
        if isinstance(t, p.PCB_VIA):
            for l in (p.F_Cu, p.B_Cu):
                objs.append((t.GetNetname(), t.GetEffectiveShape(l), l, 'via'))
        else:
            l = t.GetLayer()
            objs.append((t.GetNetname(), t.GetEffectiveShape(l), l, 'track'))
    for f in b.GetFootprints():
        for q in f.Pads():
            for l in (p.F_Cu, p.B_Cu):
                if q.IsOnLayer(l):
                    objs.append((q.GetNetname(), q.GetEffectiveShape(l), l, 'pad'))
    print('copper objects indexed: %d' % len(objs))

    # which opens involve each target net
    want = {}
    for i, u in enumerate(d['unconnected_items']):
        ds = [it.get('description', '') for it in u.get('items', [])]
        blob = ' '.join(ds)
        for net in TARGETS:
            if net in blob:
                want.setdefault(net, []).append((i, ds))
    print('opens per target net: %s' % {k: len(v) for k, v in want.items()})

    def via_ok(x, y, net):
        """Is a 0.600/0.300 via at (x,y) legal against all foreign copper on F and B?"""
        land = p.SHAPE_CIRCLE(p.VECTOR2I(x, y), VIA_LAND // 2)
        blocker = None
        for onet, shape, layer, kind in objs:
            if onet == net:
                continue
            if layer not in (p.F_Cu, p.B_Cu):
                continue
            if p.SHAPE.Collide(land, shape, CLEAR):
                blocker = '%s/%s' % (kind, onet or '<no-net>')
                return False, blocker
        # also drill-to-hole
        for t in b.GetTracks():
            if isinstance(t, p.PCB_VIA):
                c = t.GetPosition()
                if abs(c.x - x) < VIA_DRILL and abs(c.y - y) < VIA_DRILL:
                    dist = ((c.x - x) ** 2 + (c.y - y) ** 2) ** 0.5
                    if dist < VIA_DRILL:
                        return False, 'via-hole-overlap'
        for f in b.GetFootprints():
            for q in f.Pads():
                if not q.HasHole():
                    continue
                c = q.GetPosition()
                if abs(c.x - x) > 1200000 or abs(c.y - y) > 1200000:
                    continue
                if q.GetNetname() == net:
                    continue
                dist = ((c.x - x) ** 2 + (c.y - y) ** 2) ** 0.5
                if dist < VIA_DRILL + (q.GetDrillSize().x // 2) + 250000:
                    return False, 'hole-to-hole %s' % q.GetNumber()
        return True, None

    report = {}
    for net, lst in want.items():
        # endpoint coordinates of this net's fragments
        pts = []
        for t in b.GetTracks():
            if t.GetNetname() != net or isinstance(t, p.PCB_VIA):
                continue
            for q in (t.GetStart(), t.GetEnd()):
                pts.append((q.x, q.y, b.GetLayerName(t.GetLayer())))
        print('\n=== %s : %d fragment endpoint(s)' % (net, len(pts)))
        best = None
        legal = 0
        tested = 0
        # search a halo around each endpoint, on a coarse lattice
        seeds = pts[::max(1, len(pts) // 12)][:12]
        for (px, py, pl) in seeds:
            for dx in range(-HALO, HALO + 1, STEP):
                for dy in range(-HALO, HALO + 1, STEP):
                    x, y = px + dx, py + dy
                    tested += 1
                    ok, blk = via_ok(x, y, net)
                    if ok:
                        legal += 1
                        if best is None:
                            best = (x, y)
        print('  tested %d sites, legal %d' % (tested, legal))
        if best:
            print('  BEST LEGAL SITE (%.3f, %.3f)' % (best[0] / 1e6, best[1] / 1e6))
        else:
            # report what blocks the single nearest candidate
            px, py, pl = seeds[0]
            ok, blk = via_ok(px, py, net)
            print('  NO LEGAL SITE; at first endpoint blocked by: %s' % blk)
        report[net] = {'tested': tested, 'legal': legal,
                       'best': None if not best else [best[0] / 1e6, best[1] / 1e6]}

    out = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/via-feasibility.json'
    json.dump(report, open(out, 'w'), indent=2)
    print('\nverdict per net:')
    for k, v in report.items():
        print('  %-14s %s' % (k, 'CLOSABLE via at (%s)' % v['best'] if v['best']
                              else 'NO LEGAL VIA SITE (%d tested)' % v['tested']))


if __name__ == '__main__':
    main()
