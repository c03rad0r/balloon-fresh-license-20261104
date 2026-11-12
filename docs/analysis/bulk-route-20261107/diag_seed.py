#!/usr/bin/env python3
"""diag_seed.py -- is the A* start cell blocked?

route_batch.py seeds A* with ONE cell: the pad's centre. If that cell is blocked the search
returns "start or goal cell blocked" immediately. But a pad has many free cells around its
copper, and a route may legally begin from any of them.

This checks, for the two SPI1 nets that failed, whether the single centre cell is blocked and
how many nearby free cells exist. If many exist and the centre is blocked, the router is failing
on its seeding, not on the board.
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

W = R.World(os.path.join(HERE, "latest.kicad_pcb"))
PITCH = 0.1

for net, ref, num in (("/SPI1_MISO", "U3", "3"), ("/SPI1_MISO", "U_C", "3"),
                      ("/SPI1_MOSI", "U3", "4"), ("/SPI1_MOSI", "U_C", "4")):
    p = [q for q in W.pads if q["ref"] == ref and q["num"] == num and q["net"] == net][0]
    own = {(ref, num)}
    grid, nx, ny = R.build_raster(W, PITCH, net, [p["rect"]], own)
    ox, oy = W.origin
    cx = (p["rect"][0] + p["rect"][2]) / 2
    cy = (p["rect"][1] + p["rect"][3]) / 2
    ci = int(round((cx - ox) / PITCH))
    cj = int(round((cy - oy) / PITCH))

    centre_ok = []
    free_near = 0
    for li, lay in ((0, R.F), (1, R.B)):
        if lay not in (p["layers"] or [R.F, R.B]):
            continue
        blk = bool(grid[li, cj, ci])
        centre_ok.append((W.b.GetLayerName(lay), "BLOCKED" if blk else "free"))
        for di in range(-8, 9):
            for dj in range(-8, 9):
                i, j = ci + di, cj + dj
                if 0 <= i < nx and 0 <= j < ny and not grid[li, j, i]:
                    px, py = ox + i * PITCH, oy + j * PITCH
                    # must sit on the pad's own copper footprint to be a valid start
                    if (p["rect"][0] - 0.05 <= px <= p["rect"][2] + 0.05
                            and p["rect"][1] - 0.05 <= py <= p["rect"][3] + 0.05):
                        free_near += 1
    print(f"{net} {ref}.{num} centre cell ({ci},{cj}): {centre_ok}   "
          f"free cells on/near pad: {free_near}")
