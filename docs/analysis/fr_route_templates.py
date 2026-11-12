"""Extract freerouting's legal routes for the 4 nets it closed, and check them against C10.

The freerouting candidate is refused as a whole, but only because of WHERE some of its copper sits.
Its routes for /CUT_SENSE_W1, /W1_SOLAR_N, /W1_SOLAR_P and /W3_SOLAR_N are the first evidence all
campaign that those opens are closable at full S1 -- two independent routers plus this one all call
the OTHER four pads trapped, but these four were closed.

So the question is not "is freerouting right" but "is each individual segment of those four routes
legal". If a route for a net stays outside the C10 window entirely, that route is a usable template
and can be reproduced.

This script does that per net: collect every segment and via ADDED relative to the live board, then
classify each one as INSIDE or OUTSIDE the frozen window x 8.00-11.20, y 41.00-44.20.

A net whose added copper is entirely outside C10 is a candidate template. A net with any copper inside
C10 must have that portion re-routed, which is real work and not a copy.
"""

import pcbnew as p

UM = 1_000_000.0
BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
CAND = BASE + '/batches/FREEROUTING_WIDE/routed.kicad_pcb'

C10 = (8.00, 41.00, 11.20, 44.20)
TARGETS = ['/CUT_SENSE_W1', '/W1_SOLAR_N', '/W1_SOLAR_P', '/W3_SOLAR_N']


def segs(board, nets):
    """(net, layer, x1, y1, x2, y2, width, is_via) for tracks/vias on the given nets."""
    b = p.LoadBoard(board)
    out = []
    for t in b.GetTracks():
        n = str(t.GetNetname())
        if n not in nets:
            continue
        s, e = t.GetStart(), t.GetEnd()
        out.append((n, b.GetLayerName(t.GetLayer()),
                    s.x / UM, s.y / UM, e.x / UM, e.y / UM,
                    t.GetWidth() / UM, t.Type() == p.PCB_VIA_T))
    return out


def key(rec):
    """Round to nm so live and candidate records with the same geometry match exactly."""
    n, lay, x1, y1, x2, y2, w, v = rec
    return (n, lay, round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6), round(w, 6), v)


def inside(rec, win):
    x0, y0, x1, y1 = win
    _, _, ax, ay, bx, by, _, _ = rec
    return (x0 <= ax <= x1 and y0 <= ay <= y1) or (x0 <= bx <= x1 and y0 <= by <= y1)


live = segs(LIVE, set(TARGETS))
cand = segs(CAND, set(TARGETS))
live_keys = {key(r) for r in live}

added = [r for r in cand if key(r) not in live_keys]

print('=== copper freerouting ADDED on the 4 nets it closed ===')
print('  live segments on those nets : %d' % len(live))
print('  candidate segments          : %d' % len(cand))
print('  ADDED                       : %d' % len(added))

per_net = {}
for r in added:
    per_net.setdefault(r[0], []).append(r)

print()
print('%-16s %5s %5s %-10s %s' % ('NET', 'add', 'inC10', 'VERDICT', 'layers'))
print('-' * 78)
templates, needs_work = [], []
for n in TARGETS:
    rs = per_net.get(n, [])
    ins = [r for r in rs if inside(r, C10)]
    lays = sorted({r[1] for r in rs})
    if not rs:
        print('%-16s %5d %5s %-10s %s' % (n, 0, '-', 'NOT ROUTED', ''))
        continue
    verdict = 'TEMPLATE' if not ins else 'NEEDS WORK'
    (templates if not ins else needs_work).append(n)
    print('%-16s %5d %5d %-10s %s' % (n, len(rs), len(ins), verdict, ','.join(lays)))

print()
print('=== TEMPLATES (added copper entirely outside C10) ===')
for n in templates:
    print('  %s' % n)
if not templates:
    print('  none')

print()
print('=== NEEDS RE-ROUTING (copper inside the frozen window) ===')
for n in needs_work:
    rs = per_net.get(n, [])
    ins = [r for r in rs if inside(r, C10)]
    print('  %s : %d of %d segments inside C10' % (n, len(ins), len(rs)))
    # where do they sit, and how much of the route is affected
    tot = sum(abs(r[4] - r[2]) + abs(r[5] - r[3]) for r in rs)
    aff = sum(abs(r[4] - r[2]) + abs(r[5] - r[3]) for r in ins)
    print('      %.2f of %.2f mm of added copper is in the frozen window' % (aff, tot))
    for r in ins[:6]:
        print('      %-10s %s (%.3f,%.3f)->(%.3f,%.3f) w%.3f' % (r[1], 'VIA' if r[7] else 'trk',
              r[2], r[3], r[4], r[5], r[6]))
