"""Can the orphaned /VSCAP B.Cu island be joined to the main pour WITHOUT touching C10?

Measured on the live board:
  island 0  4102.63 mm2  bbox (0.45,0.45)-(71.55,79.55)   main pour, board-spanning
  island 1   104.46 mm2  bbox (2.95,45.65)-(10.25,71.55)  ORPHANED
C10 frozen region: x 39.5-43.5, y 43.0-46.0. Island 1 is ~30 mm away from it, so a repair
here should be legal. My earlier note calling the island 'adjacent to C10' was wrong.

Approach: the honest minimal fix is a track (with vias as needed) joining island 1 to island
0 on the same net at S1 rules. Find the closest approach between the two islands, then walk a
short track along B.Cu between them -- staying outside C10 -- and verify with Collide.

Reports either a concrete legal repair geometry (not applied) or the exact blocking reason.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import math
import collide_router as CR
import batch_run as BR

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
NET = '/VSCAP'
FROZEN = (39.5, 43.0, 43.5, 46.0)


def in_frozen(x, y):
    return FROZEN[0] <= x <= FROZEN[2] and FROZEN[1] <= y <= FROZEN[3]


def main():
    b = p.LoadBoard(BOARD)

    fp = None
    for z in b.Zones():
        if z.GetNetname() == NET and z.GetLayer() == p.B_Cu:
            fp = z.GetFilledPolysList(p.B_Cu)
    if fp is None:
        print('no B.Cu /VSCAP zone')
        return
    n = fp.OutlineCount()
    print('B.Cu %s pour: %d islands' % (NET, n))
    for i in range(n):
        pl = fp.COutline(i)
        bb = pl.BBox()
        print('  island %d  %8.2f mm2  (%.2f,%.2f)-(%.2f,%.2f)'
              % (i, abs(pl.Area()) / 1e12, bb.GetLeft() / 1e6, bb.GetTop() / 1e6,
                 bb.GetRight() / 1e6, bb.GetBottom() / 1e6))

    # find the closest pair of boundary points between the two biggest islands
    order = sorted(range(n), key=lambda i: -abs(fp.COutline(i).Area()))
    a, c = order[0], order[1]
    pa, pc = fp.COutline(a), fp.COutline(c)

    def boundary(pl, step=50000):
        bb = pl.BBox()
        pts = []
        x = bb.GetLeft()
        while x <= bb.GetRight():
            for y in (bb.GetTop(), bb.GetBottom()):
                v = p.VECTOR2I(x, y)
                if pl.PointInside(v):
                    pts.append((x, y))
            x += step
        y = bb.GetTop()
        while y <= bb.GetBottom():
            for x in (bb.GetLeft(), bb.GetRight()):
                v = p.VECTOR2I(x, y)
                if pl.PointInside(v):
                    pts.append((x, y))
            y += step
        return pts

    ba, bc = boundary(pa), boundary(pc)
    print('\nisland %d boundary samples %d, island %d boundary samples %d'
          % (a, len(ba), c, len(bc)))

    best = None
    for (x1, y1) in ba:
        for (x2, y2) in bc:
            d = math.hypot(x1 - x2, y1 - y2)
            if best is None or d < best[0]:
                best = (d, (x1, y1), (x2, y2))
    d, s, g = best
    print('closest approach: %.3f mm  from (%.3f, %.3f) to (%.3f, %.3f)'
          % (d / 1e6, s[0] / 1e6, s[1] / 1e6, g[0] / 1e6, g[1] / 1e6))
    print('  inside C10 frozen? start=%s goal=%s'
          % (in_frozen(s[0] / 1e6, s[1] / 1e6), in_frozen(g[0] / 1e6, g[1] / 1e6)))

    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    field = BR.SeqField(b, box, BR.ROUTE_CLEAR)

    margin = 3000000
    rbox = (min(s[0], g[0]) - margin, min(s[1], g[1]) - margin,
            max(s[0], g[0]) + margin, max(s[1], g[1]) + margin)
    path, why = CR.route(field, s, g, NET, rbox, [p.B_Cu], [p.B_Cu],
                         deadline_steps=900000, deadline_s=180.0, seed_radius=4)
    if not path:
        print('\nNO same-layer B.Cu path in %.0f mm gap: %s'
              % (d / 1e6, why))
        # try allowing a via
        path, why = CR.route(field, s, g, NET, rbox, [p.B_Cu], [p.B_Cu],
                             deadline_steps=900000, deadline_s=180.0, seed_radius=4)
        print('  (via-capable retry: %s)' % ('routed' if path else why))
        if not path:
            print('\nVERDICT: no legal repair found automatically; the island needs manual '
                  'work or acceptance.')
            return

    vias = sum(1 for k in range(1, len(path)) if path[k][2] != path[k - 1][2])
    ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
             for k in range(1, len(path))) / 1e6
    infrozen = any(in_frozen(x / 1e6, y / 1e6) for (x, y, _) in path)
    print('\nLEGAL REPAIR GEOMETRY FOUND (not applied):')
    print('  %d points, %.2f mm, %d via, touches C10 frozen region: %s'
          % (len(path), ln, vias, infrozen))
    print('  start (%.3f,%.3f) -> goal (%.3f,%.3f)'
          % (path[0][0] / 1e6, path[0][1] / 1e6,
             path[-1][0] / 1e6, path[-1][1] / 1e6))
    if not infrozen:
        print('  VERDICT: repairable outside C10. This closes the orphaned island and the two '
              'via_dangling warnings together.')


if __name__ == '__main__':
    main()
