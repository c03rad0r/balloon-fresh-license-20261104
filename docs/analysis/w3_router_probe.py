"""Test whether collide_router can close /W3_SOLAR_N once In2 is available.

TWO CLAIMS OF MINE ARE CHECKED HERE, ONE OF WHICH I SUSPECT IS WRONG.

CLAIM A (I stated it repeatedly): "route_batch plans ONE via and cannot do two layer changes."
  Reading collide_router.route(), a layer change is an ordinary A* neighbour:
      other = LAYERS[1 - LAYERS.index(l)]
      if via(i, j) and ok(i, j, other): cand.append(((i, j, other), 4.0))
  Any number of vias can be chained. The real restriction is LAYERS = (F_Cu, B_Cu) -- only two copper
  layers. So the limit is LAYER COUNT, not via count. If that is right, my "two layer changes" framing
  has been wrong all campaign and the true blocker is that In2 was never offered.

CLAIM B: /W3_SOLAR_N is closable on In2 with its leg at y >= 6.600 to clear the J_W4 cavity.
  Cavity is a 0.5 x 6.0 mm slot at x 35.750-36.250, y 0-6.000. Freerouting ran at y=6.507 -> 0.407 mm
  copper gap, under the 0.50 rule. y>=6.600 gives 0.800 mm.

This runs the router with In2 added, on /W3_SOLAR_N, from J_W4.1 to D_BP4.1, with a bbox that covers the
cavity region, and reports whether a path exists and whether any segment lands inside the forbidden
band x 35.75-36.25, y < 6.600.

Nothing is written to the live board.
"""

import sys
import math
import time
import pcbnew as p

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import collide_router as CR

UM = 1_000_000.0
LIVE = ('/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/'
        'latest.kicad_pcb')
NET = '/W3_SOLAR_N'

START = (38.700, 3.000)     # J_W4.1, B.Cu
GOAL = (29.000, 2.000)      # D_BP4.1, B.Cu

CAV = (35.750, 0.000, 36.250, 6.000)
SAFE_Y = 6.600

print('=== router configuration as shipped ===')
print('  LAYERS = %s' % (CR.LAYERS,))
print('  GRID   = %.3f mm' % (CR.GRID / UM))

b = p.LoadBoard(LIVE)

# Two runs: as-shipped (F,B) and with In2 added.
for tag, layers in (('F,B only (as shipped)', (p.F_Cu, p.B_Cu)),
                    ('F,B,In2', (p.F_Cu, p.B_Cu, p.In2_Cu))):
    CR.LAYERS = layers
    field = CR.Field(b, (0, 0, 80 * UM, 80 * UM), clear=200_000 + 70_711)
    # small bbox around the route
    bbox = (int(27.0 * UM), int(1.0 * UM), int(41.0 * UM), int(9.0 * UM))
    t0 = time.time()
    path, why = CR.route(
        field,
        (int(START[0] * UM), int(START[1] * UM)),
        (int(GOAL[0] * UM), int(GOAL[1] * UM)),
        NET, bbox,
        (p.B_Cu,), (p.B_Cu,),
        deadline_steps=2_000_000, deadline_s=420, seed_radius=4)
    dt = time.time() - t0
    print('\n=== %s ===' % tag)
    print('  result: %s  (%.1fs)' % (why, dt))
    if path:
        vias = sum(1 for a, c in zip(path, path[1:]) if a[2] != c[2])
        print('  %d points, %d layer change(s)' % (len(path), vias))
        inband = [(x / UM, y / UM) for x, y, l in path
                  if CAV[0] - 0.3 <= x / UM <= CAV[2] + 0.3 and y / UM < SAFE_Y]
        print('  points inside the forbidden band: %d' % len(inband))
        for q in inband[:5]:
            print('     (%.3f,%.3f)' % q)
        ys = [y / UM for _, y, _ in path]
        print('  y range %.3f .. %.3f' % (min(ys), max(ys)))
        lays = sorted({b.GetLayerName(l) for _, _, l in path})
        print('  layers used: %s' % ','.join(lays))
    else:
        print('  NO PATH -- claim B not yet supported by this run')
