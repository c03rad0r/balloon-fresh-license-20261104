#!/usr/bin/env python3
"""reachability.py -- can each remaining unconnected pair be joined AT ALL?

WHY THIS EXISTS. Three times now I measured a single pad's free corridor and generalised to
the whole net: /EN "blocked", /HUB_PV_N "0.60 mm pocket" (then routed anyway from another
island), /SPI1_MISO "congestion". Two of those conclusions were wrong. The pad-corridor
measurement answers "can a via sit here", which is a different question from "is there a path".

This answers the path question directly and cheaply. It builds the SAME raster the router uses
(same World, same build_raster, same rules -- no second obstacle model), then flood-fills the
free cells of each layer and reports which free-space component each endpoint's escape cells
belong to. A pair is routable only if some (layer at A, layer at B) combination lands in one
component, where a layer change is allowed only where via_ok passes.

No A*. No 300 s wait to learn "no". Exit code 1 if any pair is unreachable.

Usage:
    reachability.py BOARD --pair 'NET:REF.NUM:REF.NUM' [--pair ...]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from collections import deque

import numpy as np
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
spec = importlib.util.spec_from_file_location("R", os.path.join(REPO, "tracker", "hardware",
                                                               "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def pad_of(W, ref, num):
    for p in W.pads:
        if p["ref"] == ref and p["num"] == num:
            return p
    return None


def cells_near(W, pad, pitch, layers):
    """Free cells on `layers` sitting on the pad's own copper -- where a route may start."""
    x0, y0, x1, y1 = pad["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    rad = max(x1 - x0, y1 - y0) / 2 + 0.25
    n = int(np.ceil(rad / pitch))
    ox, oy = W.origin
    for li, lay in enumerate((R.F, R.B)):
        if lay not in layers and not pad["pth"]:
            continue
        for di in range(-n, n + 1):
            for dj in range(-n, n + 1):
                x = cx + di * pitch
                y = cy + dj * pitch
                if not (x0 - 0.05 <= x <= x1 + 0.05 and y0 - 0.05 <= y <= y1 + 0.05):
                    continue
                ok, _ = W.seg_ok(lay, (x, y), (x, y), pad["net"], {(pad["ref"], pad["num"])})
                if ok:
                    out.append((x, y, li))
    return out


def flood(grid, nx, ny, pitch, origin, from_cells, goal_cells, via_ok):
    """One connected-component label set over BOTH layers, with via_ok as the layer gate."""
    ox, oy = origin
    lab = -np.ones((2, ny, nx), dtype=np.int32)
    # PRECOMPUTE the via permission map ONCE. via_ok is O(all pads + all tracks + all holes +
    # all edge segments) per call; calling it inside the flood made a 7-pair run exceed 10
    # minutes (measured, killed). This is the same mistake the original raster made with
    # contains_xy -- pay the expensive test once per cell, not once per visit.
    via = np.zeros((ny, nx), dtype=bool)
    # NO CROP. An earlier version computed the via map only inside the rectangle spanned by the
    # two endpoints, on the reasoning that "the flood cannot leave this rectangle". That was
    # FALSE: the raster is whole-board, so the flood roams freely on a layer and may change
    # layers anywhere -- but the crop silently forbade every layer change outside the box. A net
    # whose only via site lay outside that box was reported UNREACHABLE when it was routable.
    # That is a test window manufacturing a false "blocked", the worst class of error in this
    # workstream. The whole-board map is too slow to precompute (720k O(thousands-of-items)
    # calls), so it is memoised LAZILY: each cell is evaluated only if the flood reaches it.
    via_cache: dict[tuple[int, int], bool] = {}
    comp = 0
    comp = 0
    for (sx, sy, sl) in from_cells:
        i = int(round((sx - ox) / pitch))
        j = int(round((sy - oy) / pitch))
        if not (0 <= i < nx and 0 <= j < ny) or grid[sl, j, i] or lab[sl, j, i] >= 0:
            continue
        comp += 1
        dq = deque()
        dq.append((sl, i, j))
        lab[sl, j, i] = comp
        while dq:
            l, ci, cj = dq.popleft()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < nx and 0 <= nj < ny):
                    continue
                if grid[l, nj, ni] or lab[l, nj, ni] >= 0:
                    continue
                lab[l, nj, ni] = comp
                dq.append((l, ni, nj))
            # layer change: only where a via at this site is legal for this net
            nl = 1 - l
            if not grid[nl, cj, ci] and lab[nl, cj, ci] < 0:
                key = (ci, cj)
                if key not in via_cache:
                    via_cache[key] = bool(via_ok(ox + ci * pitch, oy + cj * pitch))
                if not via_cache[key]:
                    continue
                lab[nl, cj, ci] = comp
                dq.append((nl, ci, cj))
    return lab, comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--pair", action="append", required=True)
    ap.add_argument("--pitch", type=float, default=0.1)
    a = ap.parse_args()

    W = R.World(a.board)
    print(f"board {os.path.basename(a.board)}  pads={len(W.pads)} tracks={len(W.tracks)}")
    unreachable = []
    for spec_s in a.pair:
        net, ra, rb = spec_s.split(":")
        pa, pb = pad_of(W, *ra.rsplit(".", 1)), pad_of(W, *rb.rsplit(".", 1))
        if pa is None or pb is None:
            print(f"{spec_s}: PAD NOT FOUND")
            continue
        grid, nx, ny = R.build_raster(W, a.pitch, net, [pa["rect"], pb["rect"]],
                                      {(pa["ref"], pa["num"]), (pb["ref"], pb["num"])})
        vok = lambda x, y: W.via_ok(x, y, net)[0]   # noqa: E731
        ca = cells_near(W, pa, a.pitch, pa["layers"] or [R.F, R.B])
        cb = cells_near(W, pb, a.pitch, pb["layers"] or [R.F, R.B])
        if not ca or not cb:
            print(f"{spec_s}: NO FREE CELL AT {'A' if not ca else 'B'} "
                  f"-- pad fully sealed by foreign copper")
            unreachable.append(spec_s)
            continue
        lab, ncomp = flood(grid, nx, ny, a.pitch, W.origin, ca, cb, vok)
        ox, oy = W.origin
        comps_b = set()
        for (x, y, l) in cb:
            i = int(round((x - ox) / a.pitch))
            j = int(round((y - oy) / a.pitch))
            if 0 <= i < nx and 0 <= j < ny and lab[l, j, i] >= 0:
                comps_b.add(int(lab[l, j, i]))
        comps_a = set()
        for (x, y, l) in ca:
            i = int(round((x - ox) / a.pitch))
            j = int(round((y - oy) / a.pitch))
            if 0 <= i < nx and 0 <= j < ny and lab[l, j, i] >= 0:
                comps_a.add(int(lab[l, j, i]))
        ok = bool(comps_a & comps_b)
        print(f"{spec_s}: {'REACHABLE' if ok else 'UNREACHABLE'}  "
              f"cellsA={len(ca)} cellsB={len(cb)} "
              f"compA={sorted(comps_a)[:3]} compB={sorted(comps_b)[:3]}")
        if not ok:
            unreachable.append(spec_s)
    print(f"\n{len(unreachable)}/{len(a.pair)} pairs UNREACHABLE at {a.pitch} mm pitch")
    return 1 if unreachable else 0


if __name__ == "__main__":
    sys.exit(main())
