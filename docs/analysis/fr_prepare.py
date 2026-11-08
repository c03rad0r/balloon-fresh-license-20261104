"""Prepare the DSN for freerouting: force S1 everywhere, and report existing wiring.

Two jobs:

1. RULE OVERRIDE. KiCad's DSN export writes
       (clearance 50 (type smd_smd))
   even though the board's Default netclass is 0.200 mm / 0.200 mm / 0.600 / 0.300 exactly. That 50 is
   an export artefact, but freerouting reads rules from the DSN, so it would route SMD-to-SMD at
   0.050 mm. Override it to 200 so the router is held to the same S1 floor as the DRC.

2. INVENTORY. Report how many existing wire paths the DSN carries. Those are the copper already routed
   on the live board. They must survive: the campaign's hard check is "previously connected pairs not
   broken", and a router that silently rips up 15 opens' worth of good routing would be a regression
   however low the open count went.
"""

import os
import re
import shutil

BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/freerouting'
SRC = os.path.join(BASE, 'board.dsn')
DST = os.path.join(BASE, 'board-s1.dsn')

txt = open(SRC, encoding='utf-8', errors='replace').read()

print('=== rules BEFORE ===')
m = re.search(r'\(rule\s*\n(.*?)\n\s*\)\n', txt, re.S)
print(m.group(0) if m else 'no rule block')

# Force every clearance directive to 200 where it is currently below S1.
def fix_clearance(mo):
    val = int(mo.group(1))
    if val < 200:
        return mo.group(0).replace('(clearance %d' % val, '(clearance 200', 1)
    return mo.group(0)

out = re.sub(r'\(clearance (\d+)', fix_clearance, txt)

# ALSO FORCE TRACK WIDTH. This was missing on the first run and it silently produced sub-S1 copper:
# KiCad's DSN export writes (width 150) in the rule block even though the netclass is 0.200 mm, and
# freerouting honours the DSN, so it laid 0.150 mm tracks. The result was 6 track_width violations
# that had to be repaired by hand afterwards (fr_widen.py). Patch it here so it cannot recur.
def fix_width(mo):
    val = int(mo.group(1))
    if val < 200:
        return mo.group(0).replace('(width %d' % val, '(width 200', 1)
    return mo.group(0)

out = re.sub(r'\(width (\d+)', fix_width, out)

# Report the result
m2 = re.search(r'\(rule\s*\n(.*?)\n\s*\)\n', out, re.S)
print('\n=== rules AFTER ===')
print(m2.group(0) if m2 else 'no rule block')

# Existing wiring inventory
n_paths = len(re.findall(r'\(path\s', out))
n_wires = len(re.findall(r'\(wire\s', out))
n_vias = len(re.findall(r'\(via\s', out))
print('\n=== existing copper carried into the DSN ===')
print('   (path ...) entries : %d' % n_paths)
print('   (wire ...) entries : %d' % n_wires)
print('   (via ...) entries  : %d' % n_vias)

# Nets
nets = re.findall(r'\(net\s+(\S+)', out)
print('   nets declared      : %d' % len(nets))

open(DST, 'w', encoding='utf-8').write(out)
print('\nwrote %s (%.1f KB)' % (DST, len(out) / 1024.0))
print('changed: %s' % (out != txt))
