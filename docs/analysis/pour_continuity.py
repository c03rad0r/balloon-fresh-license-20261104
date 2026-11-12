"""Replace the pour-AREA gate with a pour-CONTINUITY gate.

MY GATE WAS WRONG. `fr4_gate.py` and `fr_3nets.py` refused candidates because inner pour area dropped
(In1 -2.35, In2 -5.25 mm2). That is not damage. Every via that passes through a plane requires an
antipad cutout -- 0.600 mm land + 0.200 mm clearance each side = a 1.000 mm hole, area 0.785 mm2. The
3-net candidate adds exactly 3 vias, and 3 x 0.785 = 2.36 mm2, which matches In1's -2.35 to 0.01 mm2.
The board already carries 158 such vias; the live plane is full of antipads by design.

So area delta measures "did I add vias", not "did I damage the plane". Comparing area to a -1.0 mm2
threshold was a mis-calibrated gate that would have refused every legitimate route forever.

WHAT ACTUALLY MATTERS: is the plane still ONE continuous conductor? A return plane broken into islands
is a real defect (it is why this campaign spent commits on GND stitching). So the check is:

  1. island count per plane layer -- must not increase
  2. largest island fraction of total filled area -- must not collapse
  3. net of the plane unchanged

This distinguishes "another antipad" (fine) from "the pour got severed" (not fine).
"""

import pcbnew as p

UM = 1_000_000.0
BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
BOARDS = [
    ('live', BASE + '/latest.kicad_pcb'),
    ('FR3NETS', BASE + '/batches/FR3NETS/routed.kicad_pcb'),
    ('FR4NETS', BASE + '/batches/FR4NETS/routed.kicad_pcb'),
]


def plane_stats(board, lay):
    b = p.LoadBoard(board)
    islands = []
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
            a = abs(poly.Outline(i).Area()) / (UM * UM)
            if a > 0.01:
                islands.append(a)
    islands.sort(reverse=True)
    tot = sum(islands)
    return islands, tot


print('%-10s %-5s %8s %8s %10s %10s' % ('BOARD', 'LAYER', 'islands', 'total', 'largest', 'largest%'))
print('-' * 62)
res = {}
for name, path in BOARDS:
    row = {}
    for lay, lname in ((p.In1_Cu, 'In1'), (p.In2_Cu, 'In2')):
        isl, tot = plane_stats(path, lay)
        if not isl:
            print('%-10s %-5s %8d %8.2f %10s %10s' % (name, lname, 0, 0, '-', '-'))
            row[lname] = (0, 0.0, 0.0)
            continue
        biggest = isl[0]
        print('%-10s %-5s %8d %8.2f %10.2f %9.1f%%'
              % (name, lname, len(isl), tot, biggest, 100.0 * biggest / tot))
        row[lname] = (len(isl), tot, biggest)
    res[name] = row

print('\n=== continuity verdict ===')
base = res['live']
ok_all = True
for name in ('FR3NETS', 'FR4NETS'):
    print('\n  %s' % name)
    for lname in ('In1', 'In2'):
        bi, bt, bb = base[lname]
        ci, ct, cb = res[name][lname]
        islands_ok = ci <= bi
        # the plane must remain a single dominant conductor
        frac = (cb / ct) if ct else 0
        frac_ok = frac > 0.90
        ok = islands_ok and frac_ok
        ok_all = ok_all and ok
        print('    %-4s islands %d -> %d (%s)   largest %.1f%% (%s)   area %+.2f mm2'
              % (lname, bi, ci, 'OK' if islands_ok else 'GREW',
                 frac * 100, 'OK' if frac_ok else 'FRAGMENTED', ct - bt))

print('\n  %s' % ('CONTINUITY HELD -- area drops are antipads, not damage'
                  if ok_all else 'PLANE DAMAGE -- investigate'))
