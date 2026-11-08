"""Report the board's netclass clearance/track settings, and why the DSN says smd_smd 50.

The exported DSN carries:
    (rule (width 200) (clearance 200) (clearance 50 (type smd_smd)))

The (clearance 200) matches S1 and the project .kicad_dru. The 50 does NOT, and freerouting would use
0.050 mm between SMD pads if it were allowed to. Before letting freerouting touch the board I need to
know whether that 50 comes from the board's own settings (in which case KiCad already considers it
legal for pads) or is an export artefact that I should override to 200.

It is almost certainly pad-to-pad only -- pad positions are fixed by placement, so it cannot change the
board -- but 'almost certainly' is what the previous six wrong conclusions all sounded like.
"""

import pcbnew as p

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
UM = 1_000_000.0

b = p.LoadBoard(BOARD)
ds = b.GetDesignSettings()

print('=== netclasses ===')
try:
    ncs = ds.GetNetClasses()
    for name in ncs.GetNetClassNames():
        nc = ncs.Find(name) if hasattr(ncs, 'Find') else None
        if nc is None:
            continue
        print('  %-22s clearance %.3f mm  track %.3f mm  via %.3f/%.3f mm' % (
            name,
            nc.GetClearance() / UM,
            nc.GetTrackWidth() / UM,
            nc.GetViaDiameter() / UM,
            nc.GetViaDrill() / UM,
        ))
except Exception as e:
    print('  netclass read failed:', e)

print('\n=== design-settings minimums (board-wide floors) ===')
for label, fn in [
    ('min clearance', 'GetMinClearance'),
    ('min track width', 'GetTrackWidth'),
    ('min via diameter', 'GetViasMinSize'),
    ('min via drill', 'GetViasMinDrill'),
    ('min hole-to-hole', 'GetHoleToHoleMin'),
    ('solder mask expansion', 'GetSolderMaskExpansion'),
]:
    f = getattr(ds, fn, None)
    if f is None:
        print('  %-24s n/a' % label)
        continue
    try:
        v = f()
        try:
            v = v / UM
        except TypeError:
            pass
        print('  %-24s %.4f mm' % (label, v))
    except Exception as e:
        print('  %-24s err %s' % (label, e))

print('\n=== netclass assignment counts ===')
from collections import Counter
c = Counter()
for code, item in b.GetNetInfo().NetsByNetcode().items():
    try:
        c[item.GetNetClassName()] += 1
    except Exception:
        c['?'] += 1
for k, v in c.most_common():
    print('  %-22s %d nets' % (k, v))
