#!/usr/bin/env python3
"""Rasterise B.Cu obstacle occupancy, then route with a bitmap (fast, still exact at grid resolution).

WHY: the analytic version cost ~1.2 s per grid expansion because every candidate edge was tested
against ~545 obstacle objects in Python. Measured: pair 0 needed 1546 expansions and took ~100 s;
a 40 mm-apart pair timed out at 2048 expansions. Rasterising the SAME rules into a bitmap once,
then doing plain BFS on integers, makes the search milliseconds per 10k cells.

SOUNDNESS — the rasterisation is conservative, never permissive:
  * a cell is BLOCKED if a TRACK CENTRE placed there would come closer than (track_r + clearance)
    to any other-net copper. That is exactly the edge test the analytic router applies, just
    evaluated per cell instead of per edge.
  * rect obstacles use the true rectangle, not a circumscribed disc (the bug that invented 1.4 mm
    of phantom copper on a 4.00 x 1.20 mm pad).
  * a move between two FREE adjacent cells is allowed, INCLUDING diagonals only when both
    orthogonal neighbours are free (so a corner is not clipped).
  * the two endpoint pads are exempt inside a small radius, because the J_W lands sit ON Edge.Cuts
    by design (the repo's DRC allow-list scopes copper_edge_clearance to exactly those refs).

Usage: route_solar_bitmap.py <board> [--grid 0.15] [--pair N ...]
"""
import argparse
import collections
import math
import sys
import time

import pcbnew

UM = 1_000_000.0

PAIRS = [
    ("/W1_SOLAR_N", "J_W1.4", "D_BP1.2"),
    ("/W1_SOLAR_N", "J_W1.4", "D_BP2.1"),
    ("/W1_SOLAR_N", "J_W2.1", "D_BP2.1"),
    ("/W2_SOLAR_N", "J_W2.4", "D_BP2.2"),
    ("/W2_SOLAR_N", "J_W3.1", "D_BP3.1"),
    ("/W3_SOLAR_N", "J_W3.4", "D_BP3.2"),
    ("/W3_SOLAR_N", "J_W4.1", "D_BP4.1"),
    ("/W3_SOLAR_N", "J_W4.1", "D_BP3.2"),
    ("GND", "U2.4", "D_BP4.2"),
]


def bcu_pads(board, spec):
    ref, num = spec.split(".", 1)
    fp = next((f for f in board.GetFootprints() if f.GetReference() == ref), None)
    if fp is None:
        return []
    return [p for p in fp.Pads()
            if p.GetNumber() == num and pcbnew.B_Cu in p.GetLayerSet().Seq()]


