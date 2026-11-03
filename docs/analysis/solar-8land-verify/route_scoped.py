#!/usr/bin/env python3
"""Route SPECIFIC unconnected pads, additively. Never rips up existing copper.

WHY NOT auto_route_v1.py
That script deletes every track, via and zone and re-routes from scratch. On this candidate that
would discard work that is already verified: 6 solar routes proven pair-by-pair, 37 GND stitching
vias, 12 +3V3 taps, the In2 3V3 plane, the /VSCAP pour taps, the thermal fix and the via upsizing.
Re-routing everything to close ~30 opens is not a trade worth making, and ADR-140 requires a route
trial before placement is approved anyway.

WHAT IT DOES
For each still-unconnected pair from the DRC report, run a 2-layer A* on a 0.200 mm grid with
0.200 mm clearance and 0.200 mm tracks, allowing vias at 0.600/0.300 (frozen S1). Add the resulting
copper. Refuse to touch anything already connected.

HARD RULES
  - additive only; nothing is deleted or moved
  - via >= 0.60/0.30; never inside an SMD pad; never on Edge.Cuts (including J_W cavities)
  - every stub and segment is clearance-checked against EVERY layer's copper, because a via is a
    through-hole
  - a pair that cannot be routed is REPORTED, not forced
  - kicad-cli DRC is the judge; the run aborts its own result if `shorting_items` appears

SKIPS (by design, with the record that says so)
  - same pad number on F.Cu and B.Cu of one footprint: the two-face wing tab (ADR-120 R1,
    WING-TO-HUB-SOCKET-SPEC sec 2). It joins in ASSEMBLY by solder; a via is not required and the
    repo's earlier note on J_W pads says the same.
  - zone-to-zone items: a pour problem, not a missing track -- handled by island bridging.

Usage:
  route_scoped.py <src> <out> --dru <frozen.kicad_dru> --report DIR [--max-pairs N] [--dry-run]
"""
import argparse
import heapq
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time as _time

import pcbnew

# The ONLY two layers a track is ever routed on. KiCad assigns F.Cu=0, B.Cu=2, In1.Cu=4, In2.Cu=6
# -- NOT 0 and 1. So `1 - layer` yields an INNER layer, which was a live bug: the A* goal state was
# unreachable and every same-layer pair returned "no path" in 0.0 s (see astar docstring).
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)

UM = 1_000_000.0
CLEAR, TRACK_W, VIA_D, VIA_DRILL, EDGE = 0.20, 0.20, 0.60, 0.30, 0.50
GRID = 0.15
ARC_ERR = 5000

PAD_RE = re.compile(r'(?:PTH )?[Pp]ad (\d+) \[([^\]]+)\] of ([A-Za-z0-9_.]+) on (F\.Cu|B\.Cu)')


def run_drc(pcb, dru, out_json):
    stem = os.path.splitext(pcb)[0]
    shutil.copyfile(dru, stem + ".kicad_dru")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out_json, pcb], capture_output=True, text=True)
    if not os.path.exists(out_json):
        return None, None, None
    d = json.load(open(out_json))
    from collections import Counter
    return (Counter(v["type"] for v in d.get("violations", [])),
            len(d.get("unconnected_items", [])), d)


