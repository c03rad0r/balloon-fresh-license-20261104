"""Which opens did freerouting close, which did it keep, and did it invent new ones?

15 -> 10 opens is the headline, but it is only useful if the SAME opens went away. If freerouting
closed 5 known-blocked nets while opening 5 different ones, the count is a coincidence and the board
is not better. So the two open sets are diffed net by net.

The set of nets it closed is the valuable output: my router called every one of the 5 real traps
impossible at S1. Any net freerouting closed is evidence that an escape exists, and can be re-routed
by hand at clean S1 without inheriting freerouting's clearance violations.
"""

import json
import subprocess
import os
import tempfile
from collections import defaultdict

BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
NEW = BASE + '/batches/FREEROUTING/routed.kicad_pcb'


def drc(board):
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', path, board], capture_output=True, text=True)
    d = json.load(open(path))
    os.unlink(path)
    return d


def opens_by_net(d):
    """Map net -> list of endpoint descriptions, using the item description for the net name."""
    out = defaultdict(list)
    for u in d.get('unconnected_items', []):
        ends = []
        for it in u.get('items', []):
            e = it.get('description', '')
            net = ''
            if '[' in e and ']' in e:
                net = e[e.index('[') + 1:e.index(']')]
            pos = it.get('pos') or {}
            ends.append('%s @(%s,%s)' % (e.split(' of ')[0], pos.get('x'), pos.get('y')))
        # net from first item that names one
        net = ''
        for it in u.get('items', []):
            e = it.get('description', '')
            if '[' in e and ']' in e:
                net = e[e.index('[') + 1:e.index(']')]
                break
        out[net].append(' | '.join(ends))
    return out


a = opens_by_net(drc(LIVE))
b = opens_by_net(drc(NEW))

sa, sb = set(a), set(b)
print('=== opens per net ===')
print('  live       : %d opens over %d nets' % (sum(len(v) for v in a.values()), len(a)))
print('  freerouted : %d opens over %d nets' % (sum(len(v) for v in b.values()), len(b)))

print('\n=== CLOSED by freerouting (were open, now connected) ===')
closed = sorted(sa - sb)
for n in closed:
    print('  %-22s (%d open(s) closed)' % (n or '<no net>', len(a[n])))
if not closed:
    print('  none')

print('\n=== STILL OPEN in both ===')
for n in sorted(sa & sb):
    print('  %-22s live %d -> new %d' % (n or '<no net>', len(a[n]), len(b[n])))

print('\n=== NEWLY OPENED by freerouting (regressions) ===')
for n in sorted(sb - sa):
    print('  %-22s (%d)' % (n or '<no net>', len(b[n])))
    for line in b[n][:3]:
        print('      %s' % line)
if not (sb - sa):
    print('  none')

print('\n=== verdict ===')
print('  opens: %d -> %d' % (sum(len(v) for v in a.values()), sum(len(v) for v in b.values())))
print('  nets genuinely closed: %d' % len(closed))
print('  nets regressed to open: %d' % len(sb - sa))
