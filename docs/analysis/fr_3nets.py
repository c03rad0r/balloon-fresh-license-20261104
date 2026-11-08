"""Build the candidate with only the 3 routes that clear every gate, dropping /W3_SOLAR_N.

WHY /W3_SOLAR_N IS THE ONE TO DROP. The full 4-net candidate gives 15 -> 9 opens but fails two gates,
and both failures point at the same net:

  SOCKET EDGE  /W3_SOLAR_N In2.Cu at J_W4, gap +0.407 mm against the 0.50 mm rule
               (35.976,6.507)->(33.379,6.507)  -- a real AGENTS.md 13a violation: no track within
               0.50 mm of, or across, a wing-socket cavity edge
  POUR HEALTH  In2 -21.03 mm2. /W3_SOLAR_N is the ONLY one of the four with copper on In2.Cu (it is
               the only net of the four routed on In2 at all), so it is the only possible cause.

CONTROL ALREADY RUN: refilling the UNCHANGED live board through the same ZONE_FILLER changes its pour
area by exactly +0.00 mm2 on both In1 and In2. So the -21 mm2 is the candidate's copper, not my
refill. It is a signal track crossing the +3V3 plane, which removes pour area by clearance cutout --
legal (the live board already carries /GNSS_PPS and /F33_BUSY on In2) but it is a real change to the
plane, and combined with the socket violation the net is not worth its one open.

So: 3 nets. Expected 15 -> 10 opens, with the socket rule and the plane preserved.
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
DIR = BASE + '/batches/FR3NETS'
OUT = DIR + '/routed.kicad_pcb'
C10 = (8.00, 41.00, 11.20, 44.20)
KEEP = ['/CUT_SENSE_W1', '/W1_SOLAR_N', '/W1_SOLAR_P']
DROP = ['/W3_SOLAR_N']

os.makedirs(DIR, exist_ok=True)


def drc(board):
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', path, board], capture_output=True, text=True)
    d = json.load(open(path))
    os.unlink(path)
    return d


def opens_by_net(d):
    out = defaultdict(int)
    for u in d.get('unconnected_items', []):
        for it in u.get('items', []):
            e = it.get('description', '')
            if '[' in e and ']' in e:
                out[e[e.index('[') + 1:e.index(']')]] += 1
                break
    return out


def rec(t, bn):
    s, e = t.GetStart(), t.GetEnd()
    return (str(t.GetNetname()), bn, round(s.x / UM, 6), round(s.y / UM, 6),
            round(e.x / UM, 6), round(e.y / UM, 6), round(t.GetWidth() / UM, 6),
            t.Type() == p.PCB_VIA_T, t.GetLayer())


def collect(board, nets):
    b = p.LoadBoard(board)
    return [rec(t, b.GetLayerName(t.GetLayer())) for t in b.GetTracks() if str(t.GetNetname()) in nets]


def in_c10(r):
    x0, y0, x1, y1 = C10
    _, _, ax, ay, bx, by = r[:6]
    return (x0 <= ax <= x1 and y0 <= ay <= y1) or (x0 <= bx <= x1 and y0 <= by <= y1)


live = collect(LIVE, set(KEEP))
cand = collect(CAND, set(KEEP))
lk = {(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in live}
added = [r for r in cand if (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) not in lk]

print('=== plan: 3 nets, /W3_SOLAR_N excluded ===')
print('  segments to apply : %d' % len(added))
bad = [r for r in added if in_c10(r)]
print('  inside C10        : %d' % len(bad))
if bad:
    raise SystemExit('REFUSING: copper in frozen window')

shutil.copy(LIVE, OUT)
b = p.LoadBoard(OUT)
name2code = {str(i.GetNetname()): c for c, i in b.GetNetInfo().NetsByNetcode().items()}
LAYER = {'F.Cu': p.F_Cu, 'B.Cu': p.B_Cu, 'In1.Cu': p.In1_Cu, 'In2.Cu': p.In2_Cu}

ntr = nvi = 0
for r in added:
    net, lname, x1, y1, x2, y2, w, isvia, _ = r
    code = name2code.get(net)
    lay = LAYER.get(lname)
    if code is None or lay is None:
        continue
    if isvia:
        v = p.PCB_VIA(b)
        v.SetPosition(p.VECTOR2I(int(round(x1 * UM)), int(round(y1 * UM))))
        v.SetWidth(int(round(w * UM)))
        v.SetDrill(int(round(w * UM * 0.6)))
        v.SetLayerPair(p.F_Cu, p.B_Cu)
        v.SetNet(b.FindNet(code))
        b.Add(v)
        nvi += 1
    else:
        t = p.PCB_TRACK(b)
        t.SetStart(p.VECTOR2I(int(round(x1 * UM)), int(round(y1 * UM))))
        t.SetEnd(p.VECTOR2I(int(round(x2 * UM)), int(round(y2 * UM))))
        t.SetWidth(int(round(w * UM)))
        t.SetLayer(lay)
        t.SetNet(b.FindNet(code))
        b.Add(t)
        ntr += 1
print('  applied %d track(s), %d via(s)' % (ntr, nvi))

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

dl, dc = drc(LIVE), drc(OUT)
ol, oc = len(dl.get('unconnected_items', [])), len(dc.get('unconnected_items', []))
al, ac = opens_by_net(dl), opens_by_net(dc)
cln = Counter(v.get('type') for v in dl.get('violations', []))
cnn = Counter(v.get('type') for v in dc.get('violations', []))
closed, newly = sorted(set(al) - set(ac)), sorted(set(ac) - set(al))
HARD = ('clearance', 'hole_clearance', 'track_width', 'shorting_items', 'tracks_crossing',
        'copper_edge_clearance', 'isolated_copper', 'via_dangling')
hl = sum(cln.get(t, 0) for t in HARD)
hc = sum(cnn.get(t, 0) for t in HARD)


def pour(board):
    bb = p.LoadBoard(board)
    o = {}
    for lay, name in ((p.In1_Cu, 'In1'), (p.In2_Cu, 'In2')):
        tot = 0.0
        for z in bb.Zones():
            if z.IsOnLayer(lay):
                try:
                    tot += abs(z.GetFilledPolysList(lay).Area()) / (UM * UM)
                except Exception:
                    pass
        o[name] = tot
    return o


def c10count(board):
    bb = p.LoadBoard(board)
    n = 0
    x0, y0, x1, y1 = C10
    for t in bb.GetTracks():
        s, e = t.GetStart(), t.GetEnd()
        if any(x0 <= px / UM <= x1 and y0 <= py / UM <= y1 for px, py in ((s.x, s.y), (e.x, e.y))):
            n += 1
    return n


print('\n=== gates ===')
print('  opens             : %d -> %d              %s' % (ol, oc, 'PASS' if oc < ol else 'FAIL'))
print('  closed            : %s' % (', '.join(closed) or 'none'))
print('  new opens         : %s   %s' % (', '.join(newly) or 'none', 'PASS' if not newly else 'FAIL'))
print('  hard electrical   : %d -> %d              %s' % (hl, hc, 'PASS' if hc <= hl else 'FAIL'))
print('  C10 items         : %d -> %d              %s' % (c10count(LIVE), c10count(OUT),
                                                          'PASS' if c10count(OUT) <= c10count(LIVE) else 'FAIL'))
pl, pc = pour(LIVE), pour(OUT)
pok = True
for k in pl:
    dd = pc[k] - pl[k]
    ok = dd > -1.0
    pok = pok and ok
    print('  pour %-4s         : %8.2f -> %8.2f (%+.2f) %s' % (k, pl[k], pc[k], dd, 'PASS' if ok else 'FAIL'))
print('\n  file: %s' % OUT)
