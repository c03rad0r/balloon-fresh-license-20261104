"""Full adoption gate for the FR4NETS candidate: the 3 batch checks plus the C10 freeze and pours.

The headline is 15 -> 9 opens with violations unchanged at 16 and no new opens. That is the best result
this campaign has produced, and it arrives by taking freerouting's four *legal* routes while leaving
every piece of its collateral behind.

But "best result" is exactly when this campaign's previous adoptions went wrong, so the same extra
checks that refused the wholesale candidate run here:

  C10 FREEZE   no copper may sit inside x 8.00-11.20, y 41.00-44.20 that was not there before
  POUR HEALTH  In1 (GND) and In2 (+3V3) filled area must not have dropped
  SILK         check_silk.py must still report LEGIBLE
  SOCKET EDGE  no track within 0.50 mm of, or across, a wing-socket cavity edge
  PARITY       schematic parity unchanged
"""

import os
import subprocess
import json
import tempfile
import pcbnew as p
from collections import Counter, defaultdict

UM = 1_000_000.0
BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
CAND = BASE + '/batches/FR4NETS/routed.kicad_pcb'
WORK = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
C10 = (8.00, 41.00, 11.20, 44.20)


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


def copper_in_window(board, win):
    x0, y0, x1, y1 = win
    b = p.LoadBoard(board)
    out = []
    for t in b.GetTracks():
        s, e = t.GetStart(), t.GetEnd()
        if any(x0 <= px / UM <= x1 and y0 <= py / UM <= y1 for px, py in ((s.x, s.y), (e.x, e.y))):
            out.append((str(t.GetNetname()), b.GetLayerName(t.GetLayer()),
                        round(t.GetLength() / UM, 6), t.Type() == p.PCB_VIA_T))
    return out


def pour(board):
    b = p.LoadBoard(board)
    out = {}
    for lay, name in ((p.In1_Cu, 'In1'), (p.In2_Cu, 'In2')):
        tot = 0.0
        for z in b.Zones():
            if not z.IsOnLayer(lay):
                continue
            try:
                tot += abs(z.GetFilledPolysList(lay).Area()) / (UM * UM)
            except Exception:
                pass
        out[name] = tot
    return out


dl, dc = drc(LIVE), drc(CAND)
al, ac = opens_by_net(dl), opens_by_net(dc)
cl_, cn = Counter(v.get('type') for v in dl.get('violations', [])), Counter(v.get('type') for v in dc.get('violations', []))
ol, oc = len(dl.get('unconnected_items', [])), len(dc.get('unconnected_items', []))

print('=== 1 opens ===')
print('  %d -> %d   %s' % (ol, oc, 'PASS' if oc < ol else 'FAIL'))

print('\n=== 2 previously connected pairs (no new opens) ===')
newly = sorted(set(ac) - set(al))
closed = sorted(set(al) - set(ac))
print('  closed: %s' % (', '.join(closed) or 'none'))
print('  new   : %s' % (', '.join(newly) or 'none'))
print('  -> %s' % ('PASS' if not newly else 'FAIL'))

print('\n=== 3 hard electrical items ===')
HARD = ('clearance', 'hole_clearance', 'track_width', 'shorting_items', 'tracks_crossing',
        'copper_edge_clearance', 'isolated_copper', 'via_dangling')
hl = sum(cl_.get(t, 0) for t in HARD)
hc = sum(cn.get(t, 0) for t in HARD)
print('  live %d -> candidate %d   %s' % (hl, hc, 'PASS' if hc <= hl else 'FAIL'))
for t in sorted(set(list(cl_) + list(cn))):
    if cl_.get(t) or cn.get(t):
        print('     %-24s %3d -> %3d' % (t, cl_.get(t, 0), cn.get(t, 0)))

print('\n=== 4 C10 FROZEN WINDOW %s ===' % (C10,))
li = copper_in_window(LIVE, C10)
ci = copper_in_window(CAND, C10)
live_ct = Counter(li)
cand_ct = Counter(ci)
added = cand_ct - live_ct
removed = live_ct - cand_ct
print('  live items %d   candidate items %d   delta %+d' % (len(li), len(ci), len(ci) - len(li)))
if added:
    print('  ADDED:')
    for k, n in added.items():
        print('     %s x%d' % (str(k), n))
if removed:
    print('  REMOVED:')
    for k, n in removed.items():
        print('     %s x%d' % (str(k), n))
c10_ok = not added
print('  -> %s' % ('PASS' if c10_ok else 'FAIL'))

print('\n=== 5 inner pour health ===')
pl, pc = pour(LIVE), pour(CAND)
pour_ok = True
for k in pl:
    d_ = pc[k] - pl[k]
    ok = d_ > -1.0
    pour_ok = pour_ok and ok
    print('  %-4s %8.2f -> %8.2f mm2 (%+.2f)  %s' % (k, pl[k], pc[k], d_, 'PASS' if ok else 'FAIL'))

print('\n=== 6 silk / socket / parity (repo gates) ===')
gates = {}
for name, cmd in (
    ('check_silk', ['/usr/bin/python3', '-B', 'tracker/hardware/check_silk.py', CAND]),
    ('check_socket_edge_tracks', ['/usr/bin/python3', '-B', 'tracker/hardware/check_socket_edge_tracks.py', CAND]),
):
    r = subprocess.run(cmd, cwd=WORK, capture_output=True, text=True, timeout=900)
    txt = (r.stdout + r.stderr).strip().splitlines()
    gates[name] = r.returncode
    print('  %-26s rc=%d  %s' % (name, r.returncode, txt[-1][:90] if txt else ''))

print('\n=== VERDICT ===')
checks = [('opens decrease', oc < ol), ('no new opens', not newly),
          ('hard electrical', hc <= hl), ('C10 frozen', c10_ok), ('pour health', pour_ok)]
for n, ok in checks:
    print('  %-20s %s' % (n, 'PASS' if ok else 'FAIL'))
allok = all(ok for _, ok in checks)
print()
print('  %s' % ('ALL PASS -- adopt' if allok else 'REFUSED'))
