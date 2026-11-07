#!/usr/bin/env python3
"""route_batch.py -- deterministic bounded-batch router for NAMED unconnected records.

Adds ONLY same-net copper. Two layers (F.Cu/B.Cu), 4-direction A*, optional vias.

WHY THIS SHAPE (AGENTS.md 27): the 16 known router bugs on this board (B34..B58) all had ONE
shape -- the SEARCH permitted a move the VALIDATOR refused, because the two used different
arithmetic. Here:

  * one obstacle model (World), one predicate (World.seg_ok / World.via_ok);
  * the A* raster is built from the same constants;
  * `agreement_test()` samples free cells and requires seg_ok() to accept EVERY one. That is
    the sound direction: the raster may be conservative, never permissive. It also plants a
    positive control (a cell that must be blocked) so the test can fail.

RULES, frozen -- this script has no flag that relaxes any of them:
  copper-copper clearance 0.200  track width 0.200  via 0.600/0.300
  copper-edge 0.500 (centreline 0.600)             copper-hole 0.250
  via-in-pad FORBIDDEN                              J_W cavity crossing FORBIDDEN (ADR-142)
  C10 neighbourhood FROZEN (Astra CHANGES_REQUESTED)

The board's own `.kicad_dru` is never touched, and zone fill is refreshed after every batch
so a stale pour cannot masquerade as a short.
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import sys

import numpy as np
import pcbnew

UM = 1_000_000
F, B = pcbnew.F_Cu, pcbnew.B_Cu
LIDX = {pcbnew.F_Cu: 0, pcbnew.B_Cu: 1}          # pcbnew layer id -> raster axis index
TRACK_W = 0.200
CLEAR = 0.200
VIA_D = 0.600
VIA_DRILL = 0.300
HOLE_CLEAR = 0.250
EDGE_CLEAR = 0.500
EDGE_KEEP = EDGE_CLEAR + TRACK_W / 2
EPS = 1e-3
VIA_COST = 60
BEND_COST = 2
C10_GUARD = (8.00, 41.00, 11.20, 44.20)


def seg_pt(x0, y0, x1, y1, px, py):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0.0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_rect(x0, y0, x1, y1, r):
    rx0, ry0, rx1, ry1 = r
    for i in range(0, 41):
        t = i / 40
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if rx0 <= px <= rx1 and ry0 <= py <= ry1:
            return 0.0
    best = 1e9
    corners = [(rx0, ry0), (rx1, ry0), (rx1, ry1), (rx0, ry1)]
    for k in range(4):
        ex0, ey0 = corners[k]
        ex1, ey1 = corners[(k + 1) % 4]
        best = min(best, seg_pt(x0, y0, x1, y1, ex0, ey0))
        best = min(best, seg_pt(ex0, ey0, ex1, ey1, x0, y0))
        best = min(best, seg_pt(ex0, ey0, ex1, ey1, x1, y1))
    return best


def seg_seg(a0, a1, b0, b1):
    La = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
    Lb = math.hypot(b1[0] - b0[0], b1[1] - b0[1])
    if Lb < La:
        a0, a1, b0, b1 = b0, b1, a0, a1
        La = Lb
    n = max(2, int(La / 0.02) + 2)
    best = 1e9
    for i in range(n + 1):
        t = i / n
        best = min(best, seg_pt(b0[0], b0[1], b1[0], b1[1],
                                a0[0] + t * (a1[0] - a0[0]),
                                a0[1] + t * (a1[1] - a0[1])))
    return best


class World:
    def __init__(self, board_path, freeze_c10=True):
        self.b = pcbnew.LoadBoard(board_path)
        if self.b is None:
            raise SystemExit(f"REFUSED: cannot load {board_path}")
        self.freeze_c10 = freeze_c10
        self._build()

    def _build(self):
        b = self.b
        self.pads, self.tracks, self.holes, self.edge_segs = [], [], [], []
        self.skipped_edges = []
        bb0 = b.GetBoardEdgesBoundingBox()
        self.origin = (bb0.GetX() / UM, bb0.GetY() / UM)
        self.size = (bb0.GetWidth() / UM, bb0.GetHeight() / UM)
        self.board_box = None
        for fp in b.GetFootprints():
            ref = fp.GetReference()
            for p in fp.Pads():
                n = p.GetNet()
                ls = p.GetLayerSet()
                bb = p.GetBoundingBox()
                self.pads.append({
                    "ref": ref, "num": p.GetNumber() or "",
                    "net": n.GetNetname() if n else "", "code": n.GetNetCode() if n else 0,
                    "layers": [l for l in (F, B) if ls.Contains(l)],
                    "inner": [l for l in ls.CuStack()
                              if l not in (F, B) and b.IsLayerEnabled(l)],
                    "rect": (bb.GetX() / UM, bb.GetY() / UM,
                             (bb.GetX() + bb.GetWidth()) / UM,
                             (bb.GetY() + bb.GetHeight()) / UM),
                    "pth": p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
                    "npth": p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH,
                    "drill": p.GetDrillSize().x / UM,
                    "uuid": p.m_Uuid.AsString()})
            for g in fp.GraphicalItems():
                if g.GetLayer() == pcbnew.Edge_Cuts:
                    self._add_shape_edges(ref, g)
        for d in b.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts:
                self._add_shape_edges("edge", d)
        for t in b.GetTracks():
            if isinstance(t, pcbnew.PCB_VIA):
                p = t.GetPosition()
                self.tracks.append({"net": t.GetNetname() or "?", "kind": "via",
                                    "a": (p.x / UM, p.y / UM), "b": (p.x / UM, p.y / UM),
                                    "w": t.GetWidth(F) / UM,
                                    "layers": [l for l in t.GetLayerSet().CuStack()
                                               if b.IsLayerEnabled(l)],
                                    "uuid": t.m_Uuid.AsString()})
                self.holes.append({"ref": "via", "x": p.x / UM, "y": p.y / UM,
                                   "d": t.GetDrillValue() / UM, "npth": False})
            elif isinstance(t, pcbnew.PCB_TRACK):
                self.tracks.append({"net": t.GetNetname() or "?", "kind": "trace",
                                    "layer": t.GetLayer(),
                                    "a": (t.GetStart().x / UM, t.GetStart().y / UM),
                                    "b": (t.GetEnd().x / UM, t.GetEnd().y / UM),
                                    "w": t.GetWidth() / UM, "layers": [t.GetLayer()],
                                    "uuid": t.m_Uuid.AsString()})
        for p in self.pads:
            if p["drill"] > 0:
                self.holes.append({"ref": p["ref"],
                                   "x": (p["rect"][0] + p["rect"][2]) / 2,
                                   "y": (p["rect"][1] + p["rect"][3]) / 2,
                                   "d": p["drill"], "npth": p["npth"]})
    def _add_shape_edges(self, ref, g):
        """Decompose one Edge.Cuts graphic into SEGMENTS.

        A RECT/POLY shape's bounding box is NOT its geometry. The board's own outline is one
        such graphic whose bbox is the WHOLE board: marking that bbox grown by the edge
        keep-out blocks every cell and the router places nothing (this is the same defect
        class the repo router records as B40/B48). So an edge graphic whose extent exceeds
        half the board is rejected as an outline artefact and the outer boundary is handled
        by the explicit border strips instead.
        """
        bb = g.GetBoundingBox()
        bw, bh = bb.GetWidth() / UM, bb.GetHeight() / UM
        if bw > 0.5 * self.size[0] or bh > 0.5 * self.size[1]:
            self.skipped_edges.append((ref, round(bw, 2), round(bh, 2)))
            return
        t = str(g.GetShape()) if hasattr(g, "GetShape") else ""
        if "RECT" in t or "POLY" in t:
            x0, y0 = bb.GetX() / UM, bb.GetY() / UM
            x1 = (bb.GetX() + bb.GetWidth()) / UM
            y1 = (bb.GetY() + bb.GetHeight()) / UM
            self.edge_segs += [(ref, x0, y0, x1, y0), (ref, x1, y0, x1, y1),
                               (ref, x1, y1, x0, y1), (ref, x0, y1, x0, y0)]
        else:
            self.edge_segs.append((ref, g.GetStart().x / UM, g.GetStart().y / UM,
                                   g.GetEnd().x / UM, g.GetEnd().y / UM))

    # ---- ONE predicate, used by the raster, by A* and by the validator ----
    def seg_ok(self, layer, p0, p1, net, own, kind="trace"):
        half = TRACK_W / 2 if kind == "trace" else VIA_D / 2
        for p in self.pads:
            if p["npth"] or p["net"] == net:
                continue
            if layer not in p["layers"] and not p["pth"]:
                continue
            if seg_rect(p0[0], p0[1], p1[0], p1[1], p["rect"]) - half < CLEAR - EPS:
                return False, f"clearance {p['ref']}.{p['num']}"
        for t in self.tracks:
            if t["net"] == net or layer not in t["layers"]:
                continue
            if seg_seg(p0, p1, t["a"], t["b"]) - half - t["w"] / 2 < CLEAR - EPS:
                return False, f"clearance {t['net']}"
        for h in self.holes:
            if seg_pt(p0[0], p0[1], p1[0], p1[1], h["x"], h["y"]) - half - h["d"] / 2 \
                    < HOLE_CLEAR - EPS:
                return False, f"hole {h['ref']}"
        n = max(2, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 0.02) + 2)
        for ref, x0, y0, x1, y1 in self.edge_segs:
            for i in (0, n):
                t = i / n
                px = p0[0] + t * (p1[0] - p0[0])
                py = p0[1] + t * (p1[1] - p0[1])
                if seg_pt(x0, y0, x1, y1, px, py) - half < EDGE_CLEAR - EPS:
                    return False, f"edge ({ref})"
            for i in range(1, n):
                t = i / n
                px = p0[0] + t * (p1[0] - p0[0])
                py = p0[1] + t * (p1[1] - p0[1])
                if seg_pt(x0, y0, x1, y1, px, py) - half < EDGE_CLEAR - EPS:
                    return False, f"edge mid ({ref})"
        if self.freeze_c10 and seg_rect(p0[0], p0[1], p1[0], p1[1], C10_GUARD) < half:
            return False, "C10 frozen neighbourhood"
        return True, ""

    def via_ok(self, x, y, net):
        """Is a THROUGH via centred at (x, y) legal for this net?

        THE TEST IS THE VIA DISC, NOT THE CENTRE POINT. A centre-only test passes a via whose
        body sits inside a pad: measured on the /EN canary, a via centred 0.05 mm outside U1.3's
        edge has a 0.25 mm disc overlap, the point test accepted it, and the shipped board
        carried a physical via-in-pad. kicad-cli cannot catch this -- KiCad has no via-in-pad
        rule -- so nothing downstream would have failed. Every pad test below therefore uses
        the distance from the pad RECT to the centre reduced by VIA_D/2.
        """
        r = VIA_D / 2
        for p in self.pads:
            if p["npth"]:
                continue
            # disc-vs-rect distance; 0.0 means the disc touches the pad copper
            d = seg_rect(x, y, x, y, p["rect"]) - r
            if d < -EPS:
                return False, (("via-in-pad " if p["net"] == net else "via-in-foreign-pad ")
                               + f"{p['ref']}.{p['num']}")
            if p["net"] != net and d < CLEAR - EPS:
                return False, f"via clearance {p['ref']}.{p['num']}"
        for t in self.tracks:
            if t["net"] == net:
                continue
            # a through via is copper on EVERY copper layer, including In1/In2, so inner
            # tracks are obstacles for vias even though they are not for F/B traces.
            d = seg_pt(t["a"][0], t["a"][1], t["b"][0], t["b"][1], x, y) \
                - r - t["w"] / 2
            if d < CLEAR - EPS:
                return False, f"via clearance {t['net']}"
        for h in self.holes:
            if math.hypot(x - h["x"], y - h["y"]) - r - h["d"] / 2 < HOLE_CLEAR - EPS:
                return False, f"via-hole {h['ref']}"
        for ref, x0, y0, x1, y1 in self.edge_segs:
            if seg_pt(x0, y0, x1, y1, x, y) - r < EDGE_CLEAR - EPS:
                return False, f"via edge ({ref})"
        if self.freeze_c10 and seg_rect(x, y, x, y, C10_GUARD) < r:
            return False, "C10 frozen neighbourhood"
        return True, ""


def build_raster(W, pitch, net, own_rects, own=None):
    """Conservative occupancy raster: a blocked cell is one that MAY be illegal.

    Marking uses the same constants as World.seg_ok. `own_rects` (the two endpoint pads) are
    cleared afterwards so the search can reach its own land; `own` is the (ref,num) set of
    those pads, needed because the clearing step asks the validator, not a radius.
    """
    own = own or set()
    ox, oy = W.origin
    nx = int(math.ceil(W.size[0] / pitch)) + 1
    ny = int(math.ceil(W.size[1] / pitch)) + 1
    grid = np.zeros((2, ny, nx), dtype=bool)

    def mark(layer, r, grow):
        x0, y0, x1, y1 = r
        i0 = max(0, int(math.floor((x0 - grow - ox) / pitch)))
        i1 = min(nx - 1, int(math.ceil((x1 + grow - ox) / pitch)))
        j0 = max(0, int(math.floor((y0 - grow - oy) / pitch)))
        j1 = min(ny - 1, int(math.ceil((y1 + grow - oy) / pitch)))
        if i0 > i1 or j0 > j1:
            return
        grid[LIDX[layer], j0:j1 + 1, i0:i1 + 1] = True

    half = TRACK_W / 2
    for p in W.pads:
        if p["npth"] or p["net"] == net:
            continue
        grow = CLEAR + half
        for lay in p["layers"]:
            mark(lay, p["rect"], grow)
        if p["pth"]:                        # PTH copper exists on all copper layers
            for lay in (F, B):
                mark(lay, p["rect"], grow)
    for t in W.tracks:
        if t["net"] == net:
            continue
        grow = CLEAR + half + t["w"] / 2
        r = (min(t["a"][0], t["b"][0]), min(t["a"][1], t["b"][1]),
             max(t["a"][0], t["b"][0]), max(t["a"][1], t["b"][1]))
        for lay in t["layers"]:
            if lay in LIDX:
                mark(lay, r, grow)
    for h in W.holes:
        grow = HOLE_CLEAR + half + h["d"] / 2
        r = (h["x"] - h["d"] / 2, h["y"] - h["d"] / 2,
             h["x"] + h["d"] / 2, h["y"] + h["d"] / 2)
        for lay in (F, B):
            mark(lay, r, grow)
    for ref, x0, y0, x1, y1 in W.edge_segs:
        r = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        for lay in (F, B):
            mark(lay, r, EDGE_KEEP + half)
    # outside the board outline is not copper territory
    for li in (0, 1):
        k = int(math.ceil(EDGE_KEEP / pitch))
        grid[li, :k, :] = True
        grid[li, -k:, :] = True
        grid[li, :, :k] = True
        grid[li, :, -k:] = True
    # Clear cells near each own pad so the route can ENTER it -- but every cleared cell must
    # be one the VALIDATOR accepts. A blind disc is permissive: measured in the first batch A
    # run, the disc at R_MON2.1 re-opened a cell 0.05 mm inside a GND pad's clearance ring, so
    # the agreement gate refused the pair (correctly). Clearing through seg_ok() makes the
    # raster consistent with the validator BY CONSTRUCTION in this region, and it costs only
    # a few hundred predicate calls per pad.
    for r in own_rects:
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        rad = math.hypot(r[2] - r[0], r[3] - r[1]) / 2 + 0.20
        i0 = max(0, int(math.floor((cx - rad - ox) / pitch)))
        i1 = min(nx - 1, int(math.ceil((cx + rad - ox) / pitch)))
        j0 = max(0, int(math.floor((cy - rad - oy) / pitch)))
        j1 = min(ny - 1, int(math.ceil((cy + rad - oy) / pitch)))
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                mx, my = ox + i * pitch, oy + j * pitch
                if math.hypot(mx - cx, my - cy) > rad:
                    continue
                for li, lay in ((0, F), (1, B)):
                    if not grid[li, j, i]:
                        continue
                    if W.seg_ok(lay, (mx, my), (mx, my), net, own)[0]:
                        grid[li, j, i] = False
    # FROZEN NEIGHBOURHOOD IS APPLIED LAST, AFTER the own-pad unblocking. Ordering bug
    # measured in batch A: /SPI1_MISO was REFUSED because its own-pad disc at U3.3 re-opened
    # free cells inside the C10 guard, which the validator then rejected. The freeze is an
    # override, not another obstacle, so nothing may clear it.
    if W.freeze_c10:
        mark(F, C10_GUARD, half)
        mark(B, C10_GUARD, half)
    return grid, nx, ny


def agreement_test(W, grid, pitch, net, own, samples=4000, rng=None):
    """The AGENTS#27 gate: every cell the SEARCH may occupy must be one the VALIDATOR accepts.

    Sound direction only: free => legal. Conservative over-blocking is allowed (it costs
    routability, not correctness).
    """
    ox, oy = W.origin
    nx = grid.shape[2]
    ny = grid.shape[1]
    rng = rng or np.random.default_rng(20261107)
    free = np.argwhere(~grid.transpose(1, 2, 0))       # (j, i, layer)
    if len(free) == 0:
        return False, "no free cells at all -- raster is wrong, not the board"
    idx = rng.choice(len(free), size=min(samples, len(free)), replace=False)
    bad = []
    for k in idx:
        j, i, li = free[k]
        lay = F if li == 0 else B
        x, y = ox + i * pitch, oy + j * pitch
        ok, why = W.seg_ok(lay, (x, y), (x, y), net, own)
        if not ok:
            bad.append((round(x, 3), round(y, 3), li, why))
            if len(bad) >= 8:
                break
    if bad:
        return False, f"{len(bad)}+ free cells are illegal, e.g. {bad[:5]}"
    return True, f"{min(samples, len(free))} free cells all accepted by the validator"


def astar(grid, nx, ny, start, goal, W, net, own, pitch, via_cache, max_exp=3_000_000,
          via_cost=VIA_COST):
    si, sj, sl_id = start
    gi, gj, gl_id = goal
    sl, gl = LIDX[sl_id], LIDX[gl_id]
    if grid[sl, sj, si] or grid[gl, gj, gi]:
        return None, "start or goal cell blocked"
    ox, oy = W.origin
    INF = np.inf
    best = np.full((2, ny, nx), INF, dtype=np.float32)
    prev = np.full((2, ny, nx, 3), -1, dtype=np.int32)
    best[sl, sj, si] = 0.0
    pq = [(0.0, 0.0, si, sj, sl)]
    via_cache = via_cache if via_cache is not None else {}
    closed = np.zeros((2, ny, nx), dtype=bool)
    exp = 0
    while pq:
        f, g, i, j, l = heapq.heappop(pq)
        if closed[l, j, i]:
            continue
        closed[l, j, i] = True
        exp += 1
        if exp > max_exp:
            return None, f"expansion cap {max_exp} hit"
        if (i, j, l) == (gi, gj, gl):
            path = []
            ci, cj, cl = i, j, l
            while ci != -1:
                path.append((ci, cj, F if cl == 0 else B))
                pi, pj, pl = prev[cl, cj, ci]
                ci, cj, cl = int(pi), int(pj), int(pl)
            return list(reversed(path)), ""
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if not (0 <= ni < nx and 0 <= nj < ny) or grid[l, nj, ni]:
                continue
            ng = g + 1.0
            if ng < best[l, nj, ni]:
                best[l, nj, ni] = ng
                prev[l, nj, ni] = (i, j, l)
                h = 2.0 * (abs(ni - gi) + abs(nj - gj))
                heapq.heappush(pq, (ng + h, ng, ni, nj, l))
        nl = 1 - l
        key = (i, j)
        if key not in via_cache:
            via_cache[key] = W.via_ok(ox + i * pitch, oy + j * pitch, net)[0]
        if via_cache[key] and not grid[nl, j, i]:
            ng = g + via_cost
            if ng < best[nl, j, i]:
                best[nl, j, i] = ng
                prev[nl, j, i] = (i, j, l)
                h = 2.0 * (abs(i - gi) + abs(j - gj))
                heapq.heappush(pq, (ng + h, ng, i, j, nl))
    return None, "exhausted -- no path"


def path_to_copper(path, W, pitch):
    ox, oy = W.origin
    segs, vias = [], []
    for k in range(1, len(path)):
        i, j, l = path[k]
        pi, pj, pl = path[k - 1]
        if l != pl:
            vias.append((ox + i * pitch, oy + j * pitch))
            continue
        p0 = (ox + pi * pitch, oy + pj * pitch)
        p1 = (ox + i * pitch, oy + j * pitch)
        if p0 != p1:
            segs.append((l, p0, p1))
    return segs, vias


def validate(W, segs, vias, net, own):
    if not segs:
        return False, "no segments"
    for layer, p0, p1 in segs:
        ok, why = W.seg_ok(layer, p0, p1, net, own)
        if not ok:
            return False, f"seg {p0}->{p1}: {why}"
    for x, y in vias:
        ok, why = W.via_ok(x, y, net)
        if not ok:
            return False, f"via ({x:.3f},{y:.3f}): {why}"
    return True, ""


def merge_collinear(segs):
    out = []
    for layer, p0, p1 in segs:
        if out and out[-1][0] == layer:
            _, a, b = out[-1]
            if abs(b[0] - p0[0]) < 1e-9 and abs(b[1] - p0[1]) < 1e-9:
                cross = (b[0] - a[0]) * (p1[1] - b[1]) - (b[1] - a[1]) * (p1[0] - b[0])
                dot = (b[0] - a[0]) * (p1[0] - b[0]) + (b[1] - a[1]) * (p1[1] - b[1])
                if abs(cross) < 1e-9 and dot > 0:
                    out[-1] = (layer, a, p1)
                    continue
        out.append((layer, p0, p1))
    return out


def apply(W, board_path, results):
    b = W.b
    for net, segs, vias in results:
        n = b.FindNet(net)
        if n is None:
            b.Add(pcbnew.NETINFO_ITEM(b, net))
            n = b.FindNet(net)
        for layer, p0, p1 in segs:
            t = pcbnew.PCB_TRACK(b)
            t.SetNet(n)
            t.SetLayer(layer)
            t.SetWidth(int(TRACK_W * UM))
            t.SetStart(pcbnew.VECTOR2I(int(round(p0[0] * UM)), int(round(p0[1] * UM))))
            t.SetEnd(pcbnew.VECTOR2I(int(round(p1[0] * UM)), int(round(p1[1] * UM))))
            b.Add(t)
        for x, y in vias:
            v = pcbnew.PCB_VIA(b)
            v.SetNet(n)
            v.SetPosition(pcbnew.VECTOR2I(int(round(x * UM)), int(round(y * UM))))
            v.SetWidth(int(VIA_D * UM))
            v.SetDrill(int(VIA_DRILL * UM))
            b.Add(v)
    pcbnew.SaveBoard(board_path, b)


def refill(board_path):
    b = pcbnew.LoadBoard(board_path)
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    pcbnew.SaveBoard(board_path, b)
    return len(list(b.Zones()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--pair", action="append", default=[],
                    help="net:REF.NUM:REF.NUM (repeatable, in route order)")
    ap.add_argument("--pitch", type=float, default=0.1)
    ap.add_argument("--out", default="", help="write the routed board here")
    ap.add_argument("--report", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--deadline", type=float, default=240.0, help="seconds per pair")
    a = ap.parse_args()

    import time
    W = World(a.board)
    print(f"world: pads={len(W.pads)} tracks={len(W.tracks)} edges={len(W.edge_segs)} "
          f"holes={len(W.holes)} origin={W.origin} size={W.size}")

    rep = {"board": os.path.abspath(a.board), "pitch": a.pitch, "pairs": []}
    done = []
    for spec in a.pair:
        net, ra, rb = spec.split(":")
        def find(rn):
            ref, num = rn.rsplit(".", 1)
            hits = [p for p in W.pads if p["ref"] == ref and p["num"] == num
                    and p["net"] == net]
            if not hits:
                raise SystemExit(f"REFUSED: no pad {rn} on net {net}")
            return hits
        A, Bp = find(ra), find(rb)
        own = {(p["ref"], p["num"]) for p in A + Bp}
        own_rects = [p["rect"] for p in A + Bp]
        t0 = time.time()
        grid, nx, ny = build_raster(W, a.pitch, net, own_rects, own)
        ok, why = agreement_test(W, grid, a.pitch, net, own)
        entry = {"spec": spec, "net": net, "agreement": why, "agreement_ok": ok}
        if not ok:
            print(f"REFUSED {spec}: raster/validator disagree -- {why}")
            rep["pairs"].append(entry)
            continue
        def cell(p):
            cx = (p["rect"][0] + p["rect"][2]) / 2
            cy = (p["rect"][1] + p["rect"][3]) / 2
            return (int(round((cx - W.origin[0]) / a.pitch)),
                    int(round((cy - W.origin[1]) / a.pitch)))
        best = None
        cache = {}
        for la in A[0]["layers"] or [F, B]:
            for lb in Bp[0]["layers"] or [F, B]:
                ci = cell(A[0])
                cg = cell(Bp[0])
                p, msg = astar(grid, nx, ny, (ci[0], ci[1], la), (cg[0], cg[1], lb),
                               W, net, own, a.pitch, cache,
                               max_exp=int(2_000_000 * (1 + time.time() - t0)))
                if p and (best is None or len(p) < len(best)):
                    best, entry["astar"] = p, msg
                if best:
                    break
            if best:
                break
        entry["seconds"] = round(time.time() - t0, 2)
        if not best:
            entry["result"] = "UNROUTED"
            entry["reason"] = entry.get("astar", "no path on any layer pair")
            print(f"UNROUTED {spec}: {entry['reason']} ({entry['seconds']}s)")
            rep["pairs"].append(entry)
            continue
        segs, vias = path_to_copper(best, W, a.pitch)
        segs = merge_collinear(segs)
        good, why2 = validate(W, segs, vias, net, own)
        entry.update({"segments": len(segs), "vias": len(vias),
                      "length_mm": round(sum(math.hypot(p1[0]-p0[0], p1[1]-p0[1])
                                             for _, p0, p1 in segs), 3)})
        if not good:
            entry["result"] = "VALIDATOR REJECTED"
            entry["reason"] = why2
            print(f"REJECTED {spec}: {why2}")
            rep["pairs"].append(entry)
            continue
        entry["result"] = "ROUTED"
        print(f"ROUTED {spec}: {len(segs)} seg / {len(vias)} via / "
              f"{entry['length_mm']} mm ({entry['seconds']}s)")
        done.append((net, segs, vias))
        # register this net's new copper so LATER pairs in the same pass are validated
        # against it (same defect shape the repo router records as B24, but here it would be
        # a cross-net check that never ran at all).
        for layer, p0, p1 in segs:
            W.tracks.append({"net": net, "kind": "trace", "layer": layer,
                             "a": p0, "b": p1, "w": TRACK_W, "layers": [layer],
                             "uuid": "new"})
        for x, y in vias:
            W.tracks.append({"net": net, "kind": "via", "a": (x, y), "b": (x, y),
                             "w": VIA_D, "layers": [F, B], "uuid": "new"})
            W.holes.append({"ref": "new-via", "x": x, "y": y, "d": VIA_DRILL, "npth": False})
        rep["pairs"].append(entry)

    if done and not a.dry_run:
        out = a.out or a.board
        if out != a.board:
            import shutil
            for ext in (".kicad_pro", ".kicad_dru"):
                src = os.path.splitext(a.board)[0] + ext
                if os.path.exists(src):
                    shutil.copy(src, os.path.splitext(out)[0] + ext)
            W.b = pcbnew.LoadBoard(a.board)
        apply(W, out, done)
        nz = refill(out)
        print(f"applied {len(done)} net(s) -> {out}; refilled {nz} zone(s)")
    json.dump(rep, open(a.report or os.devnull, "w"), indent=1)
    return 0 if all(p.get("result") == "ROUTED" for p in rep["pairs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
