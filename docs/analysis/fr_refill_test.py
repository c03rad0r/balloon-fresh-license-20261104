"""Does refilling zones rescue the freerouting candidate?

CORRECTION TO MY OWN FINDING. `FINDING-freerouting-rejected.md` says freerouting "routed signal into
the power planes", implying that shorts the plane. That reasoning is wrong, and the live board proves
it: latest.kicad_pcb already carries SIX signal tracks on inner layers (+3V3 on In1; /F33_BUSY and
/GNSS_PPS on In2) and DRC flags none of them. A KiCad zone refills AROUND foreign copper, leaving a
clearance cutout. Signal on an inner layer is normal and legal.

So the 30 clearance violations are almost certainly NOT "signal on a plane". The likelier cause is
that pcbnew.ImportSpecctraSES adds tracks but does not refill the zones, so the OLD fill is still
sitting on top of the NEW copper -- stale fill versus fresh tracks reads as 0.000 mm actual clearance.

That is the same defect this campaign already hit once: an early add_path used SetNetCode and skipped
refill, turning 24 violations into 548. The fix then was refill; it may be the fix now.

This script refills and re-DRCs. If the clearance violations collapse, freerouting's 10-open result is
back in play and the whole 15-open conclusion changes. If they persist, my original rejection stands
and the reason needs restating precisely rather than by analogy.
"""

import os
import shutil
import subprocess
import json
import pcbnew as p

BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
SRC = BASE + '/batches/FREEROUTING/routed.kicad_pcb'
DIR = BASE + '/batches/FREEROUTING_REFILL'
OUT = DIR + '/routed.kicad_pcb'
UM = 1_000_000.0

os.makedirs(DIR, exist_ok=True)
shutil.copy(SRC, OUT)
for ext in ('.kicad_dru', '.kicad_pro'):
    s = BASE + '/latest' + ext
    if os.path.exists(s):
        shutil.copy(s, DIR + '/routed' + ext)
fp = BASE + '/fp-lib-table'
if os.path.exists(fp):
    shutil.copy(fp, DIR + '/fp-lib-table')


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
    print('  %-18s opens %2d   violations %3d  %s' % (tag, o, sum(c.values()), dict(c)))
    return o, c


print('=== before refill ===')
b0 = drc(SRC)
o0, c0 = summarize('freerouted raw', b0)

print('\n=== refilling zones ===')
b = p.LoadBoard(OUT)
b.BuildConnectivity()
filler = p.ZONE_FILLER(b)
nz = 0
for z in b.Zones():
    nz += 1
filler.Fill(b.Zones())
p.SaveBoard(OUT, b)
print('  refilled %d zone(s)' % nz)

print('\n=== after refill ===')
b1 = drc(OUT)
o1, c1 = summarize('freerouted refill', b1)

print('\n=== live reference ===')
o2, c2 = summarize('live', drc(BASE + '/latest.kicad_pcb'))

print('\n=== did refill fix the clearance violations? ===')
print('  clearance  %d -> %d' % (c0.get('clearance', 0), c1.get('clearance', 0)))
print('  hole_clr   %d -> %d' % (c0.get('hole_clearance', 0), c1.get('hole_clearance', 0)))
print('  track_w    %d -> %d' % (c0.get('track_width', 0), c1.get('track_width', 0)))
print()
if o1 < o2 and c1.get('clearance', 0) <= 5:
    print('  VERDICT: refill RESCUES the candidate -- %d opens, clearance down to %d' % (
        o1, c1.get('clearance', 0)))
elif o1 < o2:
    print('  VERDICT: refill helps but %d clearance violations remain' % c1.get('clearance', 0))
else:
    print('  VERDICT: refill does NOT rescue it -- original rejection stands')
print('  file: %s' % OUT)
