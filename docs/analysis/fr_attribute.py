"""Do freerouting's 4 genuinely-closed nets route cleanly, or are they the violations?

This is the whole question. Two very different outcomes:

  A) The 4 closed nets route at clean S1 and the 40 clearance violations are freerouting's OTHER
     copper (fanout vias, the /F33_VCC regression). Then the 4 routes are a template I can reproduce
     by hand and adopt -- real progress, 15 -> 11 opens with no new violations.

  B) The 4 closed nets achieved connection BY violating clearance (routing closer than 0.200 mm).
     Then the "escape" is not an S1 escape at all and the count is bought with rule breaks. Nothing
     to adopt, and my own router's NO PATH stands.

So: attribute every clearance / hole_clearance / track_width violation to a net, and see whether any
of them sit on the 4 newly-closed nets. Also measure the actual minimum centre-gap of the new copper
on those nets against foreign copper, using Collide bisection rather than SHAPE::Distance.
"""

import json
import subprocess
import os
import tempfile
from collections import Counter, defaultdict

BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
NEW = BASE + '/batches/FREEROUTING/routed.kicad_pcb'

CLOSED = ['/CUT_SENSE_W1', '/W1_SOLAR_N', '/W1_SOLAR_P', '/W3_SOLAR_N']
BAD_TYPES = ('clearance', 'hole_clearance', 'track_width')


def drc(board):
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', path, board], capture_output=True, text=True)
    d = json.load(open(path))
    os.unlink(path)
    return d


def nets_in(v):
    """Every net named by any item in a violation."""
    out = set()
    for it in v.get('items', []):
        e = it.get('description', '')
        if '[' in e and ']' in e:
            out.add(e[e.index('[') + 1:e.index(']')])
    return out


d = drc(NEW)
viol = d.get('violations', [])

print('=== violations by type and the nets they involve ===')
per_type = defaultdict(Counter)
for v in viol:
    t = v.get('type')
    if t not in BAD_TYPES:
        continue
    for n in nets_in(v):
        per_type[t][n] += 1

for t in BAD_TYPES:
    if not per_type[t]:
        continue
    print('\n  %s (%d total):' % (t, sum(per_type[t].values())))
    for n, c in per_type[t].most_common(12):
        mark = '  <-- ONE OF THE 4 CLOSED' if n in CLOSED else ''
        print('     %-22s %3d%s' % (n, c, mark))

print('\n=== attribution: do the 4 closed nets carry any violations? ===')
for n in CLOSED:
    hits = sum(per_type[t][n] for t in BAD_TYPES)
    print('  %-18s %d violation(s) %s' % (n, hits, 'CLEAN' if hits == 0 else 'INVOLVED'))

print('\n=== sample clearance violations NOT involving the 4 closed nets ===')
shown = 0
for v in viol:
    if v.get('type') != 'clearance':
        continue
    ns = nets_in(v)
    if ns & set(CLOSED):
        continue
    print('  %s' % v.get('description', '')[:120])
    for it in v.get('items', []):
        print('      %s' % str(it.get('description', ''))[:100])
    shown += 1
    if shown >= 5:
        break
