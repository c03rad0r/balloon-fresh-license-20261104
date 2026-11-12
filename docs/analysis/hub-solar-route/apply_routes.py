#!/usr/bin/env python3
"""Apply the 7 single-layer B.Cu solar-gap routes as REAL copper, on a COPY.

Method
------
Path search is delegated to the router merged as PR #438
(`docs/analysis/solar-8land-verify/route_solar_bitmap.py`) rather than a second
hand-rolled router, because that one carries a negative control proving it can
refuse: `negative_control.py` raises the clearance to 1.50 mm and asserts the
paths change or lengthen. A router without that property found 8 of 9 here and
was wrong.

The one rule difference that matters: the board-edge keep-out is lifted ONLY
under each endpoint pad's own body. The J_W lands are edge-launched by design
(ADR-046/048) and the repo's DRC allow-list scopes `copper_edge_clearance` to
exactly those refs. Applying the 0.50 mm edge rule to the whole board - which an
earlier attempt did - walls off the J_W row and produces FALSE "blocked"
verdicts.

Verification is native: `drc.py` refills zones and runs pcbnew 9.0.9 DRC, and the
violation multiset is compared against the untouched before-board.
"""
import argparse
import importlib.util
import math
import shutil
import sys
from pathlib import Path

import pcbnew as k

HERE = Path(__file__).resolve().parent
UM = 1_000_000
LAYER = 'B.Cu'


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def collect_edge_cuts(board):
    """Every Edge.Cuts segment on the board, as (x1, y1, x2, y2) in mm."""
    cid = board.GetLayerID('Edge.Cuts')
    segs = []
    for dr in board.GetDrawings():
        if dr.GetLayer() == cid and dr.Type() == k.PCB_SHAPE_T:
            segs.append((dr.GetStart().x / UM, dr.GetStart().y / UM,
                         dr.GetEnd().x / UM, dr.GetEnd().y / UM))
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetLayer() == cid and g.Type() == k.PCB_SHAPE_T:
                segs.append((g.GetStart().x / UM, g.GetStart().y / UM,
                             g.GetEnd().x / UM, g.GetEnd().y / UM))
    return segs


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def stamp_segs(segs, blocked, nx, ny, wx0, wy0, grid, r):
    for (x1, y1, x2, y2) in segs:
        i0 = max(0, int((min(x1, x2) - r - wx0) / grid) - 1)
        i1 = min(nx - 1, int((max(x1, x2) + r - wx0) / grid) + 1)
        j0 = max(0, int((min(y1, y2) - r - wy0) / grid) - 1)
        j1 = min(ny - 1, int((max(y1, y2) + r - wy0) / grid) + 1)
        for j in range(j0, j1 + 1):
            py = wy0 + j * grid
            base = j * nx
            for i in range(i0, i1 + 1):
                if seg_dist(wx0 + i * grid, py, x1, y1, x2, y2) < r:
                    blocked[base + i] = 1


def stamp_edge_cuts(board, blocked, nx, ny, wx0, wy0, grid, track_r):
    """Block every grid cell within `track_r` of an Edge.Cuts segment.

    The J_W sockets are cut OUT of the board: each has a 6.0 x 0.5 mm Edge.Cuts
    rectangle (J_W1 x 0..6 y 39.75..40.25, etc). The upstream router models the
    board's outer edge but not these interior cuts, so a trunk can be routed
    straight across one - which is physically a slot through the board and
    measured as 4 new `copper_edge_clearance` violations. Blocking them here is
    the difference between "a path exists on paper" and "a path a fab can make".
    """
    cid = board.GetLayerID('Edge.Cuts')
    segs = []
    for dr in board.GetDrawings():
        if dr.GetLayer() == cid and dr.Type() == k.PCB_SHAPE_T:
            segs.append((dr.GetStart().x / UM, dr.GetStart().y / UM,
                         dr.GetEnd().x / UM, dr.GetEnd().y / UM))
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetLayer() == cid and g.Type() == k.PCB_SHAPE_T:
                segs.append((g.GetStart().x / UM, g.GetStart().y / UM,
                             g.GetEnd().x / UM, g.GetEnd().y / UM))
    r = track_r
    for (x1, y1, x2, y2) in segs:
        i0 = max(0, int((min(x1, x2) - r - wx0) / grid) - 1)
        i1 = min(nx - 1, int((max(x1, x2) + r - wx0) / grid) + 1)
        j0 = max(0, int((min(y1, y2) - r - wy0) / grid) - 1)
        j1 = min(ny - 1, int((max(y1, y2) + r - wy0) / grid) + 1)
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        for j in range(j0, j1 + 1):
            py = wy0 + j * grid
            base = j * nx
            for i in range(i0, i1 + 1):
                px = wx0 + i * grid
                if L2 == 0:
                    d = math.hypot(px - x1, py - y1)
                else:
                    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
                    d = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
                if d < r:
                    blocked[base + i] = 1
    return len(segs)