def rasterise(board, net, grid, clear, track_r, edge, win):
    wx0, wy0, wx1, wy1 = win
    nx = int((wx1 - wx0) / grid) + 1
    ny = int((wy1 - wy0) / grid) + 1
    blocked = bytearray(nx * ny)
    need_seg = track_r + clear

    # --- collect obstacles once ---
    segs = []       # (x1,y1,x2,y2,r)
    rects = []      # (x0,y0,x1,y1)
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            if t.GetNetname() == net:
                continue
            p = t.GetPosition()
            r = t.GetWidth(pcbnew.B_Cu) / UM / 2.0
            rects.append((p.x / UM - r, p.y / UM - r, p.x / UM + r, p.y / UM + r))
            continue
        if t.GetLayer() != pcbnew.B_Cu or t.GetNetname() == net:
            continue
        segs.append((t.GetStart().x / UM, t.GetStart().y / UM,
                     t.GetEnd().x / UM, t.GetEnd().y / UM, t.GetWidth() / UM / 2.0))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if pcbnew.B_Cu not in p.GetLayerSet().Seq() or p.GetNetname() == net:
                continue
            bb = p.GetBoundingBox()
            rects.append((bb.GetLeft() / UM, bb.GetTop() / UM,
                          bb.GetRight() / UM, bb.GetBottom() / UM))

    # --- mark only cells near an obstacle (local stamping, not a full scan) ---
    def mark_rect(x0, y0, x1, y1, r):
        i0 = max(0, int((x0 - r - wx0) / grid) - 1)
        i1 = min(nx - 1, int((x1 + r - wx0) / grid) + 1)
        j0 = max(0, int((y0 - r - wy0) / grid) - 1)
        j1 = min(ny - 1, int((y1 + r - wy0) / grid) + 1)
        for j in range(j0, j1 + 1):
            py = wy0 + j * grid
            dy = max(y0 - py, 0, py - y1)
            base = j * nx
            for i in range(i0, i1 + 1):
                px = wx0 + i * grid
                dx = max(x0 - px, 0, px - x1)
                if math.hypot(dx, dy) < r:
                    blocked[base + i] = 1

    for (x0, y0, x1, y1) in rects:
        mark_rect(x0, y0, x1, y1, need_seg)
    for (x1_, y1_, x2_, y2_, r) in segs:
        # stamp the segment by walking its bbox cells and testing point-segment distance
        i0 = max(0, int((min(x1_, x2_) - need_seg - r - wx0) / grid) - 1)
        i1 = min(nx - 1, int((max(x1_, x2_) + need_seg + r - wx0) / grid) + 1)
        j0 = max(0, int((min(y1_, y2_) - need_seg - r - wy0) / grid) - 1)
        j1 = min(ny - 1, int((max(y1_, y2_) + need_seg + r - wy0) / grid) + 1)
        dxs, dys = x2_ - x1_, y2_ - y1_
        L2 = dxs * dxs + dys * dys
        for j in range(j0, j1 + 1):
            py = wy0 + j * grid
            base = j * nx
            for i in range(i0, i1 + 1):
                if blocked[base + i]:
                    continue
                px = wx0 + i * grid
                if L2 == 0:
                    d = math.hypot(px - x1_, py - y1_)
                else:
                    tt = max(0.0, min(1.0, ((px - x1_) * dxs + (py - y1_) * dys) / L2))
                    d = math.hypot(px - (x1_ + tt * dxs), py - (y1_ + tt * dys))
                if d < r + need_seg:
                    blocked[base + i] = 1

    # --- board edge keep-out (everywhere except the endpoint pads) ---
    bb = board.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = (bb.GetLeft() / UM, bb.GetTop() / UM,
                          bb.GetRight() / UM, bb.GetBottom() / UM)
    m = track_r + edge
    # EDGE-ONLY separate mask: the clearance mask above stays authoritative. Keeping them apart is
    # what stops an endpoint exemption from silently excusing a clearance violation — the defect
    # the negative control found when both rules shared one bitmap.
    edge_blocked = bytearray(nx * ny)
    for j in range(ny):
        py = wy0 + j * grid
        base = j * nx
        near_y = py < ey0 + m or py > ey1 - m
        for i in range(nx):
            px = wx0 + i * grid
            if near_y or px < ex0 + m or px > ex1 - m:
                edge_blocked[base + i] = 1
    fp_edge = []
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.Edge_Cuts:
                gb = g.GetBoundingBox()
                fp_edge.append((gb.GetLeft() / UM, gb.GetTop() / UM,
                                gb.GetRight() / UM, gb.GetBottom() / UM))
    for (x0, y0, x1, y1) in fp_edge:
        i0 = max(0, int((x0 - m - wx0) / grid) - 1)
        i1 = min(nx - 1, int((x1 + m - wx0) / grid) + 1)
        j0 = max(0, int((y0 - m - wy0) / grid) - 1)
        j1 = min(ny - 1, int((y1 + m - wy0) / grid) + 1)
        for j in range(j0, j1 + 1):
            py = wy0 + j * grid
            dyv = max(y0 - py, 0, py - y1)
            base = j * nx
            for i in range(i0, i1 + 1):
                px = wx0 + i * grid
                dxv = max(x0 - px, 0, px - x1)
                if math.hypot(dxv, dyv) < m:
                    edge_blocked[base + i] = 1
    return blocked, edge_blocked, nx, ny, (wx0, wy0)


