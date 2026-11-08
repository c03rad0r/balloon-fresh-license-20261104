#!/usr/bin/env python3
"""gaps_fast.py -- classify the 5 real copper gaps with the CHEAP raster flood.

The full reachability.py costs ~20 min per pair because it evaluates via_ok lazily over the whole
board. For a pair whose two ends share a copper layer, no via is needed and the raster flood alone
answers the question in seconds. This runs only that case, and says "needs via" for the rest rather
than pretending it answered.

For each unreachable pair it also reports the nearest approach in mm, which is the number that
distinguishes "one track is in the way" from "there is no corridor at all".
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

P = 0.1
W = R.World(os.path.join(HERE, "latest.kicad_pcb"))

# The 5 records that are real copper (the other 10 are assembly lands and GND zone anchors).
GAPS = [
    ("/SPI2_SCK",   "U1.4",   "U2.12"),
    ("/F33_VSENSE", "U1.21",  "R_MON1.2"),
    ("/VSCAP",      "C_CAP1.1", "R_BAL1.1"),
    ("/VSCAP",      "R_BAL1.1", "D1.1"),
    ("/EN",         "U1.3",   "J_PROG.3"),
]

grids = {}
for net, ra, rb in GAPS:
    pa = [q for q in W.pads if f"{q['ref']}.{q['num']}" == ra and q["net"] == net]
    pb = [q for q in W.pads if f"{q['ref']}.{q['num']}" == rb and q["net"] == net]
    print(f"\n{net}  {ra} -> {rb}")
    if not pa or not pb:
        print(f"  SKIP: pad not found (pa={bool(pa)} pb={bool(pb)})")
        continue
    pa, pb = pa[0], pb[0]
    lay_a = pa["layers"] or [R.F, R.B]
    lay_b = pb["layers"] or [R.F, R.B]
    # A PTH pad has copper on every layer, so it shares any layer with the other end.
    shared = [l for l in lay_a if l in lay_b or pb.get("pth")]
    if not shared:
        shared = [l for l in lay_b if pa.get("pth")]
    print(f"  A layers={[W.b.GetLayerName(l) for l in lay_a]}"
          f"  B layers={[W.b.GetLayerName(l) for l in lay_b]}"
          f"  pthA={pa.get('pth')} pthB={pb.get('pth')}")
    if not shared:
        print("  NEEDS VIA: no shared copper layer -- this cheap check cannot answer")
        continue
    lay = shared[0]
    li = 0 if lay == R.F else 1
    if net not in grids:
        own = {(q["ref"], q["num"]) for q in W.pads if q["net"] == net}
        rects = [q["rect"] for q in W.pads if q["net"] == net]
        grids[net] = (*R.build_raster(W, P, net, rects, own), own)
    grid, nx, ny, own = grids[net]
    ox, oy = W.origin

    def cells(pad):
        x0, y0, x1, y1 = pad["rect"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        out = []
        n = int(max(x1 - x0, y1 - y0) / P / 2) + 18
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

    start, goal = cells(pa), cells(pb)
    gset = set(goal)
    seen = np.zeros((ny, nx), dtype=bool)
    dq = deque()
    for c in start:
        i, j = c
        if not seen[j, i]:
            seen[j, i] = True
            dq.append(c)
    while dq:
        i, j = dq.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < ny and not grid[li, nj, ni] and not seen[nj, ni]:
                seen[nj, ni] = True
                dq.append((ni, nj))
    got = any(seen[j, i] for (i, j) in gset)
    print(f"  layer {W.b.GetLayerName(lay)}: start={len(start)} goal={len(goal)} "
          f"flood={int(seen.sum())}  REACHABLE={got}")
    if not got:
        if not start:
            print("  (no free start cells on the pad at all)")
            continue
        if not goal:
            print("  (no free goal cells on the pad at all)")
            continue
        ys, xs = np.where(seen)
        seed = np.stack([xs, ys], axis=1)
        g = np.array(sorted(gset))
        d = ((seed[:, None, :] - g[None, :, :]) ** 2).sum(-1)
        k = int(np.argmin(d))
        si, sj = seed[k // len(g)]
        ti, tj = g[k % len(g)]
        print(f"  nearest approach {(abs(ti-si)+abs(tj-sj))*P:.2f} mm  "
              f"({ox+si*P:.2f},{oy+sj*P:.2f}) -> ({ox+ti*P:.2f},{oy+tj*P:.2f})")
