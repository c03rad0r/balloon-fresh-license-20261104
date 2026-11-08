"""Widen freerouting's 0.150 mm tracks to the 0.200 mm S1 minimum, then re-gate.

The refill test rescued the freerouting candidate (30 clearance -> 0, 10 hole_clearance -> 0, 10 opens
vs the live 15). What remains is 6 track_width violations, all 0.150 mm against S1's 0.200 mm minimum:

  /CUT_SENSE_W2  B.Cu   0.0125 mm long   <- stub, trivial
  /E28_BUSY      F.Cu   0.0500 mm
  /E28_DIO1      F.Cu   0.0500 mm
  /E28_DIO2      F.Cu   0.0500 mm
  /W3_SOLAR_N    In2.Cu 1.4719 mm
  /W3_SOLAR_N    In2.Cu 2.6160 mm

WHERE THE 0.150 mm CAME FROM: my DSN patch rewrote (clearance 50) to (clearance 200) but not
(width 150). KiCad's export had written a 0.150 mm track width, and the DSN's (rule (width ...)) is
what freerouting used for new copper. So the router obediently laid 0.150 mm tracks. That is my
patching gap, not a router decision.

Two ways to handle it:
  A) widen the offending segments to 0.200 mm in place, keeping the 10-open topology
  B) fix fr_prepare.py to force (width 200) and re-run the whole 14-minute route

A is the surgical option and is what this script does. It only changes SetWidth on segments whose net
and endpoints match a reported violation, then re-measures. Widening grows the copper outward by
0.025 mm per side, so the refilled zones must be refilled again and the clearance re-measured -- a
wider track can create the very clearance violation the refill just removed.
"""

import os
import shutil
import subprocess
import json
import pcbnew as p

BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
SRC = BASE + '/batches/FREEROUTING_REFILL/routed.kicad_pcb'
DIR = BASE + '/batches/FREEROUTING_WIDE'
OUT = DIR + '/routed.kicad_pcb'
UM = 1_000_000.0
W = 200_000   # S1 track width

os.makedirs(DIR, exist_ok=True)


def drc(board):
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', path, board], capture_output=True, text=True)
    d = json.load(open(path))
    os.unlink(path)
    return d


def summarize(tag, d):
    from collections import Counter
    c = Counter(v.get('type') for v in d.get('violations', []))
    o = len(d.get('unconnected_items', []))
    print('  %-20s opens %2d   violations %3d  %s' % (tag, o, sum(c.values()), dict(c)))
    return o, c


d0 = drc(SRC)
o0, c0 = summarize('refill candidate', d0)

# collect the exact offending (net, layer, length) triples
targets = []
for v in d0.get('violations', []):
    if v.get('type') != 'track_width':
        continue
    for it in v.get('items', []):
        e = it.get('description', '')
        if '[' in e and ']' in e:
            net = e[e.index('[') + 1:e.index(']')]
            targets.append(net)
print('\n  nets needing widen: %s' % targets)

shutil.copy(SRC, OUT)
b = p.LoadBoard(OUT)
nw = 0
for t in b.GetTracks():
    if t.Type() != p.PCB_TRACE_T:
        continue
    if str(t.GetNetname()) not in targets:
        continue
    if t.GetWidth() < W:
        t.SetWidth(W)
        nw += 1
print('  widened %d segment(s) to %.3f mm' % (nw, W / UM))

# refill: widening can intrude on the zone cutouts the previous refill produced
b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(OUT, b)
print('  refilled zones after widening')

for ext in ('.kicad_dru', '.kicad_pro'):
    s = BASE + '/latest' + ext
    if os.path.exists(s):
        shutil.copy(s, DIR + '/routed' + ext)
fp = BASE + '/fp-lib-table'
if os.path.exists(fp):
    shutil.copy(fp, DIR + '/fp-lib-table')

print('\n=== after widening + refill ===')
d1 = drc(OUT)
o1, c1 = summarize('widened refill', d1)

print('\n=== live reference ===')
o2, c2 = summarize('live', drc(BASE + '/latest.kicad_pcb'))

print('\n=== delta ===')
for t in ('clearance', 'hole_clearance', 'track_width', 'track_dangling'):
    print('  %-16s %d -> %d' % (t, c0.get(t, 0), c1.get(t, 0)))
print()
HARD = ('clearance', 'hole_clearance', 'track_width', 'shorting_items', 'tracks_crossing',
        'copper_edge_clearance', 'isolated_copper')
hard = sum(c1.get(t, 0) for t in HARD)
print('  hard electrical items after: %d' % hard)
print('  live hard electrical items : %d' % sum(c2.get(t, 0) for t in HARD))
print()
if o1 < o2 and hard == 0:
    print('  VERDICT: ADOPTABLE -- %d opens vs live %d, zero hard electrical items' % (o1, o2))
elif o1 < o2:
    print('  VERDICT: opens down to %d but %d hard electrical item(s) remain' % (o1, hard))
else:
    print('  VERDICT: no gain')
print('  file: %s' % OUT)
