"""Export the live board to Specctra DSN for freerouting, and report the rules it carries.

WHY THIS NEEDS CHECKING BEFORE ROUTING: freerouting reads clearance/track rules from the DSN, not
from the project's .kicad_dru. If the export drops the rule set, freerouting will happily route at its
default clearance and produce a board that violates S1 everywhere. So the DSN is inspected for its
rule section before anything is routed on it.

Also reports which nets are unrouted, because freerouting's value here is specifically the 5 real
opens -- everything already routed must survive.
"""

import sys
import re
import pcbnew as p

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
OUT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/freerouting/board.dsn'

UM = 1_000_000.0

b = p.LoadBoard(BOARD)
b.BuildConnectivity()

import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)

ok = p.ExportSpecctraDSN(b, OUT)
print('ExportSpecctraDSN ->', ok)

txt = open(OUT, encoding='utf-8', errors='replace').read()
print('DSN size: %.1f KB, %d lines' % (len(txt) / 1024.0, txt.count('\n')))

# What rules did it carry?
print('\n=== rule section ===')
m = re.search(r'\(rule\b(.*?)\n\s*\)\s*\n', txt, re.S)
if m:
    print(m.group(0)[:1200])
else:
    print('NO (rule ...) block found -- DSN carries no clearance rules')

# layer / structure sanity
print('\n=== structure ===')
for key in ('(structure', '(layer ', '(plane ', '(network', '(resolution'):
    print('   %-12s %d occurrence(s)' % (key, txt.count(key)))

# nets present, and how many pads per net the DSN thinks are connected
print('\n=== nets in DSN ===')
netnames = re.findall(r'\(net\s+"([^"]+)"', txt)
print('   %d nets declared' % len(netnames))

# Which nets are unrouted on the live board (from connectivity, not DRC)
print('\n=== unrouted nets on the live board ===')
ni = b.GetConnectivity()
unrouted = set()
for code, item in b.GetNetInfo().NetsByNetcode().items():
    name = item.GetNetname()
    if not name:
        continue
    ratsnest = ni.GetRatsnestForNet(code)
    if ratsnest is not None and ratsnest.GetCount() > 0:
        unrouted.add(name)
for n in sorted(unrouted):
    print('   %s' % n)
print('   %d unrouted net(s)' % len(unrouted))