def merge_collinear(pts, tol=1e-6):
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        scale = math.hypot(bx - ax, by - ay) * math.hypot(cx - ax, cy - ay)
        if scale > 0 and abs(cross) / scale < tol:
            continue
        out.append((bx, by))
    out.append(pts[-1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('board', help='source .kicad_pcb (read only)')
    ap.add_argument('--out', required=True, help='output directory for the copy')
    ap.add_argument('--router', required=True,
                    help='route_solar_bitmap.py with the tested negative control')
    ap.add_argument('--grid', type=float, default=0.15)
    ap.add_argument('--clearance', type=float, default=0.20)
    ap.add_argument('--track-w', type=float, default=0.20)
    ap.add_argument('--edge', type=float, default=0.50)
    ap.add_argument('--window-pad', type=float, default=5.0)
    a = ap.parse_args()

    src = Path(a.board)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in src.parent.glob(src.stem + '.kicad_*'):
        shutil.copy(f, out / f.name)
    dst = out / src.name
    shutil.copy(src, dst)

    R = load_module(a.router, 'rsb')
    board = k.LoadBoard(str(dst))
    net_index = {}
    applied, refused = [], []

    for pi, (net, sa, sb) in enumerate(R.PAIRS):
        pa, pb = R.bcu_pads(board, sa), R.bcu_pads(board, sb)
        if not pa or not pb:
            refused.append((pi, net, sa, sb, 'no B.Cu pad on one end'))
            continue
        A, B = pa[0], pb[0]
        ax, ay = A.GetPosition().x / UM, A.GetPosition().y / UM
        bx, by = B.GetPosition().x / UM, B.GetPosition().y / UM
        win = (min(ax, bx) - a.window_pad, min(ay, by) - a.window_pad,
               max(ax, bx) + a.window_pad, max(ay, by) + a.window_pad)
        blocked, edge_blocked, nx, ny, (wx0, wy0) = R.rasterise(
            board, net, a.grid, a.clearance, a.track_w / 2.0, a.edge, win)
        s = (int(round((ax - wx0) / a.grid)), int(round((ay - wy0) / a.grid)))
        g = (int(round((bx - wx0) / a.grid)), int(round((by - wy0) / a.grid)))

        exempt = set()
        for pad in (A, B):
            bb = pad.GetBoundingBox()
            bb_mm = (bb.GetLeft() / UM, bb.GetTop() / UM,
                     bb.GetRight() / UM, bb.GetBottom() / UM)
            i0 = int((bb_mm[0] - a.grid - wx0) / a.grid)
            i1 = int((bb_mm[2] + a.grid - wx0) / a.grid)
            j0 = int((bb_mm[1] - a.grid - wy0) / a.grid)
            j1 = int((bb_mm[3] + a.grid - wy0) / a.grid)
            for j in range(max(0, j0), min(ny - 1, j1) + 1):
                for i in range(max(0, i0), min(nx - 1, i1) + 1):
                    px, py = wx0 + i * a.grid, wy0 + j * a.grid
                    if (bb_mm[0] - a.grid <= px <= bb_mm[2] + a.grid
                            and bb_mm[1] - a.grid <= py <= bb_mm[3] + a.grid):
                        exempt.add((i, j))
        blocked[s[1] * nx + s[0]] = 0
        blocked[g[1] * nx + g[0]] = 0

        # Interior Edge.Cuts are real obstacles, at the FULL 0.50 mm edge rule for a
        # TRACK (the J_W pads are exempt by the repo's DRC allow-list; a track is not).
        # Measured: modelling them at track-half-width gave 4 new
        # copper_edge_clearance violations at 0.10-0.18 mm actual.
        slot_r = a.edge + a.track_w / 2.0
        slot_segs = collect_edge_cuts(board)
        stamp_segs(slot_segs, blocked, nx, ny, wx0, wy0, a.grid, slot_r)

        # Clear only the LEGAL part of each endpoint pad: inside the pad body AND at
        # least slot_r from every slot segment. This matters because J_W pad 2 ends
        # 0.05 mm from its socket cavity, so the near half of that pad can never take
        # a track - only the far half can.
        def clear_landing(pad):
            bb = pad.GetBoundingBox()
            x0, y0 = bb.GetLeft() / UM, bb.GetTop() / UM
            x1, y1 = bb.GetRight() / UM, bb.GetBottom() / UM
            cells = []
            i0 = int((x0 - a.grid - wx0) / a.grid)
            i1 = int((x1 + a.grid - wx0) / a.grid)
            j0 = int((y0 - a.grid - wy0) / a.grid)
            j1 = int((y1 + a.grid - wy0) / a.grid)
            for j in range(max(0, j0), min(ny - 1, j1) + 1):
                for i in range(max(0, i0), min(nx - 1, i1) + 1):
                    px, py = wx0 + i * a.grid, wy0 + j * a.grid
                    if not (x0 <= px <= x1 and y0 <= py <= y1):
                        continue
                    if min(seg_dist(px, py, *sg) for sg in slot_segs) < slot_r:
                        continue
                    blocked[j * nx + i] = 0
                    cells.append((i, j))
            return cells

        ca, cb = clear_landing(A), clear_landing(B)
        if not ca or not cb:
            refused.append((pi, net, sa, sb,
                            'endpoint pad has no legal landing area clear of the slot'))
            continue

        def nearest(cells, target):
            return min(cells, key=lambda c: (wx0 + c[0] * a.grid - target[0]) ** 2
                       + (wy0 + c[1] * a.grid - target[1]) ** 2)

        s = nearest(ca, (bx, by))
        g = nearest(cb, (ax, ay))

        path = R.bfs(blocked, edge_blocked, nx, ny, s, g, exempt)
        if path is None:
            refused.append((pi, net, sa, sb, 'NO PATH on B.Cu'))
            continue

        pts = [(wx0 + i * a.grid, wy0 + j * a.grid) for i, j in path]
        pts = merge_collinear(pts, tol=1e-3)
        # Pin the ends ON the pads but not at their centres: each J_W socket has an
        # Edge.Cuts slot cut through it, and a track leaving the centre crosses that
        # slot, which DRC reports as copper_edge_clearance 0.00 mm (measured: 4 new
        # violations). Pull each end back to a point inside the pad body, on the line
        # toward its neighbour, so the copper still lands on the pad without crossing
        # the slot.
        def clamp_into(pad, toward):
            bb = pad.GetBoundingBox()
            x0, y0 = bb.GetLeft() / UM, bb.GetTop() / UM
            x1, y1 = bb.GetRight() / UM, bb.GetBottom() / UM
            inset = 0.05
            x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
            px, py = (x0 + x1) / 2, (y0 + y1) / 2
            dx, dy = toward[0] - px, toward[1] - py
            ts = [1.0]
            if dx > 0:
                ts.append((x1 - px) / dx)
            elif dx < 0:
                ts.append((x0 - px) / dx)
            if dy > 0:
                ts.append((y1 - py) / dy)
            elif dy < 0:
                ts.append((y0 - py) / dy)
            t = min([v for v in ts if v > 0], default=1.0)
            return (px + dx * t, py + dy * t)

        pts[0] = clamp_into(A, pts[1])
        pts[-1] = clamp_into(B, pts[-2])

        if net not in net_index:
            n = board.FindNet(net)
            if n is None:
                refused.append((pi, net, sa, sb, 'net not found on board'))
                continue
            net_index[net] = n
        ni = net_index[net]
        length = 0.0
        for p, q in zip(pts, pts[1:]):
            t = k.PCB_TRACK(board)
            t.SetStart(k.VECTOR2I(int(round(p[0] * UM)), int(round(p[1] * UM))))
            t.SetEnd(k.VECTOR2I(int(round(q[0] * UM)), int(round(q[1] * UM))))
            t.SetWidth(int(round(a.track_w * UM)))
            t.SetLayer(board.GetLayerID(LAYER))
            t.SetNet(ni)
            board.Add(t)
            length += math.hypot(q[0] - p[0], q[1] - p[1])
        applied.append({'pair': pi, 'net': net, 'a': sa, 'b': sb,
                        'segments': len(pts) - 1, 'length_mm': round(length, 3),
                        'points': [[round(x, 4), round(y, 4)] for x, y in pts]})
        print(f'applied pair {pi} {net:14s} {sa} -> {sb}  '
              f'{len(pts)-1} segs {length:.2f} mm', flush=True)

    k.SaveBoard(str(dst), board)
    print(f'\napplied {len(applied)} of {len(R.PAIRS)}; refused {len(refused)}')
    for r in refused:
        print(f'  refused {r[0]} {r[1]} {r[2]} -> {r[3]}: {r[4]}')

    import json
    (out / 'routes-applied.json').write_text(json.dumps(
        {'board': src.name, 'applied': applied, 'refused': refused}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
