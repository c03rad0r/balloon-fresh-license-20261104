"""Control for the pour-area check: refill the UNCHANGED live board the same way.

`fr4_gate.py` reported In1 -2.77 mm2 and In2 -21.03 mm2 for the 4-net candidate and refused it.

Suspicious detail: the In2 drop is EXACTLY -21.03, identical to the wholesale freerouting candidate's
drop. Two different boards producing the same loss to two decimal places points at the measuring
instrument, not the copper -- both were refilled by ZONE_FILLER in my own script.

So this refills the LIVE board with the same call and re-measures. If live-refilled also loses ~21 mm2
on In2, the drop is my refill producing a different (less generous) fill than whatever filled the board
originally, and it says nothing about the candidate's copper. If live-refilled keeps its area, the drop
is real damage and the refusal stands.
"""

import os
import shutil
import pcbnew as p

UM = 1_000_000.0
BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
OUT = '/home/c08r4d0r/.hermes/cache/scratch/live_refill/live_refilled.kicad_pcb'


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


def zone_detail(board):
    b = p.LoadBoard(board)
    for z in b.Zones():
        for lay, name in ((p.In1_Cu, 'In1'), (p.In2_Cu, 'In2')):
            if not z.IsOnLayer(lay):
                continue
            try:
                a = abs(z.GetFilledPolysList(lay).Area()) / (UM * UM)
            except Exception:
                a = -1
            print('     zone %-14s %-6s %8.2f mm2  prio %s  minwidth %.3f  thermal_gap %.3f'
                  % (z.GetNetname(), name, a, z.GetAssignedPriority(),
                     z.GetMinThickness() / UM, z.GetThermalReliefGap() / UM))


print('=== as-stored ===')
base_p = pour(LIVE)
print('  %s' % base_p)
zone_detail(LIVE)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
shutil.copy(LIVE, OUT)
b = p.LoadBoard(OUT)
b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(OUT, b)
print('\n=== after MY refill of the UNCHANGED live board ===')
new_p = pour(OUT)
print('  %s' % new_p)

print('\n=== delta caused purely by refilling, no copper change ===')
for k in base_p:
    print('  %-4s %8.2f -> %8.2f  (%+.2f)' % (k, base_p[k], new_p[k], new_p[k] - base_p[k]))

print()
d_in2 = new_p['In2'] - base_p['In2']
print('  In2 change from refill alone: %+.2f mm2' % d_in2)
if d_in2 < -10:
    print('  -> the -21 mm2 "damage" is MY REFILL, not the candidate copper.')
    print('     The pour-area gate as written measures my filler, not the board.')
else:
    print('  -> refill alone does not explain the drop; treat the candidate loss as real.')
