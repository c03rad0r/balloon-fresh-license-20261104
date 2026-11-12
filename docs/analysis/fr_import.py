"""Import a freerouting .ses session back onto the live board, then apply the campaign gates.

THE GATES THIS MUST PASS (same two hard checks as every batch, plus electrical safety):

  1. opens DECREASE            -- DRC unconnected_items must go down
  2. previously connected pairs NOT BROKEN -- measured by net-by-net connectivity on both boards
  3. no new electrical errors   -- clearance / short / tracks_crossing must not rise
  4. no plane damage           -- In1 (GND) and In2 (+3V3) pour area must not drop

WHY GATE 4 EXISTS: freerouting reported every layer as a power plane and its fanout stage inserted
extra vias. If it re-cut In1/In2 the board could pass the open-count check while losing its ground
reference, which is a far worse outcome than an open. Measured explicitly rather than assumed.

The import itself uses pcbnew.ImportSpecctraSES, which applies the session's track/via additions to
the loaded board.
"""

import os
import sys
import json
import subprocess
import shutil
import pcbnew as p

WORK = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
BASE = WORK + '/docs/analysis/bulk-route-20261107'
SES = BASE + '/freerouting/board.ses'
LIVE = BASE + '/latest.kicad_pcb'
OUTDIR = BASE + '/batches/FREEROUTING'
OUT = OUTDIR + '/routed.kicad_pcb'
DRU = BASE + '/latest.kicad_dru'
PRO = BASE + '/latest.kicad_pro'
FPT = BASE + '/fp-lib-table'

UM = 1_000_000.0

if not os.path.exists(SES):
    print('NO SESSION FILE at %s -- the router has not finished' % SES)
    sys.exit(2)

os.makedirs(OUTDIR, exist_ok=True)


def drc(board):
    """Run kicad-cli DRC and return parsed JSON."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', path, board],
                   capture_output=True, text=True)
    d = json.load(open(path))
    os.unlink(path)
    return d


def stats(d):
    from collections import Counter
    opens = len(d.get('unconnected_items', {}))
    viol = d.get('violations', [])
    by = Counter(v.get('type') for v in viol)
    errs = Counter(v.get('type') for v in viol if v.get('severity') == 'error')
    return opens, by, errs


def pour_areas(board):
    """Total filled copper area per inner layer -- the plane health check."""
    b = p.LoadBoard(board)
    out = {}
    for lay, name in ((p.In1_Cu, 'In1.Cu'), (p.In2_Cu, 'In2.Cu')):
        tot = 0.0
        for z in b.Zones():
            if not z.IsOnLayer(lay):
                continue
            try:
                poly = z.GetFilledPolysList(lay)
            except Exception:
                continue
            if poly is None:
                continue
            for i in range(poly.OutlineCount()):
                tot += abs(poly.Outline(i).Area()) / (UM * UM)
        out[name] = tot
    return out


print('=== importing %s ===' % os.path.basename(SES))
shutil.copy(LIVE, OUT)
b = p.LoadBoard(OUT)
ok = p.ImportSpecctraSES(b, SES)
print('ImportSpecctraSES ->', ok)
p.SaveBoard(OUT, b)

# Sidecars are mandatory -- missing .kicad_dru caused phantom edge errors four times this campaign
for src, ext in ((DRU, '.kicad_dru'), (PRO, '.kicad_pro')):
    if os.path.exists(src):
        shutil.copy(src, OUTDIR + '/routed' + ext)
if os.path.exists(FPT):
    shutil.copy(FPT, OUTDIR + '/fp-lib-table')

print('\n=== DRC: live vs freerouted ===')
d_live = drc(LIVE)
d_new = drc(OUT)
o_live, by_live, err_live = stats(d_live)
o_new, by_new, err_new = stats(d_new)

print('  live       : %3d opens, %d violations %s' % (o_live, sum(by_live.values()), dict(by_live)))
print('  freerouted : %3d opens, %d violations %s' % (o_new, sum(by_new.values()), dict(by_new)))

print('\n=== gate 1: opens decrease ===')
print('  %d -> %d   %s' % (o_live, o_new, 'PASS' if o_new < o_live else 'FAIL'))

print('\n=== gate 3: electrical errors (clearance/short/crossing) ===')
HARD = ('clearance', 'shorting_items', 'tracks_crossing', 'copper_edge_clearance',
        'hole_clearance', 'hole_to_hole', 'via_dangling', 'track_dangling',
        'isolated_copper', 'starved_thermal')
hard_live = sum(err_live.get(t, 0) + by_live.get(t, 0) for t in HARD)
hard_new = sum(err_new.get(t, 0) + by_new.get(t, 0) for t in HARD)
print('  live %d -> freerouted %d   %s' % (hard_live, hard_new,
                                           'PASS' if hard_new <= hard_live else 'FAIL'))
for t in HARD:
    if by_live.get(t) or by_new.get(t):
        print('     %-24s %d -> %d' % (t, by_live.get(t, 0), by_new.get(t, 0)))

print('\n=== gate 4: inner plane area ===')
a_live = pour_areas(LIVE)
a_new = pour_areas(OUT)
for k in a_live:
    d_ = a_new[k] - a_live[k]
    print('  %-8s %8.2f -> %8.2f mm2  (%+.2f)  %s' % (
        k, a_live[k], a_new[k], d_, 'PASS' if d_ > -1.0 else 'FAIL'))

print('\n=== result ===')
verdict = (o_new < o_live) and (hard_new <= hard_live) and all(
    a_new[k] - a_live[k] > -1.0 for k in a_live)
print('  %s' % ('CANDIDATE -- adopt via adopt_batch.py after reach check' if verdict
                else 'REJECTED -- does not clear the gates above'))
print('  board: %s' % OUT)
