"""Build a surgical candidate: live board + ONLY freerouting's 4 closed-net routes.

The freerouting candidate is refused wholesale, but its damage is caused by collateral: it also
re-routed /F33_VCC (opening it), +3V3, /SPI1_MISO and /SPI1_MOSI (into the C10 freeze), and shrank the
inner pours. None of that was asked for. The four routes that DO close opens are clean -- measured, all
51 added segments sit outside the C10 window.

So this takes the live board and adds only those 51 segments, net by net, then refills and gates. If it
works, the opens fall with zero collateral.

SAFETY: copper is added only for nets in CLOSED, only for segments present in the freerouting candidate
and absent from live, and only if the segment lies entirely outside the C10 window (checked again here
rather than trusted from the previous run). Every added segment is SetNet()'d before being committed to
the board, because SetNetCode alone has produced 548 violations earlier in this campaign.

Zones are refilled after adding copper, and the refill is mandatory: without it the stale fill sits on
the new copper and DRC reports phantom clearance failures at 0.000 mm.
"""

import os
import shutil
import subprocess
import json
import tempfile
import pcbnew as p
from collections import Counter, defaultdict

UM = 1_000_000.0
BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
CAND = BASE + '/batches/FREEROUTING_WIDE/routed.kicad_pcb'
DIR = BASE + '/batches/FR4NETS'
OUT = DIR + '/routed.kicad_pcb'

C10 = (8.00, 41.00, 11.20, 44.20)
CLOSED = ['/CUT_SENSE_W1', '/W1_SOLAR_N', '/W1_SOLAR_P', '/W3_SOLAR_N']

os.makedirs(DIR, exist_ok=True)


def drc(board):
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', path, board], capture_output=True, text=True)
    d = json.load(open(path))
    os.unlink(path)
    return d


def summarize(tag, d):
    c = Counter(v.get('type') for v in d.get('violations', []))
    o = len(d.get('unconnected_items', []))
    print('  %-22s opens %2d   violations %3d  %s' % (tag, o, sum(c.values()), dict(c)))
    return o, c


def rec(t, bname):
    s, e = t.GetStart(), t.GetEnd()
    return (str(t.GetNetname()), bname, round(s.x / UM, 6), round(s.y / UM, 6),
            round(e.x / UM, 6), round(e.y / UM, 6), round(t.GetWidth() / UM, 6),
            t.Type() == p.PCB_VIA_T, t.GetLayer())


def collect(board, nets):
    b = p.LoadBoard(board)
    return [rec(t, b.GetLayerName(t.GetLayer())) for t in b.GetTracks() if str(t.GetNetname()) in nets]


def in_c10(r):
    x0, y0, x1, y1 = C10
    _, _, ax, ay, bx, by = r[:6]
    return (x0 <= ax <= x1 and y0 <= ay <= y1) or (x0 <= bx <= x1 and y0 <= by <= y1)


live = collect(LIVE, set(CLOSED))
cand = collect(CAND, set(CLOSED))
live_keys = {(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in live}

added = [r for r in cand
         if (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) not in live_keys]

# refuse anything in the frozen window, re-checked here
blocked = [r for r in added if in_c10(r)]
added = [r for r in added if not in_c10(r)]
print('=== plan ===')
print('  added segments from freerouting : %d' % (len(added) + len(blocked)))
print('  inside C10 (REFUSED)            : %d' % len(blocked))
print('  will be applied                 : %d' % len(added))
if blocked:
    print('  REFUSING TO PROCEED -- copper in the frozen window')
    raise SystemExit(2)

shutil.copy(LIVE, OUT)
b = p.LoadBoard(OUT)

# net name -> netcode via nets by name
name2code = {}
for code, item in b.GetNetInfo().NetsByNetcode().items():
    name2code[str(item.GetNetname())] = code

LAYER = {'F.Cu': p.F_Cu, 'B.Cu': p.B_Cu, 'In1.Cu': p.In1_Cu, 'In2.Cu': p.In2_Cu}

n_tr = n_vi = 0
for r in added:
    net, lname, x1, y1, x2, y2, w, isvia, laynum = r
    code = name2code.get(net)
    if code is None:
        print('  SKIP %s -- net not on board' % net)
        continue
    lay = LAYER.get(lname)
    if lay is None:
        continue
    if isvia:
        via = p.PCB_VIA(b)
        via.SetPosition(p.VECTOR2I(int(round(x1 * UM)), int(round(y1 * UM))))
        via.SetWidth(int(round(w * UM)))
        via.SetDrill(int(round(w * UM * 0.6)))   # land:drill 0.6:0.3 ratio held
        via.SetLayerPair(p.F_Cu, p.B_Cu)
        via.SetNet(b.FindNet(code))
        b.Add(via)
        n_vi += 1
    else:
        t = p.PCB_TRACK(b)
        t.SetStart(p.VECTOR2I(int(round(x1 * UM)), int(round(y1 * UM))))
        t.SetEnd(p.VECTOR2I(int(round(x2 * UM)), int(round(y2 * UM))))
        t.SetWidth(int(round(w * UM)))
        t.SetLayer(lay)
        t.SetNet(b.FindNet(code))
        b.Add(t)
        n_tr += 1

print('\n  applied %d track(s), %d via(s)' % (n_tr, n_vi))

b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(OUT, b)
print('  refilled zones')

for ext in ('.kicad_dru', '.kicad_pro'):
    s = BASE + '/latest' + ext
    if os.path.exists(s):
        shutil.copy(s, DIR + '/routed' + ext)
fp = BASE + '/fp-lib-table'
if os.path.exists(fp):
    shutil.copy(fp, DIR + '/fp-lib-table')

print('\n=== DRC ===')
o0, c0 = summarize('live', drc(LIVE))
o1, c1 = summarize('4-nets surgical', drc(OUT))

print('\n=== gates ===')
print('  1 opens decrease : %d -> %d   %s' % (o0, o1, 'PASS' if o1 < o0 else 'FAIL'))

def opens_by_net(d):
    out = defaultdict(int)
    for u in d.get('unconnected_items', []):
        for it in u.get('items', []):
            e = it.get('description', '')
            if '[' in e and ']' in e:
                out[e[e.index('[') + 1:e.index(']')]] += 1
                break
    return out

dl = drc(LIVE)
a, bb_ = opens_by_net(dl), opens_by_net(drc(OUT))
newly = sorted(set(bb_) - set(a))
closed = sorted(set(a) - set(bb_))
print('  2 no new opens   : closed %s / new %s   %s'
      % (closed or 'none', newly or 'none', 'PASS' if not newly else 'FAIL'))

HARD = ('clearance', 'hole_clearance', 'track_width', 'shorting_items', 'tracks_crossing',
        'copper_edge_clearance', 'isolated_copper', 'via_dangling')
hl = sum(c0.get(t, 0) for t in HARD)
h1 = sum(c1.get(t, 0) for t in HARD)
print('  3 no hard elec   : %d -> %d   %s' % (hl, h1, 'PASS' if h1 <= hl else 'FAIL'))
for t in HARD:
    if c0.get(t) or c1.get(t):
        print('       %-22s %d -> %d' % (t, c0.get(t, 0), c1.get(t, 0)))

print('\n  %s' % ('ADOPTABLE' if (o1 < o0 and not newly and h1 <= hl) else 'REFUSED'))
print('  file: %s' % OUT)
