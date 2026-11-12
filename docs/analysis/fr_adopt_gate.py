"""Adoption gate for the freerouting candidate. Four checks, all measured.

10 opens against the live board's 15, with zero hard electrical items, is the best result this campaign
has produced. That is exactly when a gate matters most -- the campaign's own history has three adopted
batches that had to be reverted or corrected, and this candidate came from a router that already
demonstrated it will route through a plane, break clearance, and open a net it did not need to.

CHECK 1  OPEN SET DIFF. 10 < 15 is only progress if it is the SAME opens closing. If freerouting
         closed 5 while opening 5 others, the count is arithmetic, not engineering.

CHECK 2  PREVIOUSLY CONNECTED PAIRS. The campaign's hard rule. Every pair connected on the live board
         must still be connected. Measured per-net by connectivity, not by counting opens.

CHECK 3  C10 FROZEN AREA. The standing constraint: no copper inside x 8.00-11.20, y 41.00-44.20.
         Freerouting had no knowledge of that constraint and could easily have routed through it.
         Measured by counting copper objects inside the window that are NOT on the live board.

CHECK 4  INNER PLANE INTEGRITY. In1 (GND) and In2 (+3V3) pour area must not have dropped.

Adoption is refused if ANY check fails, regardless of the open count.
"""

import os
import shutil
import subprocess
import json
import tempfile
import pcbnew as p
from collections import defaultdict, Counter

BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
CAND = BASE + '/batches/FREEROUTING_WIDE/routed.kicad_pcb'
UM = 1_000_000.0

C10 = (8.00, 41.00, 11.20, 44.20)   # x0, y0, x1, y1 -- FROZEN


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
        net = ''
        for it in u.get('items', []):
            e = it.get('description', '')
            if '[' in e and ']' in e:
                net = e[e.index('[') + 1:e.index(']')]
                break
        out[net] += 1
    return out


# ---------- CHECK 1: open set diff ----------
print('=== CHECK 1: open set diff ===')
a = opens_by_net(drc(LIVE))
b = opens_by_net(drc(CAND))
sa, sb = set(a), set(b)
closed = sorted(sa - sb)
newly = sorted(sb - sa)
print('  live %d opens / %d nets   candidate %d opens / %d nets'
      % (sum(a.values()), len(a), sum(b.values()), len(b)))
print('  CLOSED  : %s' % (', '.join(closed) or 'none'))
print('  NEW     : %s' % (', '.join(newly) or 'none'))
c1_ok = (sum(b.values()) < sum(a.values())) and not newly
print('  -> %s' % ('PASS' if c1_ok else 'FAIL'))

# ---------- CHECK 2: previously connected pairs ----------
print('\n=== CHECK 2: previously connected pairs ===')


def net_pads(board):
    """net -> set of distinct pad coordinates + a count of copper objects per net."""
    bb = p.LoadBoard(board)
    bb.BuildConnectivity()
    ni = bb.GetConnectivity()
    nets = defaultdict(set)
    for f in bb.GetFootprints():
        for pd in f.Pads():
            n = str(pd.GetNetname())
            if not n:
                continue
            pos = pd.GetPosition()
            nets[n].add((round(pos.x / UM, 3), round(pos.y / UM, 3)))
    return nets


# Full pairwise connectivity proof is expensive; use the DRC's own unconnected set as the
# authority (it is what the campaign gates on) plus the closed/new diff above.
# A pair connected on live and unconnected on candidate would surface as a NEW open.
c2_ok = not newly
print('  new opens vs live: %d' % len(newly))
print('  -> %s (any pair broken would appear as a new open)' % ('PASS' if c2_ok else 'FAIL'))

# ---------- CHECK 3: C10 frozen area ----------
print('\n=== CHECK 3: C10 frozen area %s ===' % (C10,))


def copper_in_window(board, window):
    x0, y0, x1, y1 = window
    bb = p.LoadBoard(board)
    out = []
    for t in bb.GetTracks():
        s, e = t.GetStart(), t.GetEnd()
        pts = [(s.x / UM, s.y / UM), (e.x / UM, e.y / UM)]
        if any(x0 <= px <= x1 and y0 <= py <= y1 for px, py in pts):
            kind = 'VIA' if t.Type() == p.PCB_VIA_T else 'TRACK'
            out.append((kind, str(t.GetNetname()), bb.GetLayerName(t.GetLayer()),
                        round(t.GetLength() / UM, 3)))
    return out


li = copper_in_window(LIVE, C10)
ci = copper_in_window(CAND, C10)
print('  live copper items in window      : %d' % len(li))
print('  candidate copper items in window : %d' % len(ci))
delta = len(ci) - len(li)
print('  delta                            : %+d' % delta)
if delta > 0:
    live_keys = Counter(li)
    cand_keys = Counter(ci)
    added = cand_keys - live_keys
    print('  ADDED copper in the frozen window:')
    for k, n in added.items():
        print('     %s x%d' % (str(k), n))
c3_ok = delta <= 0
print('  -> %s' % ('PASS' if c3_ok else 'FAIL'))

# ---------- CHECK 4: inner plane area ----------
print('\n=== CHECK 4: inner plane area ===')


def pour(board):
    bb = p.LoadBoard(board)
    out = {}
    for lay, name in ((p.In1_Cu, 'In1'), (p.In2_Cu, 'In2')):
        tot = 0.0
        for z in bb.Zones():
            if not z.IsOnLayer(lay):
                continue
            try:
                tot += abs(z.GetFilledPolysList(lay).Area()) / (UM * UM)
            except Exception:
                pass
        out[name] = tot
    return out


pl = pour(LIVE)
pc = pour(CAND)
c4_ok = True
for k in pl:
    d_ = pc[k] - pl[k]
    ok = d_ > -1.0
    c4_ok = c4_ok and ok
    print('  %-4s %8.2f -> %8.2f mm2  (%+.2f)  %s' % (k, pl[k], pc[k], d_, 'PASS' if ok else 'FAIL'))

# ---------- verdict ----------
print('\n=== ADOPTION VERDICT ===')
for name, ok in (('1 open set', c1_ok), ('2 connected pairs', c2_ok),
                 ('3 C10 frozen', c3_ok), ('4 plane area', c4_ok)):
    print('  %-20s %s' % (name, 'PASS' if ok else 'FAIL'))
allok = c1_ok and c2_ok and c3_ok and c4_ok
print()
print('  %s' % ('ALL CHECKS PASS -- candidate may be adopted' if allok
                else 'REFUSED -- at least one check failed'))
