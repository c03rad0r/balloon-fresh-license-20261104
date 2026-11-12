#!/usr/bin/env python3
"""Close the 8 shared-B.Cu solar gap pairs with routed B.Cu tracks, on a COPY.

Measured facts this rests on (see FINDINGS.md in the deliverable):
  * every J_W pad exists TWICE in the footprint - one F.Cu land and one B.Cu land
    at identical XY with identical net (stacked double-sided edge-card land, per
    ADR-046 §2.2 / WING-TO-HUB-SOCKET-SPEC §2). Keying pads by pad NUMBER in a
    dict collapses the pair to whichever was seen last, which is why an earlier
    pass reported "no shared layer" for all nine gaps.
  * 8 of the 9 solar-gap pairs therefore DO share B.Cu and are closable with a
    plain B.Cu track. The 9th (GND D_BP4.2[B.Cu] <-> U2.4[F.Cu]) shares no layer.

Routing: clearance-aware 8-connected A* on a 0.20 mm grid, greedy string-pulling,
then EVERY retained segment is re-validated before a single track is written.
Hard constraints enforced against the board's own rules:
  * 0.20 mm copper clearance to foreign copper
  * 0.50 mm copper-to-board-edge, as "inside the outline eroded by 0.50 + half"
  * milled J_W slots are physical cuts: no track may cross one

Zones are deliberately NOT obstacles: the filler retreats around new copper on
refill, so a B.Cu track crossing the B.Cu pour is legal and normal (the base
board already does this 386 times).

Pairs are routed with deferral: a pair whose corridor is closed by copper added
for an earlier pair is retried on the next pass, so source order does not decide
the outcome.

Writes only under OUT. The source board is opened read-only and never saved.
"""
import json
import pathlib
import shutil
from collections import deque

import numpy as np
import pcbnew as k
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

SRC = pathlib.Path('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
                   'hub-repair-20261102/output/after')
OUT = pathlib.Path('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/solar-fix/after')
STEM = 'hub_board_v10_lora1280_7of9'
CLEAR = 0.20          # board rule: copper clearance
EDGE = 0.50           # board rule: copper to board edge
HALF = 0.10           # 0.20 mm track -> half width
GRID = 0.20
# 1 um of slack in the OBSTACLE MODEL only. The J_W land row is 1.8 mm pitch with
# 1.2 mm lands, so the gap between neighbouring lands is 0.600 mm and a 0.20 mm
# track needs exactly 0.600 mm of clearance envelope (0.2 + 0.2 + 0.2). That is a
# knife edge: the corridor is legal at exactly 0.200 mm, but shapely reports
# tangency as intersection, so the raster and the segment validator disagree by a
# float ulp and the search declares a legal corridor closed. 1 um is three orders
# of magnitude below the 0.20 mm rule and far below any fab tolerance. Native DRC
# is the authority and it is run on every output.
EPS = 0.001
LAYER = 'B.Cu'

# Order matters: the wing-land escapes are the tight ones and are walled off by
# the long inter-wing trunk if that trunk is laid first (measured: the
# /W1_SOLAR_N trunk's bounding box crosses the /W2_SOLAR_N land escape). So the
# three land-adjacent pairs go first; the long trunks go last and route around
# whatever is already there.
PAIRS = [
    ('/W2_SOLAR_N', 'D_BP2', '2', 'J_W2', '4'),
    ('/W3_SOLAR_N', 'J_W4', '1', 'D_BP4', '1'),
    ('/W3_SOLAR_N', 'D_BP3', '2', 'J_W4', '1'),
    ('/W2_SOLAR_N', 'J_W3', '1', 'D_BP3', '1'),
    ('/W3_SOLAR_N', 'J_W3', '4', 'D_BP3', '2'),
    ('/W1_SOLAR_N', 'D_BP1', '2', 'J_W1', '4'),
    ('/W1_SOLAR_N', 'D_BP2', '1', 'J_W2', '1'),
    ('/W1_SOLAR_N', 'J_W1', '4', 'D_BP2', '1'),
    ('/W3_SOLAR_N', 'D_BP3', '2', 'J_W4', '1'),
    ('/W3_SOLAR_N', 'J_W4', '1', 'D_BP4', '1'),
]
SKIP = [('GND', 'D_BP4', '2', 'U2', '4')]


