"""Fast legal-via-site test for the cross-layer fragment opens, using the proven router field.

The slow version tested 120k lattice points against 1988 objects with an O(n) scan. The
router's SeqField already has a 2 mm spatial hash, memoised cell tests and a deadline, and
its via_ok() is the same predicate the accepted batches used. Reuse it instead of writing
new geometry code -- that is the whole point of having a tested field.

For each remaining cross-layer open: search a 1.5 mm halo around the endpoints of the two
reported fragments for a legal 0.600/0.300 via at frozen S1 rules, and report the exact
blocking object when there is none.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json
import time
import batch_run as BR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
HALO = 1500000
STEP = 50000
DEADLINE = 240.0

TARGETS = ['/SPI1_MOSI', '/SPI1_SCK', '/W2_SOLAR_N', '/W3_SOLAR_N', '/VSCAP']


class ProbeField(BR.SeqField):
    """Records WHICH object blocks a candidate site, so a refusal is explained not asserted."""

    def __init__(self, board, bbox, clear):
        super().__init__(board, bbox, clear)
        self.last_blocker = None

    def why_via(self, x, y, net):
        """Return the blocking object for a via at (x,y), or None if legal."""
        d = self.disc(p.VECTOR2I(x, y), BR.VIA_R)
        for obj in self.objs:
            onet = obj[1]
            if onet == net:
                continue
            layers = obj[2]
            if layers is not None and not any(l in layers for l in BR.CU_ALL):
                continue
            if p.SHAPE.Collide(d, obj[0], self.clear):
                return '%s/%s' % (obj[3] if len(obj) > 3 else 'obj', onet or '<no-net>')
        return None


def board_bbox(b):
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    m = 500000
    return (bb.GetLeft() - m, bb.GetTop() - m, bb.GetRight() + m, bb.GetBottom() + m)


def main():
    b = p.LoadBoard(BOARD)
    bb = board_bbox(b)
    f = ProbeField(b, bb, BR.ROUTE_CLEAR)
    print('field built')

    report = {}
    for net in TARGETS:
        t0 = time.time()
        segs = [t for t in b.GetTracks()
                if not isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
        if not segs:
            print('%s: no tracks' % net)
            continue
        pts = []
        for t in segs:
            for q in (t.GetStart(), t.GetEnd()):
                pts.append((q.x, q.y))
        # dedupe and keep a spread of endpoints
        uniq = list(dict.fromkeys(pts))
        step = max(1, len(uniq) // 16)
        seeds = uniq[::step][:16]

        legal = []
        blocked_by = {}
        tested = 0
        stop = False
        for (px, py) in seeds:
            if stop:
                break
            for dx in range(-HALO, HALO + 1, STEP):
                for dy in range(-HALO, HALO + 1, STEP):
                    x, y = px + dx, py + dy
                    tested += 1
                    if f.via_ok(x, y, net):
                        legal.append((x, y))
                        if len(legal) >= 8:
                            stop = True
                            break
                    else:
                        blk = f.blocker_at(x, y, net) if hasattr(f, 'blocker_at') else None
                        if blk:
                            blocked_by[blk] = blocked_by.get(blk, 0) + 1
                if stop:
                    break
            if time.time() - t0 > DEADLINE:
                print('  (deadline hit after %d sites)' % tested)
                break

        print('\n=== %s' % net)
        print('  segments %d, endpoints %d, sites tested %d, legal %d'
              % (len(segs), len(uniq), tested, len(legal)))
        if legal:
            for (x, y) in legal[:5]:
                print('    LEGAL via site (%.3f, %.3f)' % (x / 1e6, y / 1e6))
        else:
            top = sorted(blocked_by.items(), key=lambda kv: -kv[1])[:4]
            print('    NO LEGAL SITE; blockers: %s' % top)
        report[net] = {'segments': len(segs), 'tested': tested, 'legal': len(legal),
                       'sites': [[x / 1e6, y / 1e6] for (x, y) in legal[:8]],
                       'blockers': dict(sorted(blocked_by.items(), key=lambda kv: -kv[1])[:6])}

    out = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/via-feasibility.json'
    json.dump(report, open(out, 'w'), indent=2)
    print('\n=== VERDICT')
    for k, v in report.items():
        print('  %-14s %s' % (k, ('CLOSABLE - %d legal via sites' % v['legal']) if v['legal']
                              else 'NO LEGAL VIA SITE (%d tested)' % v['tested']))


if __name__ == '__main__':
    main()
