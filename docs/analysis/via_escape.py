"""Can a trapped pad escape through a NORMAL via placed nearby? (No drill-in-pad.)

The escape probe tested whether a 0.200 mm TRACK can leave each trapped pad and found every
direction blocked within 0.4-1.4 mm. That does not settle whether a VIA can be placed in that
space and reached by a short stub:

  - a track needs 0.100 mm half-width + 0.200 mm clearance = 0.300 mm of room from its centreline
  - a via needs a 0.300 mm land radius + 0.200 mm clearance   = 0.500 mm of room from its centre

Different constraints, so a pad that cannot leak a track can still hand off to a via and continue
on the other layer. This is fully within S1: 0.600 mm land / 0.300 mm drill, 0.250 mm hole-to-hole,
no drill-in-pad, nothing added inside the pad.

Scans a grid around each pad, keeps sites where
  1. the 0.600 mm land clears all FOREIGN copper at S1 + guard, on BOTH outer layers
  2. the 0.300 mm drill respects hole-to-hole 0.250 mm against every existing hole
  3. a straight 0.200 mm F.Cu stub from the pad centre reaches the site clear of foreign copper
and reports the reachable sites, nearest first. Read-only.
"""
import math
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')

import pcbnew as p

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')

TRACK_R = 100_000          # 0.200 mm track
LAND_R = 300_000           # 0.600 mm land
DRILL_R = 150_000          # 0.300 mm drill
CLEAR = 200_000
GUARD = CLEAR + 70_711
HOLE_TO_HOLE = 250_000

TARGETS = [t for t in os.environ.get(
    'VIA_TARGETS', '/EN:U1:3,/SPI2_SCK:U1:4').split(',') if t]
MAXR = 3.0                 # mm search radius around the pad
STEP_MM = 0.050            # grid step


def main():
    b = p.LoadBoard(LIVE)

    # every foreign copper shape, bucketed for speed
    CELL = 2_000_000

    def key(x, y):
        return (int(x // CELL), int(y // CELL))

    obst = {}
    for t in b.GetTracks():
        nets = str(t.GetNetname())
        shp = t.GetEffectiveShape(0)
        lay = t.GetLayer()
        bb = shp.BBox()
        for ix in range(int(bb.GetLeft() // CELL), int(bb.GetRight() // CELL) + 1):
            for iy in range(int(bb.GetTop() // CELL), int(bb.GetBottom() // CELL) + 1):
                obst.setdefault((ix, iy), []).append((nets, lay, shp))
    for f in b.GetFootprints():
        for pad in f.Pads():
            nets = str(pad.GetNetname())
            for lay in (p.F_Cu, p.B_Cu):
                if not pad.IsOnLayer(lay):
                    continue
                shp = pad.GetEffectiveShape(lay)
                bb = shp.BBox()
                for ix in range(int(bb.GetLeft() // CELL), int(bb.GetRight() // CELL) + 1):
                    for iy in range(int(bb.GetTop() // CELL), int(bb.GetBottom() // CELL) + 1):
                        obst.setdefault((ix, iy), []).append((nets, lay, shp))

    # existing holes for hole-to-hole
    holes = []
    for t in b.GetTracks():
        if t.Type() == p.PCB_VIA_T:
            q = t.GetPosition()
            holes.append((q.x, q.y, t.GetDrill() / 2))
    for f in b.GetFootprints():
        for pad in f.Pads():
            d = pad.GetDrillSize()
            if d.x > 0:
                q = pad.GetPosition()
                holes.append((q.x, q.y, d.x / 2))

    for spec in TARGETS:
        parts = spec.split(':')
        if len(parts) != 3:
            continue
        net, ref, pin = parts
        pad = None
        for f in b.GetFootprints():
            if f.GetReference() != ref:
                continue
            for pd in f.Pads():
                if str(pd.GetNumber()) == str(pin):
                    pad = pd
        if pad is None or not pad.IsOnLayer(p.F_Cu):
            print('%s %s.%s: not an F.Cu pad' % (net, ref, pin))
            continue
        c = pad.GetPosition()
        px, py = c.x / UM, c.y / UM
        print('%s  pad %s.%s (%.3f, %.3f)  scanning %0.1f mm radius for reachable via sites'
              % (net, ref, pin, px, py, MAXR))

        def cand_shapes(x, y, r):
            k = key(int(x * UM), int(y * UM))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for item in obst.get((k[0] + dx, k[1] + dy), ()):
                        yield item

        good = []
        n = int(MAXR / STEP_MM)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                x, y = px + i * STEP_MM, py + j * STEP_MM
                d = math.hypot(x - px, y - py)
                # A FIXED 0.35 mm minimum is WRONG: this pad is 1.500 x 0.900 mm, so its own
                # half-extent is 0.750 mm and every site within 0.35 mm of the centre lies INSIDE
                # the pad copper -- that is drill-in-pad, which is not authorised. Measured: the
                # first version of this probe reported "95 reachable sites" that were all inside
                # the pad. Require the DRILL to be geometrically clear of the pad instead.
                drill = p.SHAPE_CIRCLE(p.VECTOR2I(int(round(x * UM)), int(round(y * UM))), DRILL_R)
                if p.SHAPE.Collide(pad.GetEffectiveShape(p.F_Cu), drill, 0):
                    continue                    # drill would sit in the pad -> drill-in-pad
                if d < 0.35 or d > MAXR:
                    continue
                cx, cy = int(round(x * UM)), int(round(y * UM))
                land = p.SHAPE_CIRCLE(p.VECTOR2I(cx, cy), LAND_R)
                # 1. land clears foreign copper on both outer layers
                bad = False
                for nets, lay, shp in cand_shapes(x, y, LAND_R):
                    if nets == net:
                        continue
                    if p.SHAPE.Collide(shp, land, GUARD):
                        bad = True
                        break
                if bad:
                    continue
                # 2. hole-to-hole
                for hx, hy, hr in holes:
                    if math.hypot(hx - cx, hy - cy) < (DRILL_R + hr + HOLE_TO_HOLE):
                        bad = True
                        break
                if bad:
                    continue
                # 3. stub from pad centre to the site, F.Cu, clear of foreign copper
                stub = p.SHAPE_SEGMENT(p.VECTOR2I(int(round(px * UM)), int(round(py * UM))),
                                       p.VECTOR2I(cx, cy), TRACK_R)
                for nets, lay, shp in cand_shapes(x, y, TRACK_R):
                    if nets == net or lay not in (p.F_Cu,):
                        continue
                    if p.SHAPE.Collide(shp, stub, GUARD):
                        bad = True
                        break
                if bad:
                    continue
                good.append((d, x, y))

        good.sort()
        if not good:
            print('   NO reachable via site within %.1f mm -> genuinely enclosed for a via too'
                  % MAXR)
        else:
            print('   %d reachable via site(s); nearest %.3f mm at (%.3f, %.3f)'
                  % (len(good), good[0][0], good[0][1], good[0][2]))
            for d, x, y in good[:5]:
                print('      %.3f mm  (%.3f, %.3f)' % (d, x, y))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
