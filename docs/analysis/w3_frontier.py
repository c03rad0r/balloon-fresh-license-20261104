"""Instrument route() directly: count expansions and where the search actually went.

Everything checked so far says the route should exist:
  start track_ok(B.Cu)=True, 238/441 cells free around it
  goal  track_ok(B.Cu)=True, 441/441 cells free around it
  zero foreign copper within 1.2 mm of the start
and yet it returns "search exhausted 472 steps" for both the 2-layer and 3-layer run.

472 expansions cannot cover two free pockets. So the search is being confined. Candidates:
  a) the bbox handed to route() is too small or mis-origined, so most of the path is outside it
  b) the A* frontier collapses because every neighbour fails a test that is fine at the seed
  c) the deadline fires early and reports 'exhausted'

This re-implements the frontier walk with counters so the answer is measured, not inferred. Nothing is
written to any board.
"""

import sys
import math
import heapq
import pcbnew as p

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import collide_router as CR

UM = 1_000_000.0
LIVE = ('/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/'
        'latest.kicad_pcb')
NET = '/W3_SOLAR_N'
START = (38.700, 3.000)
GOAL = (29.000, 2.000)

CR.LAYERS = (p.F_Cu, p.B_Cu, p.In2_Cu)
b = p.LoadBoard(LIVE)
field = CR.Field(b, (0, 0, 80 * UM, 80 * UM), clear=200_000 + 70_711)

# deliberately generous bbox this time, and print it
bbox = (int(26.0 * UM), int(0.5 * UM), int(42.0 * UM), int(10.0 * UM))
print('=== bbox ===')
print('  (%.1f,%.1f)-(%.1f,%.1f) mm' % (bbox[0] / UM, bbox[1] / UM, bbox[2] / UM, bbox[3] / UM))
x0, y0 = bbox[0], bbox[1]
nx = (bbox[2] - x0) // CR.GRID + 1
ny = (bbox[3] - y0) // CR.GRID + 1
print('  %d x %d cells' % (nx, ny))

si = (int(START[0] * UM) - x0) // CR.GRID
sj = (int(START[1] * UM) - y0) // CR.GRID
gi = (int(GOAL[0] * UM) - x0) // CR.GRID
gj = (int(GOAL[1] * UM) - y0) // CR.GRID
print('  start cell (%d,%d)  goal cell (%d,%d)' % (si, sj, gi, gj))
print('  start inside bbox: %s   goal inside bbox: %s'
      % (0 <= si < nx and 0 <= sj < ny, 0 <= gi < nx and 0 <= gj < ny))

# manual BFS on B.Cu only, counting reachable cells
print('\n=== manual BFS on B.Cu from the start cell, within the bbox ===')
seen = set()
stack = [(si, sj)]
seen.add((si, sj))
blocked_first = 0
while stack:
    i, j = stack.pop()
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        c = (i + di, j + dj)
        if c in seen or not (0 <= c[0] < nx and 0 <= c[1] < ny):
            continue
        ok = field.track_ok(x0 + c[0] * CR.GRID, y0 + c[1] * CR.GRID, p.B_Cu, NET)
        if not ok:
            blocked_first += 1
            continue
        seen.add(c)
        stack.append(c)
print('  reachable cells on B.Cu: %d of %d' % (len(seen), nx * ny))
print('  goal cell reached      : %s' % ((gi, gj) in seen))

if (gi, gj) not in seen:
    # how close did the flood get to the goal?
    best = min(seen, key=lambda c: math.hypot(c[0] - gi, c[1] - gj))
    print('  closest flood cell to goal: (%d,%d) -> (%.3f,%.3f), distance %.3f mm'
          % (best[0], best[1], (x0 + best[0] * CR.GRID) / UM, (y0 + best[1] * CR.GRID) / UM,
             math.hypot(best[0] - gi, best[1] - gj) * CR.GRID / UM))
    # what blocks the straight line between them?
    print('\n  walking the straight line from that cell to the goal, naming blockers:')
    n = 40
    last_ok = True
    for k in range(n + 1):
        ci = best[0] + (gi - best[0]) * k // n
        cj = best[1] + (gj - best[1]) * k // n
        ok = field.track_ok(x0 + ci * CR.GRID, y0 + cj * CR.GRID, p.B_Cu, NET)
        if last_ok and not ok:
            wx, wy = (x0 + ci * CR.GRID) / UM, (y0 + cj * CR.GRID) / UM
            print('    first block at (%.3f,%.3f)' % (wx, wy))
            blk = []
            for o in field.buckets[p.B_Cu].query(x0 + ci * CR.GRID, y0 + cj * CR.GRID,
                                                 CR.TRACK_R + field.clear):
                if o.net == NET:
                    continue
                d = field.disc(p.VECTOR2I(x0 + ci * CR.GRID, y0 + cj * CR.GRID), CR.TRACK_R)
                if d.Collide(o.sh, field.clear):
                    blk.append((o.kind, o.net, o.name))
            print('    blockers: %s' % (blk[:6] or 'none found by bucket query'))
            break
        last_ok = ok
