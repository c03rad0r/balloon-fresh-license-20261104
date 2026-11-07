#!/usr/bin/env python3
"""trace_path.py -- reconstruct the actual free-space path, cell by cell.

Guessing at corridors from clearances was not converging. The pre-batch board HAS a B.Cu path
from U3.3 to U_C.3 (flood says so); this reconstructs it, so the corridor that /SPI1_SCK must
stay out of is read off the board instead of inferred.

Prints the path as a coarse polyline: direction changes only, so it reads as the route.
"""
import importlib.util
import os
import sys
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

P = 0.1
board = sys.argv[1]
net = sys.argv[2]
ra, rb = sys.argv[3], sys.argv[4]
layer = R.B if len(sys.argv) < 6 or sys.argv[5] == "B" else R.F

W = R.World(board)
own = {(q["ref"], q["num"]) for q in W.pads if q["net"] == net}
rects = [q["rect"] for q in W.pads if q["net"] == net]
grid, nx, ny = R.build_raster(W, P, net, rects, own)
ox, oy = W.origin
li = 0 if layer == R.F else 1

pa = [q for q in W.pads if f"{q['ref']}.{q['num']}" == ra and q["net"] == net][0]
pb = [q for q in W.pads if f"{q['ref']}.{q['num']}" == rb and q["net"] == net][0]


def cells(pad):
    x0, y0, x1, y1 = pad["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    n = int(max(x1 - x0, y1 - y0) / P / 2) + 15
    for di in range(-n, n + 1):
        for dj in range(-n, n + 1):
            px, py = cx + di * P, cy + dj * P
            if not (x0 - 0.03 <= px <= x1 + 0.03 and y0 - 0.03 <= py <= y1 + 0.03):
                continue
            i = int(round((px - ox) / P))
            j = int(round((py - oy) / P))
            if 0 <= i < nx and 0 <= j < ny and not grid[li, j, i]:
                out.append((i, j))
    return out


start, goal = cells(pa), set(cells(pb))
prev = {}
seen = np.zeros((ny, nx), dtype=bool)
dq = deque()
for c in start:
    i, j = c
    if not seen[j, i]:
        seen[j, i] = True
        dq.append(c)
hit = None
while dq:
    i, j = dq.popleft()
    if (i, j) in goal:
        hit = (i, j)
        break
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ni, nj = i + di, j + dj
        if 0 <= ni < nx and 0 <= nj < ny and not grid[li, nj, ni] and not seen[nj, ni]:
            seen[nj, ni] = True
            prev[(ni, nj)] = (i, j)
            dq.append((ni, nj))

print(f"{net} {ra} -> {rb} on {W.b.GetLayerName(layer)}  board={os.path.basename(board)}")
if not hit:
    print("  NO PATH")
    sys.exit(1)
path = [hit]
while path[-1] in prev:
    path.append(prev[path[-1]])
path.reverse()
print(f"  path cells: {len(path)}  length {(len(path)-1)*P:.2f} mm")
turns = []
for k in range(1, len(path) - 1):
    a, b, c = path[k - 1], path[k], path[k + 1]
    d1 = (b[0] - a[0], b[1] - a[1])
    d2 = (c[0] - b[0], c[1] - b[1])
    if d1 != d2:
        turns.append(path[k])
pts = [path[0]] + turns + [path[-1]]
print("  route: " + " -> ".join(
    f"({ox+i*P:.2f},{oy+j*P:.2f})" for (i, j) in pts))
xs = [ox + i * P for (i, j) in path]
ys = [oy + j * P for (i, j) in path]
print(f"  bounding box: x {min(xs):.2f}..{max(xs):.2f}   y {min(ys):.2f}..{max(ys):.2f}")