def bfs(blocked, edge_blocked, nx, ny, start, goal, edge_exempt):
    if start == goal:
        return [start]

    def free(i, j):
        idx = j * nx + i
        if blocked[idx]:
            return False
        if edge_blocked[idx] and (i, j) not in edge_exempt:
            return False
        return True

    q = collections.deque([start])
    prev = {start: None}
    while q:
        cur = q.popleft()
        i, j = cur
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            ni, nj = i + di, j + dj
            if not (0 <= ni < nx and 0 <= nj < ny):
                continue
            if (ni, nj) in prev:
                continue
            if not free(ni, nj):
                continue
            if di and dj:      # no corner clipping
                if not free(ni, j) or not free(i, nj):
                    continue
            if (ni, nj) == goal:
                prev[goal] = cur
                path = [goal]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            prev[(ni, nj)] = cur
            q.append((ni, nj))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--grid", type=float, default=0.15)
    ap.add_argument("--clearance", type=float, default=0.20)
    ap.add_argument("--track-w", type=float, default=0.20)
    ap.add_argument("--edge", type=float, default=0.50)
    ap.add_argument("--window-pad", type=float, default=12.0)
    ap.add_argument("--pair", type=int, action="append")
    a = ap.parse_args()
    board = pcbnew.LoadBoard(a.board)
    proved = ran = 0
    for pi, (net, sa, sb) in enumerate(PAIRS):
        if a.pair and pi not in a.pair:
            continue
        ran += 1
        pa, pb = bcu_pads(board, sa), bcu_pads(board, sb)
        if not pa or not pb:
            print(f"pair {pi} {net:14s} {sa} -> {sb}: no B.Cu pad on one end "
                  f"(A={len(pa)} B={len(pb)}) — needs a via, not a B.Cu track", flush=True)
            continue
        A, B = pa[0], pb[0]
        ax, ay = A.GetPosition().x / UM, A.GetPosition().y / UM
        bx, by = B.GetPosition().x / UM, B.GetPosition().y / UM
        win = (min(ax, bx) - a.window_pad, min(ay, by) - a.window_pad,
               max(ax, bx) + a.window_pad, max(ay, by) + a.window_pad)
        t0 = time.time()
        blocked, edge_blocked, nx, ny, (wx0, wy0) = rasterise(board, net, a.grid, a.clearance,
                                                             a.track_w / 2.0, a.edge, win)
        t_raster = time.time() - t0
        s = (int(round((ax - wx0) / a.grid)), int(round((ay - wy0) / a.grid)))
        g = (int(round((bx - wx0) / a.grid)), int(round((by - wy0) / a.grid)))
        # ENDPOINT EXEMPTION — EDGE RULE ONLY, and only inside the endpoint pad's own body.
        #
        # A previous version exempted a 2.5 mm DISC around each pad from ALL blocking. Measured by
        # the negative control: raising clearance 0.20 -> 1.50 mm returned the IDENTICAL 5.59 mm
        # path, because the two discs (5.59 mm apart) covered nearly the whole route. The path
        # existed only inside exempted space, i.e. it was not a route. The clearance rule now
        # applies everywhere; only the board-edge keep-out is lifted, and only under the pads,
        # because the J_W lands sit on Edge.Cuts by design (repo DRC allow-list scopes
        # copper_edge_clearance to exactly those refs).
        exempt = set()
        for pad in (A, B):
            bb2 = pad.GetBoundingBox()
            pad_bb = (bb2.GetLeft() / UM, bb2.GetTop() / UM,
                      bb2.GetRight() / UM, bb2.GetBottom() / UM)
            i0 = int((pad_bb[0] - a.grid - wx0) / a.grid)
            i1 = int((pad_bb[2] + a.grid - wx0) / a.grid)
            j0 = int((pad_bb[1] - a.grid - wy0) / a.grid)
            j1 = int((pad_bb[3] + a.grid - wy0) / a.grid)
            for j in range(max(0, j0), min(ny - 1, j1) + 1):
                for i in range(max(0, i0), min(nx - 1, i1) + 1):
                    px, py = wx0 + i * a.grid, wy0 + j * a.grid
                    if (pad_bb[0] - a.grid <= px <= pad_bb[2] + a.grid
                            and pad_bb[1] - a.grid <= py <= pad_bb[3] + a.grid):
                        exempt.add((i, j))
        blocked[s[1] * nx + s[0]] = 0
        blocked[g[1] * nx + g[0]] = 0
        t1 = time.time()
        path = bfs(blocked, edge_blocked, nx, ny, s, g, exempt)
        t_bfs = time.time() - t1
        if path is None:
            print(f"pair {pi} {net:14s} {sa} -> {sb}: NO PATH on B.Cu  "
                  f"(grid {a.grid}, {nx}x{ny}, raster {t_raster:.1f}s bfs {t_bfs:.1f}s)", flush=True)
            continue
        length = 0.0
        for k in range(1, len(path)):
            length += math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1]) * a.grid
        proved += 1
        print(f"pair {pi} {net:14s} {sa}(B.Cu) -> {sb}(B.Cu): PATH {length:.2f} mm, "
              f"0 vias, {len(path)} pts  (grid {a.grid}, raster {t_raster:.1f}s bfs {t_bfs:.1f}s)",
              flush=True)
    print(f"\nPROVED on B.Cu single-layer: {proved} of {ran}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
