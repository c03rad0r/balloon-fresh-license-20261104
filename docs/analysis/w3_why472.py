"""Why does the search exhaust at exactly 472 steps whatever the layer set?

Two runs, different LAYERS, identical 472 steps. That is the signature of a search that never leaves a
small pocket, so the variable under test cannot matter. Before changing anything else, measure the
pocket: how many free cells exist around the start, and what is immediately blocking.

Checks, in order:
  1. is the start pad's own copper being treated as an obstacle (the defect that produced a false
     "pad-local pocket" in reach_fast.py)?
  2. does the start point sit inside the bbox at all, and is the bbox large enough that the goal is
     inside it?
  3. what does one expansion look like -- how many neighbours does the start cell have?

This is diagnosis only; nothing is written.
"""

import sys
import pcbnew as p

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import collide_router as CR

UM = 1_000_000.0
LIVE = ('/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/'
        'latest.kicad_pcb')
NET = '/W3_SOLAR_N'
START = (38.700, 3.000)
GOAL = (29.000, 2.000)

b = p.LoadBoard(LIVE)
field = CR.Field(b, (0, 0, 80 * UM, 80 * UM), clear=200_000 + 70_711)

print('=== field constants ===')
for k in ('TRACK_R', 'CLEAR', 'VIA_R', 'DRILL_R', 'EDGE'):
    print('  %-8s %.3f mm' % (k, getattr(CR, k) / UM))
print('  clear   %.3f mm (guard band)' % (field.clear / UM))

print('\n=== is the START free for its own net? ===')
sx, sy = int(START[0] * UM), int(START[1] * UM)
print('  track_ok(B.Cu) = %s' % field.track_ok(sx, sy, p.B_Cu, NET))
print('  track_ok(F.Cu) = %s' % field.track_ok(sx, sy, p.F_Cu, NET))
print('  via_ok         = %s' % field.via_ok(sx, sy, NET))

print('\n=== what blocks it, if anything (foreign copper within 1 mm of start, B.Cu) ===')
tr = CR.TRACK_R
for r in (200_000, 400_000, 800_000, 1_200_000):
    hits = []
    for o in field.buckets[p.B_Cu].query(sx, sy, r + field.clear):
        if o.net == NET:
            continue
        d = field.disc(p.VECTOR2I(sx, sy), tr)
        if d.Collide(o.sh, field.clear):
            hits.append((o.kind, o.net, o.name))
    print('  radius %.1f mm : %d blocking object(s) %s' % (r / UM, len(hits), hits[:4]))
    if hits:
        break

print('\n=== the SAME pads, but is the goal free? ===')
gx, gy = int(GOAL[0] * UM), int(GOAL[1] * UM)
print('  track_ok(B.Cu) = %s' % field.track_ok(gx, gy, p.B_Cu, NET))
print('  via_ok         = %s' % field.via_ok(gx, gy, NET))

print('\n=== free-cell count around each terminal (radius 10 lattices = 1.0 mm) ===')
for tag, (px, py) in (('START', START), ('GOAL', GOAL)):
    ix, iy = int(px * UM), int(py * UM)
    free = total = 0
    for di in range(-10, 11):
        for dj in range(-10, 11):
            total += 1
            if field.track_ok(ix + di * CR.GRID, iy + dj * CR.GRID, p.B_Cu, NET):
                free += 1
    print('  %-6s %d of %d cells free on B.Cu' % (tag, free, total))

print('\n=== does the net have copper ALREADY at these coordinates? ===')
for t in b.GetTracks():
    if str(t.GetNetname()) != NET:
        continue
    s, e = t.GetStart(), t.GetEnd()
    for px, py in ((s.x / UM, s.y / UM), (e.x / UM, e.y / UM)):
        for tag, (qx, qy) in (('START', START), ('GOAL', GOAL)):
            if abs(px - qx) < 0.001 and abs(py - qy) < 0.001:
                print('  %s coincides with a %s endpoint on %s'
                      % (tag, 'VIA' if t.Type() == p.PCB_VIA_T else 'track',
                         b.GetLayerName(t.GetLayer())))
