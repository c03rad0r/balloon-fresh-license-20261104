#!/usr/bin/env python3
"""gaps_generous.py -- re-run the 4 unresolved gaps on a GENEROUS raster.

The strict raster grows pads by CLEAR + half track width and grows tracks by CLEAR + half width,
which can enclose a pad that a real router could escape. If a flood escapes on the generous raster
(mark by CLEAR only), then the exit exists and the strict result was an artefact of the screen --
not evidence of a blocked net.

This changes a SCREEN, never the board or the design rules.
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
GAPS = [("/SPI2_SCK", "U1.4", "U2.12"),
        ("/F33_VSENSE", "U1.21", "R_MON1.2"),
        ("/VSCAP", "R_BAL1.1", "D1.1"),
        ("/EN", "U1.3", "J_PROG.3")]


def build_generous(net):
    ox, oy = W.origin
    nx = int(np.ceil(W.size[0] / P)) + 1
    ny = int(np.ceil(W.size[1] / P)) + 1
    grid = np.zeros((2, ny, nx), dtype=bool)

    def mark(lay, x0, y0, x1, y1, g):
        li = 0 if lay == R.F else 1
        i0 = max(0, int((x0 - g - ox) // P))
        i1 = min(nx - 1, int(np.ceil((x1 + g - ox) / P)))
        j0 = max(0, int((y0 - g - oy) // P))
        j1 = min(ny - 1, int(np.ceil((y1 + g - oy) / P)))
        if i0 <= i1 and j0 <= j1:
            grid[li, j0:j1 + 1, i0:i1 + 1] = True

    for p in W.pads:
        if p["npth"] or p["net"] == net:
            continue
        x0, y0, x1, y1 = p["rect"]
        for lay in p["layers"]:
            mark(lay, x0, y0, x1, y1, R.CLEAR)
        if p["pth"]:
            for lay in (R.F, R.B):
                mark(lay, x0, y0, x1, y1, R.CLEAR)
    for t in W.tracks:
        if t["net"] == net:
            continue
        x0 = min(t["a"][0], t["b"][0])
        x1 = max(t["a"][0], t["b"][0])
        y0 = min(t["a"][1], t["b"][1])
        y1 = max(t["a"][1], t["b"][1])
        for lay in t["layers"]:
            mark(lay, x0, y0, x1, y1, R.CLEAR + t["w"] / 2)
    return grid, nx, ny


for net, ra, rb in GAPS:
    pa = [q for q in W.pads if f"{q['ref']}.{q['num']}" == ra and q["net"] == net]
    pb = [q for q in W.pads if f"{q['ref']}.{q['num']}" == rb and q["net"] == net]
    if not pa or not pb:
        print(f"{net} {ra}->{rb}: pad missing")
        continue
    pa, pb = pa[0], pb[0]
    sh = [l for l in pa["layers"] if l in pb["layers"]]
    if not sh:
        print(f"{net} {ra}->{rb}: no shared layer")
        continue
    lay = sh[0]
    li = 0 if lay == R.F else 1
    grid, nx, ny = build_generous(net)
    ox, oy = W.origin

    def cells(pad):
        x0, y0, x1, y1 = pad["rect"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        out = []
        for di in range(-20, 21):
            for dj in range(-20, 21):
                px, py = cx + di * P, cy + dj * P
                if not (x0 - 0.02 <= px <= x1 + 0.02 and y0 - 0.02 <= py <= y1 + 0.02):
                    continue
                i = int(round((px - ox) / P))
                j = int(round((py - oy) / P))
                if 0 <= i < nx and 0 <= j < ny and not grid[li, j, i]:
                    out.append((i, j))
        return out

    s, g = cells(pa), set(cells(pb))
    seen = np.zeros((ny, nx), dtype=bool)
    dq = deque()
    for i, j in s:
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
    print(f"{net:14s} {ra:9s}->{rb:9s} generous: start={len(s):4d} goal={len(g):4d} "
          f"flood={int(seen.sum()):7d} REACHABLE={any(seen[j, i] for i, j in g)}")