def seg_pt(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


class World:
    """Copper + hole obstacles, and the pads we are allowed to touch."""

    def __init__(self, board):
        self.b = board
        self.segs, self.vias, self.padrects, self.edges, self.pads = [], [], [], [], {}
        for t in board.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                self.vias.append((p.x / UM, p.y / UM, t.GetWidth(pcbnew.F_Cu) / UM / 2.0,
                                  t.GetDrillValue() / UM / 2.0, t.GetNetCode()))
            else:
                self.segs.append((t.GetStart().x / UM, t.GetStart().y / UM, t.GetEnd().x / UM,
                                  t.GetEnd().y / UM, t.GetWidth() / UM / 2.0, t.GetLayer(),
                                  t.GetNetCode()))
        for fp in board.GetFootprints():
            for p in fp.Pads():
                bb = p.GetBoundingBox()
                dr = p.GetDrillSize()
                self.padrects.append((bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM,
                                      bb.GetBottom() / UM, max(dr.x, dr.y) / UM / 2.0,
                                      p.GetNetCode()))
                self.pads[(fp.GetReference(), p.GetNumber())] = p
        for d_ in board.GetDrawings():
            if d_.GetLayer() == pcbnew.Edge_Cuts:
                self._edge(d_)
        for fp in board.GetFootprints():
            for gi in fp.GraphicalItems():
                if gi.GetLayer() == pcbnew.Edge_Cuts:
                    self._edge(gi)

    def _edge(self, shape):
        try:
            ps = pcbnew.SHAPE_POLY_SET()
            shape.TransformShapeToPolygon(ps, pcbnew.Edge_Cuts, 0, ARC_ERR, pcbnew.ERROR_INSIDE)
            self.edges.append(ps)
        except Exception:
            pass

    def _edge_mask(self, step=0.25):
        """Precompute edge proximity on a coarse grid: on_edge() per A* cell was too slow.

        There are 16 J_W cavity slots plus the board outline, and a poly-set Distance() call for
        each, for every candidate cell, made a single pair run past 500 s (measured 2026-11-03).
        The edge geometry is static for a run, so it is rasterised ONCE at 0.25 mm -- four times
        coarser than the 0.10 mm routing grid -- and cells within `step` of a hit are marked.
        Coarser is safe here: the mask is dilated by one cell, so it over-reports rather than
        under-reports, and over-reporting only refuses sites.
        """
        x0, y0, x1, y1 = 0.0, 0.0, 72.1, 80.1
        nx = int((x1 - x0) / step) + 2
        ny = int((y1 - y0) / step) + 2
        lim_mm = EDGE + TRACK_W / 2.0 + step
        lim = int(lim_mm * UM)
        mask = bytearray(nx * ny)
        for es in self.edges:
            try:
                bb = es.BBox()
                ex0 = bb.GetLeft() / UM - lim_mm
                ex1 = bb.GetRight() / UM + lim_mm
                ey0 = bb.GetTop() / UM - lim_mm
                ey1 = bb.GetBottom() / UM + lim_mm
            except Exception:
                ex0, ey0, ex1, ey1 = x0, y0, x1, y1
            # only rasterise cells near THIS shape, not the whole board
            i0 = max(0, int((ex0 - x0) / step))
            i1 = min(nx - 1, int((ex1 - x0) / step))
            j0 = max(0, int((ey0 - y0) / step))
            j1 = min(ny - 1, int((ey1 - y0) / step))
            for j in range(j0, j1 + 1):
                y = y0 + j * step
                for i in range(i0, i1 + 1):
                    x = x0 + i * step
                    try:
                        if es.Distance(pcbnew.VECTOR2I(int(x * UM), int(y * UM))) < lim:
                            mask[j * nx + i] = 1
                    except Exception:
                        pass
        self._emask = (mask, nx, ny, step, x0, y0)

    def on_edge(self, x, y):
        if not hasattr(self, "_emask"):
            self._edge_mask()
        mask, nx, ny, step, x0, y0 = self._emask
        i = int((x - x0) / step)
        j = int((y - y0) / step)
        if 0 <= i < nx and 0 <= j < ny and mask[j * nx + i]:
            return True
        return False

    def in_any_pad(self, x, y):
        for (l, t, r, b, dr, code) in self.padrects:
            if l <= x <= r and t <= y <= b:
                return code
        return None

    def blocked(self, x, y, layer, netcode, allow_pad=None):
        """Is a track centre at (x,y) on `layer` illegal for `netcode`?"""
        if not (0.5 < x < 71.6 and 0.5 < y < 79.6):
            return True
        # EDGE.CUTS APPLIES TO TRACKS TOO. Only via placement checked edges, so a track could be
        # routed straight across a J_W cavity slot: measured 2026-11-03, the 8-way run produced 6
        # copper_edge_clearance errors from a D_BP2.2 -> J_W2.4 segment crossing J_W4's slot.
        # ADR-142 keeps the pad exemption pad-only; a track must never cross a socket cavity.
        if self.on_edge(x, y):
            return True
        r = TRACK_W / 2.0 + CLEAR
        for (x1, y1, x2, y2, rw, lay, code) in self.segs:
            if code != netcode and seg_pt(x, y, x1, y1, x2, y2) < r + rw:
                return True
        for (px, py, pr, _d, code) in self.vias:
            if code != netcode and math.hypot(x - px, y - py) < r + pr:
                return True
        for (l, t, rr, b, dr, code) in self.padrects:
            if code == netcode:
                continue
            d = math.hypot(max(l - x, 0, x - rr), max(t - y, 0, y - b))
            if d < r:
                return True
        return False

    def via_ok(self, x, y, netcode):
        if not (0.8 < x < 71.3 and 0.8 < y < 79.3):
            return False
        if self.in_any_pad(x, y) is not None:
            return False                       # never via-in-pad
        if self.on_edge(x, y):
            return False
        r = VIA_D / 2.0 + CLEAR
        for (x1, y1, x2, y2, rw, _lay, code) in self.segs:
            if code != netcode and seg_pt(x, y, x1, y1, x2, y2) < r + rw:
                return False
        for (px, py, pr, dr, code) in self.vias:
            if math.hypot(x - px, y - py) < (VIA_DRILL / 2.0 + dr + 0.25):
                return False
        for (l, t, rr, b, dr, code) in self.padrects:
            if math.hypot(max(l - x, 0, x - rr), max(t - y, 0, y - b)) < r and code != netcode:
                return False
            if dr > 0:
                pcx, pcy = (l + rr) / 2.0, (t + b) / 2.0
                if math.hypot(x - pcx, y - pcy) < VIA_DRILL / 2.0 + dr + 0.25:
                    return False
        return True


def astar(w, start, goal, netcode, layer0, per_pair_s=25.0, goal_layer=None):
    """2-layer A* in a bounded window around the pair.

    LAYER IDS ARE 0 (F.Cu) AND 2 (B.Cu), NOT 0 AND 1. Measured 2026-11-03: the goal state was
    computed as `1 - layer0`, which is layer 1 -- an inner layer, present on this board but not a
    layer any track is routed on. The goal was therefore unreachable BY CONSTRUCTION and every pair
    returned "no path" in 0.0 s without expanding a single node. That silent failure accounted for
    the 11 "no path" results in v13/v14, not the geometry. Hence `goal_layer` is now explicit.
    """
    span = math.hypot(goal[0] - start[0], goal[1] - start[1])
    margin = min(18.0, max(6.0, span * 0.25))
    def key(p):
        return (int(round(p[0] / GRID)), int(round(p[1] / GRID)), p[2])
    s, g = key((start[0], start[1], layer0)), key((goal[0], goal[1], goal_layer))
    gx, gy = goal
    x0 = min(start[0], goal[0]) - margin
    x1 = max(start[0], goal[0]) + margin
    y0 = min(start[1], goal[1]) - margin
    y1 = max(start[1], goal[1]) + margin

    def h(ix, iy):
        return math.hypot(ix * GRID - gx, iy * GRID - gy) * 0.5

    openq = [(h(s[0], s[1]), 0.0, s)]
    came, cost = {}, {s: 0.0}
    seen = set()
    # THE START AND GOAL CELLS MUST BE EXEMPT FROM `blocked()`. Both pads' own copper (and any other
    # copper of the SAME net touching them) makes the exact pad centre read as blocked, so the search
    # could not take its first step and returned in 0.0 s. Measured 2026-11-03: C10.1 read
    # `START blocked? True`, which is why that pair failed instantly after the layer bug was fixed.
    EXEMPT = {s, g}
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1),
             (1, 1), (1, -1), (-1, 1), (-1, -1)]
    # SEED FROM THE PAD'S ESCAPE RING, NOT ITS CENTRE. A pad's own copper plus its clearance envelope
    # is wider than one 0.10 mm cell, so every one-cell neighbour of the pad centre is blocked and the
    # search cannot take a first step -- it returned in 0.0 s having expanded nothing. Measured
    # 2026-11-03 on C10.1: all 8 neighbours blocked, pad half-diagonal 0.42 mm vs 0.10 mm stride.
    # So we pre-load every legal cell within R_ESCAPE of each endpoint at cost = its distance.
    # BOUNDED. This seeding was first written as a full (2n+1)^2 box per endpoint, which with 8-way
    # expansion exhausted memory (rc=137) before the first pair finished. Only the RING matters: the
    # cells just outside the pad envelope that the search can actually leave from. So: cells whose
    # distance is within [0.6*R_ESCAPE, R_ESCAPE], which is the annulus, not the disc.
    R_ESCAPE = 1.20
    for (px, py, lay0) in ((start[0], start[1], layer0), (goal[0], goal[1], goal_layer)):
        n = int(math.ceil(R_ESCAPE / GRID))
        for ddx in range(-n, n + 1):
            for ddy in range(-n, n + 1):
                dist = math.hypot(ddx, ddy) * GRID
                if dist > R_ESCAPE or dist < 0.6 * R_ESCAPE:
                    continue
                ix2 = int(round(px / GRID)) + ddx
                iy2 = int(round(py / GRID)) + ddy
                if (ix2, iy2, lay0) in EXEMPT:
                    continue
                x2, y2 = ix2 * GRID, iy2 * GRID
                if w.blocked(x2, y2, lay0, netcode):
                    continue
                k2 = (ix2, iy2, lay0)
                if dist < cost.get(k2, 1e18):
                    cost[k2] = dist
                    came[k2] = (int(round(px / GRID)), int(round(py / GRID)), lay0)
                    heapq.heappush(openq, (dist + h(ix2, iy2), dist, k2))
    # 8-WAY, NOT 4-WAY. Kimi K3.1 Pro's review of this method (2026-11-03) identified the failure
    # mode exactly: measured escapes here are as narrow as 1/16 of the circle and can sit at any
    # angle, and a 4-way Manhattan grid can only leave a pad along +/-x or +/-y. If the single free
    # wedge at r=0.40mm is off-axis, no axis-aligned path stays inside it, so the search reports
    # "no path" on a pad that has a legal escape. Diagonals let the path follow an off-axis corridor.
    # The clearance check is unchanged and runs on every candidate point, so a diagonal move cannot
    # pass closer than a straight one -- the cost of a diagonal is sqrt(2) grid units, not 1.
    n = 0
    # DEADLINE INSIDE THE SEARCH, not just between pairs. Measured 2026-11-03: with 8-way moves a
    # single A* over a 42 mm pair ran past 500 s while the outer budget only checked AFTER each pair,
    # so one hard pair could consume the whole run and the remaining pairs were reported as
    # "budget exhausted" without ever being attempted. The deadline now stops the search itself and
    # the pair is reported as "no path within deadline" -- an honest partial, not a silent stall.
    deadline = _time.monotonic() + max(1.0, per_pair_s)
    while openq and n < 300000:
        if _time.monotonic() > deadline:
            return None
        n += 1
        _f, c, cur = heapq.heappop(openq)
        if cur in seen:
            continue
        seen.add(cur)
        ix, iy, lay = cur
        if (ix, iy) == (g[0], g[1]):
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return [(p[0] * GRID, p[1] * GRID, p[2]) for p in reversed(path)]
        for dx, dy in steps:
            nx, ny = ix + dx, iy + dy
            x, y = nx * GRID, ny * GRID
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            if (nx, ny, lay) not in EXEMPT and w.blocked(x, y, lay, netcode):
                continue
            nxt = (nx, ny, lay)
            nc = c + (GRID * 1.41421 if (dx and dy) else GRID)
            if nc < cost.get(nxt, 1e18):
                cost[nxt] = nc
                came[nxt] = cur
                heapq.heappush(openq, (nc + h(nx, ny), nc, nxt))
        # layer change
        if w.via_ok(ix * GRID, iy * GRID, netcode):
            # FLIP BETWEEN THE TWO ROUTABLE LAYERS, by id. `1 - lay` produced layer 1 (an inner layer).
            nxt = (ix, iy, LAYERS[1 - LAYERS.index(lay)] if lay in LAYERS else LAYERS[0])
            nc = c + 3.0
            if nc < cost.get(nxt, 1e18):
                cost[nxt] = nc
                came[nxt] = cur
                heapq.heappush(openq, (nc + h(ix, iy), nc, nxt))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--dru", required=True)
    ap.add_argument("--report", default=".")
    ap.add_argument("--max-pairs", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--per-pair-s", type=float, default=25.0,
                    help="A* deadline per pair; exceeded pairs report no path within deadline")
    ap.add_argument("--budget-s", type=float, default=240.0,
                    help="wall-clock budget for the routing loop; unattempted pairs are reported")
    a = ap.parse_args()

    before, ubefore, d = run_drc(a.src, a.dru, os.path.join(a.report, "route-before.json"))
    if d is None:
        print("DRC failed")
        return 1
    b = pcbnew.LoadBoard(a.src)
    w = World(b)

    pairs, skipped = [], []
    for it in d.get("unconnected_items", []):
        ds = [i["description"] for i in it["items"]]
        ms = [PAD_RE.search(x) for x in ds]
        if len(ms) != 2 or not all(ms):
            skipped.append(("not-a-pad-pair", " <> ".join(ds)[:90]))
            continue
        (n1, net1, r1, l1), (n2, net2, r2, l2) = [m.groups() for m in ms]
        if net1 != net2:
            skipped.append(("net-mismatch", f"{net1} vs {net2}"))
            continue
        if n1 == n2 and r1 == r2:
            # two-face wing tab: assembly joins these by solder (ADR-120 R1)
            skipped.append(("two-face-tab", f"{r1}.{n1}"))
            continue
        p1, p2 = w.pads.get((r1, n1)), w.pads.get((r2, n2))
        if not p1 or not p2:
            skipped.append(("pad-missing", f"{r1}.{n1}/{r2}.{n2}"))
            continue
        pairs.append((net1, p1, p2, f"{r1}.{n1}->{r2}.{n2}"))

    print(f"unconnected before: {ubefore}")
    print(f"pad-pairs to attempt: {len(pairs)}   skipped: {len(skipped)}")
    from collections import Counter as C
    print("  skip reasons:", dict(C(r for r, _ in skipped)))

    netnames = {b.FindNet(p[0]).GetNetCode() for p in pairs if b.FindNet(p[0])}
    done, failed = [], []
    import time as _time
    t_start = _time.time()
    budget_s = getattr(a, "budget_s", 240.0)
    for i, (net, p1, p2, label) in enumerate(pairs[:a.max_pairs]):
        if _time.time() - t_start > budget_s:
            failed.append((label, "budget exhausted (not attempted)"))
            continue
        nobj = b.FindNet(net)
        if nobj is None:
            failed.append((label, "no net"))
            continue
        code = nobj.GetNetCode()
        s = p1.GetPosition()
        e = p2.GetPosition()
        l0 = 0 if p1.IsOnLayer(pcbnew.F_Cu) else 2
        gl = 0 if p2.IsOnLayer(pcbnew.F_Cu) else 2
        path = astar(w, (s.x / UM, s.y / UM), (e.x / UM, e.y / UM), code, l0, goal_layer=gl,
                     per_pair_s=getattr(a, "per_pair_s", 25.0))
        if not path:
            failed.append((label, "no path"))
            continue
        # commit
        prev = None
        for (x, y, lay) in path:
            if prev and prev[2] == lay:
                tr = pcbnew.PCB_TRACK(b)
                tr.SetStart(pcbnew.VECTOR2I(int(prev[0] * UM), int(prev[1] * UM)))
                tr.SetEnd(pcbnew.VECTOR2I(int(x * UM), int(y * UM)))
                tr.SetWidth(int(TRACK_W * UM))
                tr.SetLayer(pcbnew.F_Cu if lay == 0 else pcbnew.B_Cu)
                tr.SetNet(nobj)
                b.Add(tr)
            if prev and prev[2] != lay:
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(int(x * UM), int(y * UM)))
                v.SetWidth(int(VIA_D * UM))
                v.SetDrill(int(VIA_DRILL * UM))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(nobj)
                b.Add(v)
            prev = (x, y, lay)
        done.append(label)
        # update the world so the next pair routes around this one
        w = World(b)

    print(f"routed: {len(done)}   failed: {len(failed)}")
    if failed:
        print("  failed:", failed[:10])
    if a.dry_run:
        print("dry run: not saved")
        return 0

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(a.out)
    after, uafter, d2 = run_drc(a.out, a.dru, os.path.join(a.report, "route-after.json"))
    print(f"\nBEFORE {dict(before)} unconnected={ubefore}")
    print(f"AFTER  {dict(after)} unconnected={uafter}")
    new = set(after) - set(before)
    print(f"NEW classes: {sorted(new) if new else 'none'}")
    hard = {"shorting_items", "clearance", "tracks_crossing", "hole_to_hole",
            "holes_co_located", "copper_edge_clearance"}
    if hard & set(after):
        print("REFUSING: short/clearance class present in result")
        return 3
    json.dump({"routed": done, "failed": failed}, open(os.path.join(a.report, "route-log.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
