#!/usr/bin/env python3
"""same_layer_wall.py -- is the B.Cu free space actually split in two?

/SPI1_MISO U3.3 and U_C.3 are BOTH on B.Cu. No layer change is needed, so the whole "via does
not fit" story is wrong for this net. The question is simpler: on B.Cu, is the free space a
single connected region or two?

Flood the B.Cu raster (no via transitions at all) from the U3.3 pad and report whether the
U_C.3 pad is in the same region. If not, measure the gap: how far apart are the two regions?
That gap is the exact obstacle.
"""
import importlib.util
import os
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

W = R.World(os.path.join(HERE, "latest.kicad_pcb"))
PITCH = 0.1

for net, ra, rb in (("/SPI1_MISO", "U3.3", "U_C.3"), ("/SPI1_MOSI", "U3.4", "U_C.4")):
    pa = [q for q in W.pads if f"{q['ref']}.{q['num']}" == ra and q["net"] == net][0]
    pb = [q for q in W.pads if f"{q['ref']}.{q['num']}" == rb and q["net"] == net][0]
    own = {(pa["ref"], pa["num"]), (pb["ref"], pb["num"])}
    grid, nx, ny = R.build_raster(W, PITCH, net, [pa["rect"], pb["rect"]], own)
    ox, oy = W.origin
    lay = int(pa["layers"][0])
    li = 0 if lay == R.F else 1

    def cells(pad):
        x0, y0, x1, y1 = pad["rect"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        out = []
        for di in range(-15, 16):
            for dj in range(-15, 16):
                px, py = cx + di * PITCH, cy + dj * PITCH
                if not (x0 - 0.03 <= px <= x1 + 0.03 and y0 - 0.03 <= py <= y1 + 0.03):
                    continue
                i = int(round((px - ox) / PITCH))
                j = int(round((py - oy) / PITCH))
                if 0 <= i < nx and 0 <= j < ny and not grid[li, j, i]:
                    out.append((i, j))
        return out

    start = cells(pa)
    goal = set(cells(pb))
    seen = np.zeros((ny, nx), dtype=bool)
    dq = deque()
    for (i, j) in start:
        if not seen[j, i]:
            seen[j, i] = True
            dq.append((i, j))
    while dq:
        i, j = dq.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < ny and not grid[li, nj, ni] and not seen[nj, ni]:
                seen[nj, ni] = True
                dq.append((ni, nj))

    joined = any(seen[j, i] for (i, j) in goal)
    reached = int(seen.sum())
    total_free = int((~grid[li]).sum())
    name = W.b.GetLayerName(lay)
    print(f"\n{net}  {ra} -> {rb}   layer {name}")
    print(f"  start cells {len(start)}, goal cells {len(goal)}")
    print(f"  flood from {ra}: {reached} cells of {total_free} free on this layer")
    print(f"  GOAL REACHED: {'YES -- same-layer path exists' if joined else 'NO'}")

    if not joined:
        # nearest approach between the flooded region and the goal cells
        best = None
        g = np.array(sorted(goal))
        if len(g):
            ys, xs = np.where(seen)
            seed = np.stack([xs, ys], axis=1)
            # coarse nearest-pair distance in cell units
            d = ((seed[:, None, :] - g[None, :, :]) ** 2).sum(-1)
            k = int(np.argmin(d))
            si, sj = seed[k // len(g)]
            ti, tj = g[k % len(g)]
            best = (abs(ti - si) + abs(tj - sj)) * PITCH
            px1, py1 = ox + si * PITCH, oy + sj * PITCH
            px2, py2 = ox + ti * PITCH, oy + tj * PITCH
            print(f"  nearest approach: {best:.2f} mm  "
                  f"({px1:.2f},{py1:.2f}) -> ({px2:.2f},{py2:.2f})")
            print(f"  the two B.Cu regions are separated; that gap is the obstacle "
                  f"(a layer change cannot bridge it because both pads are already B.Cu)")