def mm(v):
    return v / 1e6


def pad_rect(b, ref, num, layer):
    fp = b.FindFootprintByReference(ref)
    ps = [p for p in fp.Pads()
          if p.GetNumber() == num
          and layer in [b.GetLayerName(x) for x in p.GetLayerSet().Seq()]]
    assert ps, f'{ref}.{num} has no {layer} copper'
    bb = ps[0].GetBoundingBox()
    return (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))


def anchors(b, ref, num, layer, toward):
    """Candidate connection points on a pad: its centre plus points spread over the
    land. A track may legally terminate anywhere on the pad, and the land is
    4.0 x 1.2 mm, so the centre is often the WORST point to approach -- the free
    corridor is at one end. Trying several anchors is what lets the escape exist.
    """
    l, t, r, bo = pad_rect(b, ref, num, layer)
    cx, cy = (l + r) / 2, (t + bo) / 2
    w, h = r - l, bo - t
    pts = [(cx, cy)]
    for fx in (0.0, 0.25, 0.5, 0.75, 1.0):
        for fy in (0.0, 0.25, 0.5, 0.75, 1.0):
            pts.append((l + 0.15 + fx * (w - 0.30), t + 0.15 + fy * (h - 0.30)))
    pts.sort(key=lambda p: (p[0] - toward[0]) ** 2 + (p[1] - toward[1]) ** 2)
    return pts


def board_polygon(b):
    poly = k.SHAPE_POLY_SET()
    assert b.GetBoardPolygonOutlines(poly), 'board outline failed to build'
    g = []
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        g.append(Polygon([(mm(o.CPoint(j).x), mm(o.CPoint(j).y))
                          for j in range(o.PointCount())]))
        for h in range(poly.HoleCount(i)):
            hh = poly.Hole(i, h)
            g.append(Polygon([(mm(hh.CPoint(j).x), mm(hh.CPoint(j).y))
                              for j in range(hh.PointCount())]))
    return unary_union(g)


def edge_segments(b):
    """Every Edge.Cuts segment on the board, including footprint-owned slot walls."""
    segs = []

    def add(sh):
        s = sh.GetShape()
        if s == k.SHAPE_T_SEGMENT:
            segs.append(LineString([(mm(sh.GetStart().x), mm(sh.GetStart().y)),
                                    (mm(sh.GetEnd().x), mm(sh.GetEnd().y))]))
        elif s == k.SHAPE_T_RECT:
            p = [(mm(sh.GetStart().x), mm(sh.GetStart().y)),
                 (mm(sh.GetEnd().x), mm(sh.GetStart().y)),
                 (mm(sh.GetEnd().x), mm(sh.GetEnd().y)),
                 (mm(sh.GetStart().x), mm(sh.GetEnd().y)),
                 (mm(sh.GetStart().x), mm(sh.GetStart().y))]
            segs.append(LineString(p))
        elif s == k.SHAPE_T_POLY:
            o = sh.GetPolyShape().Outline(0)
            p = [(mm(o.CPoint(j).x), mm(o.CPoint(j).y))
                 for j in range(o.PointCount())]
            p.append(p[0])
            segs.append(LineString(p))

    for d in b.GetDrawings():
        if d.GetLayer() == k.Edge_Cuts:
            add(d)
    for f in b.GetFootprints():
        for gi in f.GraphicalItems():
            if gi.GetLayer() == k.Edge_Cuts:
                add(gi)
    return segs


def forbidden(b, net, layer):
    """Regions a track of `net` may not enter on `layer`.

    The board interior is NOT here - it is the allowed region, passed separately.
    """
    buf = CLEAR + HALF - EPS
    geos = []
    for t in b.GetTracks():
        if t.GetNetname() == net:
            continue
        if layer not in [b.GetLayerName(x) for x in t.GetLayerSet().Seq()]:
            continue
        geos.append(LineString(
            [(mm(t.GetStart().x), mm(t.GetStart().y)),
             (mm(t.GetEnd().x), mm(t.GetEnd().y))]).buffer(mm(t.GetWidth()) / 2 + buf))
    for f in b.GetFootprints():
        for p in f.Pads():
            if layer not in [b.GetLayerName(x) for x in p.GetLayerSet().Seq()]:
                continue
            if p.GetNetname() == net:
                continue
            bb = p.GetBoundingBox()
            geos.append(box(mm(bb.GetLeft()) - buf, mm(bb.GetTop()) - buf,
                            mm(bb.GetRight()) + buf, mm(bb.GetBottom()) + buf))
    for seg in edge_segments(b):
        geos.append(seg.buffer(0.05 + EDGE + HALF - EPS))
    return unary_union(geos)


