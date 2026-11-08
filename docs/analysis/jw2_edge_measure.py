"""Measure the TRUE distance from J_W2 pads to the board outline edge.

DRC claims 0.0500 mm against a 0.5000 mm rule. That is either the board's most serious
fabrication blocker or a misread, and it decides whether the order can go out. So measure
it directly instead of trusting the report: bisect with SHAPE::Collide (the only trusted
decision primitive on this board -- SHAPE::Distance has been wrong by 0.235 mm here).

Method: for each J_W2 pad, expand a disc from radius 0 upward and find the smallest radius
at which it collides with the board outline. CollideEdge is used for the outline because
SHAPE_POLY_SET.Collide has containment semantics and is always true inside a board.

Also reports where the board edge actually is near J_W2, and prints the edge clearance
constraint from the board's design settings so the rule value is read from the board, not
assumed.
"""
import json
import pcbnew as p

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
OUT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/jw2-edge.json'


def dist_to_outline(outline, shape, hi=6000000, lo=0):
    """Clearance from a pad shape to the board OUTLINE EDGE.

    CollideEdge takes a VECTOR2I point (not a shape), so this walks the pad's own bounding
    box perimeter at 10 um resolution and bisects the nearest point down to 0.5 um. The pad
    is a convex rectangle in every case here, so its perimeter contains the closest point.

    CollideEdge is used because SHAPE_POLY_SET.Collide includes containment: it returns true
    for any shape anywhere inside the board, which drove an earlier version of this
    measurement to 0.0003 mm for pads that are millimetres from the edge.
    """
    bb = shape.BBox()
    xs = [bb.GetLeft(), (bb.GetLeft() + bb.GetRight()) // 2, bb.GetRight()]
    ys = [bb.GetTop(), (bb.GetTop() + bb.GetBottom()) // 2, bb.GetBottom()]
    pts = set()
    step = 10000
    for x in range(bb.GetLeft(), bb.GetRight() + 1, step):
        pts.add((x, bb.GetTop()))
        pts.add((x, bb.GetBottom()))
    for y in range(bb.GetTop(), bb.GetBottom() + 1, step):
        pts.add((bb.GetLeft(), y))
        pts.add((bb.GetRight(), y))

    best = None
    for (x, y) in pts:
        pv = p.VECTOR2I(x, y)
        if not outline.CollideEdge(pv, None, hi):
            continue
        a, b = lo, hi
        while b - a > 500:
            mid = (a + b) // 2
            if outline.CollideEdge(pv, None, mid):
                b = mid
            else:
                a = mid
        if best is None or b < best:
            best = b
    return best


def main():
    b = p.LoadBoard(BOARD)

    outline = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline)
    bb = outline.BBox()
    print('board outline bbox: (%.3f, %.3f) - (%.3f, %.3f) mm'
          % (bb.GetLeft() / 1e6, bb.GetTop() / 1e6,
             bb.GetRight() / 1e6, bb.GetBottom() / 1e6))

    # the edge clearance rule as the board states it
    ds = b.GetDesignSettings()
    rule = None
    for attr in ('m_CopperEdgeClearance', 'm_EdgeClearance'):
        if hasattr(ds, attr):
            rule = getattr(ds, attr)
            print('board edge-clearance rule (%s): %.4f mm' % (attr, rule / 1e6))
            break
    if rule is None:
        print('board edge-clearance rule: not exposed on DesignSettings')

    rows = []
    for f in b.GetFootprints():
        if f.GetReference() != 'J_W2':
            continue
        for q in f.Pads():
            c = q.GetPosition()
            for ln in (p.F_Cu, p.B_Cu):
                if not q.IsOnLayer(ln):
                    continue
                sh = q.GetEffectiveShape(ln)
                d = dist_to_outline(outline, sh)
                rows.append({'pad': q.GetNumber(), 'net': q.GetNetname(),
                             'x': round(c.x / 1e6, 3), 'y': round(c.y / 1e6, 3),
                             'layer': b.GetLayerName(ln),
                             'gap_to_edge_mm': None if d is None else round(d / 1e6, 4)})
                print('  pad %-2s %-16s (%7.3f, %6.3f) %-5s  edge gap %s mm'
                      % (q.GetNumber(), q.GetNetname(), c.x / 1e6, c.y / 1e6,
                         b.GetLayerName(ln),
                         'no collision found' if d is None else '%.4f' % (d / 1e6)))

    gaps = [r['gap_to_edge_mm'] for r in rows if r['gap_to_edge_mm'] is not None]
    print('\n=== SUMMARY')
    if gaps:
        print('  pads measured: %d   min gap %.4f mm   max gap %.4f mm'
              % (len(gaps), min(gaps), max(gaps)))
        if rule:
            print('  rule %.4f mm -> %s'
                  % (rule / 1e6,
                     'VIOLATION (real fab blocker)' if min(gaps) < rule / 1e6 - 1e-6
                     else 'no violation'))
        print('\n  VERDICT: %s'
              % ('the 0.05 mm claim does NOT reproduce -- pads are further from the edge '
                 'than DRC says' if min(gaps) > 0.2 else
                 'CONFIRMED near-edge -- pads really are very close to the outline, so the '
                 'DRC condition is real and is a fabrication decision, not a tool artefact'))
    json.dump({'rule_mm': None if rule is None else rule / 1e6, 'pads': rows},
              open(OUT, 'w'), indent=2)


if __name__ == '__main__':
    main()
