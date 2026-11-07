"""Legal-via-site test for the remaining cross-layer opens, on the proven router field.

Reuses the tested SeqField (2 mm spatial hash, memoised tests, Collide-only predicate) and
adds an explanation layer: when a site is refused, name the object that refused it. A
refusal that cannot be explained is not a measurement.

S1 rules, unchanged: via land 0.600 mm, drill 0.300 mm, clearance 0.200 mm, plus the
70711 nm guard band so a point-passing site is legally clear by construction.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json
import time
import batch_run as BR
import collide_router as CR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
OUT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/via-feasibility.json'
HALO = 1200000
STEP = 100000
DEADLINE = 90.0
TARGETS = ['/SPI1_MOSI', '/SPI1_SCK', '/W2_SOLAR_N', '/W3_SOLAR_N', '/VSCAP']


def board_bbox(b):
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    m = 500000
    return (bb.GetLeft() - m, bb.GetTop() - m, bb.GetRight() + m, bb.GetBottom() + m)


def why_blocked(f, x, y, net):
    """Name the first object that blocks a via at (x,y), using the real Obs records."""
    v = p.VECTOR2I(x, y)
    land = f.disc(v, CR.VIA_R)
    for l in CR.CU_ALL:
        for o in f.buckets[l].query(x, y, CR.VIA_R + f.clear):
            if o.net == net:
                continue
            if p.SHAPE.Collide(land, o.sh, f.clear):
                return '%s %s' % (o.kind, o.name)
    return None


def main():
    b = p.LoadBoard(BOARD)
    bb = board_bbox(b)
    f = BR.SeqField(b, bb, BR.ROUTE_CLEAR)
    print('field ready (guard %d nm)' % BR.GUARD)

    report = {}
    for net in TARGETS:
        t0 = time.time()
        segs = [t for t in b.GetTracks()
                if not isinstance(t, p.PCB_VIA) and t.GetNetname() == net]
        if not segs:
            print('%-14s no tracks on board' % net)
            continue
        endpoints = []
        for t in segs:
            for q in (t.GetStart(), t.GetEnd()):
                endpoints.append((q.x, q.y))
        uniq = list(dict.fromkeys(endpoints))
        step = max(1, len(uniq) // 24)
        seeds = uniq[::step][:24]

        legal = []
        blockers = {}
        tested = 0
        timed_out = False
        for (px, py) in seeds:
            if len(legal) >= 6 or timed_out:
                break
            for dx in range(-HALO, HALO + 1, STEP):
                for dy in range(-HALO, HALO + 1, STEP):
                    x, y = px + dx, py + dy
                    tested += 1
                    if f.via_ok(x, y, net):
                        legal.append((x, y))
                        if len(legal) >= 6:
                            break
                    else:
                        w = why_blocked(f, x, y, net)
                        if w:
                            blockers[w] = blockers.get(w, 0) + 1
                if len(legal) >= 6:
                    break
            if time.time() - t0 > DEADLINE:
                timed_out = True

        top = sorted(blockers.items(), key=lambda kv: -kv[1])[:5]
        print('\n=== %s' % net)
        print('  %d segments, %d unique endpoints, %d sites tested%s'
              % (len(segs), len(uniq), tested, ' (DEADLINE)' if timed_out else ''))
        if legal:
            for (x, y) in legal[:6]:
                print('    LEGAL (%.3f, %.3f)' % (x / 1e6, y / 1e6))
        else:
            print('    NO LEGAL SITE. blockers: %s' % top)
        report[net] = {'segments': len(segs), 'tested': tested, 'legal': len(legal),
                       'sites': [[round(x / 1e6, 3), round(y / 1e6, 3)] for (x, y) in legal],
                       'top_blockers': top, 'timed_out': timed_out}

    json.dump(report, open(OUT, 'w'), indent=2)
    print('\n=== VERDICT (S1, unchanged)')
    for k, v in report.items():
        print('  %-14s %s' % (k, ('CLOSABLE: %d legal via sites' % v['legal']) if v['legal']
                              else 'NO LEGAL VIA SITE (%d tested)' % v['tested']))


if __name__ == '__main__':
    main()