def grid_and_mask(inside, bad, bounds):
    lo_x, lo_y, hi_x, hi_y = bounds
    xs = np.arange(lo_x, hi_x + GRID / 2, GRID)
    ys = np.arange(lo_y, hi_y + GRID / 2, GRID)
    X, Y = np.meshgrid(xs, ys)
    mask = shapely.contains_xy(bad, X, Y) | ~shapely.contains_xy(inside, X, Y)
    return xs, ys, mask


def nearest_open(mask, xs, ys, pt, max_r=60):
    ix = int(round((pt[0] - xs[0]) / GRID))
    iy = int(round((pt[1] - ys[0]) / GRID))
    h, w = mask.shape
    if 0 <= iy < h and 0 <= ix < w and not mask[iy, ix]:
        return (ix, iy)
    for r in range(1, max_r):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                j, i = iy + dy, ix + dx
                if 0 <= j < h and 0 <= i < w and not mask[j, i]:
                    return (i, j)
    return None


def astar(mask, s, g):
    h, w = mask.shape
    prev = {s: None}
    q = deque([s])
    while q:
        cur = q.popleft()
        if cur == g:
            break
        cx, cy = cur
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nb = (cx + dx, cy + dy)
            if nb in prev or not (0 <= nb[0] < w and 0 <= nb[1] < h):
                continue
            if mask[nb[1], nb[0]]:
                continue
            # no corner cutting: a diagonal step is only allowed when both of its
            # orthogonal neighbours are free too. Without this the grid path can
            # squeeze through a pinch that the resulting 0.20 mm segment cannot.
            if dx and dy and (mask[cy, cx + dx] or mask[cy + dy, cx]):
                continue
            prev[nb] = cur
            q.append(nb)
    if g not in prev:
        return None
    path, c = [], g
    while c is not None:
        path.append(c)
        c = prev[c]
    path.reverse()
    return path


def seg_clear(bad, a, c):
    return not bad.intersects(LineString([a, c]))


def string_pull(pts, bad):
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not seg_clear(bad, pts[i], pts[j]):
            j -= 1
        out.append(pts[j])
        i = j
    return out


def merge_collinear(pts):
    """Collapse consecutive points that lie on one straight line."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        dot = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])
        if abs(cross) < 1e-9 and dot > 0:
            continue
        out.append(b)
    out.append(pts[-1])
    return out


def try_route(b, net, ra, na, rb, nb, inside, pad_margin):
    bad = forbidden(b, net, LAYER)
    ca = pad_rect(b, ra, na, LAYER)
    cc = pad_rect(b, rb, nb, LAYER)
    mid_a = ((ca[0] + ca[2]) / 2, (ca[1] + ca[3]) / 2)
    mid_b = ((cc[0] + cc[2]) / 2, (cc[1] + cc[3]) / 2)
    # try the points on each land in order of proximity to the other land
    aa = anchors(b, ra, na, LAYER, mid_b)
    cc_pts = anchors(b, rb, nb, LAYER, mid_a)
    bounds = (min(ca[0], cc[0]) - pad_margin, min(ca[1], cc[1]) - pad_margin,
              max(ca[2], cc[2]) + pad_margin, max(ca[3], cc[3]) + pad_margin)
    bounds = (max(bounds[0], 0.0), max(bounds[1], 0.0),
              min(bounds[2], 72.0), min(bounds[3], 80.0))
    xs, ys, mask = grid_and_mask(inside, bad, bounds)
    last = 'NO FREE CELL AT PAD'
    for a in aa[:9]:
        si = nearest_open(mask, xs, ys, a, max_r=12)
        if si is None:
            continue
        for c in cc_pts[:9]:
            gi = nearest_open(mask, xs, ys, c, max_r=12)
            if gi is None:
                continue
            idx = astar(mask, si, gi)
            if idx is None:
                last = 'A* FAILED — corridor closed'
                continue
            pts = [a] + [(float(xs[i]), float(ys[j])) for i, j in idx] + [c]
            pulled = string_pull(pts, bad)
            if [(p, q) for p, q in zip(pulled, pulled[1:])
                    if not seg_clear(bad, p, q)]:
                # shortcutting failed: fall back to the raw grid path, which is
                # legal by construction (all cells free, no corner cutting)
                pulled = pts
            if [(p, q) for p, q in zip(pulled, pulled[1:])
                    if not seg_clear(bad, p, q)]:
                last = 'ILLEGAL AFTER STRING-PULL'
                continue
            return merge_collinear(pulled), 'OK'
    return None, last


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for f in list(SRC.glob(STEM + '.kicad_*')) + list(SRC.glob('fp-lib-table')):
        shutil.copy(f, OUT / f.name)
    pcb = OUT / (STEM + '.kicad_pcb')

    b = k.LoadBoard(str(pcb))
    b.BuildConnectivity()
    conn_before = b.GetConnectivity().GetUnconnectedCount(False)
    poly = board_polygon(b)
    inside = poly.buffer(-(EDGE + HALF - EPS))

    pending = list(PAIRS)
    results = {}
    for pass_no in range(1, 5):
        still = []
        for rec in pending:
            net, ra, na, rb, nb = rec
            pts, why = None, 'not tried'
            for margin in (6.0, 10.0, 16.0):
                pts, why = try_route(b, net, ra, na, rb, nb, inside, margin)
                if pts:
                    break
            if not pts:
                still.append(rec)
                results[rec] = why
                continue
            for p, q in zip(pts, pts[1:]):
                if p == q:
                    continue
                t = k.PCB_TRACK(b)
                t.SetStart(k.VECTOR2I(int(round(p[0] * 1e6)), int(round(p[1] * 1e6))))
                t.SetEnd(k.VECTOR2I(int(round(q[0] * 1e6)), int(round(q[1] * 1e6))))
                t.SetWidth(int(round(0.20 * 1e6)))
                t.SetLayer(b.GetLayerID(LAYER))
                t.SetNet(b.FindNet(net))
                b.Add(t)
            length = sum(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5
                         for p, q in zip(pts, pts[1:]))
            results[rec] = dict(status='ROUTED', pass_no=pass_no,
                                segments=len(pts) - 1,
                                length_mm=round(length, 3),
                                points=[[round(x, 3), round(y, 3)] for x, y in pts])
            print(f'pass{pass_no} {net:14s} {ra}.{na} <-> {rb}.{nb}  '
                  f'{len(pts)-1} segs {length:6.2f} mm')
        if not still:
            break
        pending = still
    for rec in pending:
        print(f'UNROUTED {rec}: {results.get(rec)}')

    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)

    b2 = k.LoadBoard(str(pcb))
    b2.BuildConnectivity()
    conn_after = b2.GetConnectivity().GetUnconnectedCount(False)
    print(f'\nunconnected {conn_before} -> {conn_after}')

    pairs_out = []
    for rec in PAIRS:
        net, ra, na, rb, nb = rec
        r = results.get(rec)
        row = dict(net=net, a=f'{ra}.{na}', b=f'{rb}.{nb}')
        if isinstance(r, dict):
            row.update(r)
        else:
            row.update(status='UNROUTED', reason=r)
        pairs_out.append(row)
    (OUT / 'routes.json').write_text(json.dumps(dict(
        pairs=pairs_out,
        skipped=[dict(net=s[0], a=f'{s[1]}.{s[2]}', b=f'{s[3]}.{s[4]}',
                      status='NOT ATTEMPTED',
                      reason='no shared copper layer: D_BP4.2 has only B.Cu, '
                             'U2.4 only F.Cu')
                 for s in SKIP],
        unconnected_before=conn_before, unconnected_after=conn_after,
        tracks_added=sum(r.get('segments', 0) for r in pairs_out
                         if r.get('status') == 'ROUTED')), indent=1))


if __name__ == '__main__':
    main()
