#!/usr/bin/env python3
"""Tap pads of a NET onto a plane/pour of the SAME net, without via-in-pad.

THE PROBLEM THIS SOLVES, MEASURED 2026-11-03 on hub_board_v10_lora1280_7of9:
`/VSCAP` has one 4467 mm2 zone on B.Cu and 11 pads — but ZERO tracks and ZERO vias. Five of the
pads are F.Cu-only, so they have no copper path to a B.Cu pour at all, and DRC reports the zone as
disconnected FROM ITSELF (two islands, 4362 + 104 mm2). Adding a via inside a B.Cu island without a
matching front-side tap produces `via_dangling`: a via that lands on the pour on one side and on
nothing on the other.

So this does the pairing: for each SMD pad on a layer that the pour is NOT on, place a via BESIDE
the pad joined by a short track of the same net, so pad -> track -> via -> pour is continuous on
both faces. GND stitching is the same geometry, which is why the ring-outside-pad rule is reused.

HARD RULES (unchanged from the stitcher):
  - via >= 0.60 mm pad / 0.30 mm drill (frozen S1; ADR-142 keeps it)
  - NEVER at a pad centre — JLCPCB does not fill/cap vias, so an uncapped barrel in a pad wicks
    solder. The via starts beyond the pad's half-diagonal.
  - no site within clearance of foreign copper, or within hole-to-hole of ANY drill (including
    own-net PTH pads, which still occupy a hole)
  - no site on Edge.Cuts, including the cavity slots embedded in the J_W footprints
  - the STUB from pad to via is clearance-checked too, on its own layer
  - a pad with no legal site is REPORTED, not forced

Usage: tap_net_to_plane.py <src> <out> --net /VSCAP --dru <frozen.kicad_dru> [--report DIR]
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

UM = 1_000_000.0
VIA_D, VIA_DRILL, CLEAR, EDGE, TRACK_W = 0.60, 0.30, 0.20, 0.50, 0.20
ARC_ERR = 5000
R_MAX = 4.0


def run_drc(pcb, dru, out_json):
    stem = os.path.splitext(pcb)[0]
    shutil.copyfile(dru, stem + ".kicad_dru")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out_json, pcb], capture_output=True, text=True)
    if not os.path.exists(out_json):
        return None, None
    d = json.load(open(out_json))
    from collections import Counter
    return Counter(v["type"] for v in d.get("violations", [])), len(d.get("unconnected_items", []))


def seg_pt(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--net", required=True)
    ap.add_argument("--dru", required=True)
    ap.add_argument("--report", default=".")
    a = ap.parse_args()

    before, ubefore = run_drc(a.src, a.dru, os.path.join(a.report, "tapnet-before.json"))
    b = pcbnew.LoadBoard(a.src)
    net = b.FindNet(a.net)
    if net is None:
        print(f"REFUSE: {a.net} absent")
        return 2
    code = net.GetNetCode()

    segs, pts, rects, edges = [], [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == a.net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            pts.append((p.x / UM, p.y / UM, t.GetWidth(pcbnew.F_Cu) / UM / 2.0))
        else:
            segs.append((t.GetStart().x / UM, t.GetStart().y / UM,
                         t.GetEnd().x / UM, t.GetEnd().y / UM,
                         t.GetWidth() / UM / 2.0, t.GetLayer()))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            dr = p.GetDrillSize()
            if p.GetNetCode() == code and dr.x == 0 and dr.y == 0:
                continue                      # own-net SMD pad is not an obstacle
            rects.append((bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM,
                          bb.GetBottom() / UM, max(dr.x, dr.y) / UM / 2.0,
                          p.GetNetCode() == code))
    for d_ in b.GetDrawings():
        if d_.GetLayer() == pcbnew.Edge_Cuts:
            try:
                ps = pcbnew.SHAPE_POLY_SET()
                d_.TransformShapeToPolygon(ps, pcbnew.Edge_Cuts, 0, ARC_ERR, pcbnew.ERROR_INSIDE)
                edges.append(ps)
            except Exception:
                pass
    for fp in b.GetFootprints():
        for gi in fp.GraphicalItems():
            if gi.GetLayer() != pcbnew.Edge_Cuts:
                continue
            try:
                ps = pcbnew.SHAPE_POLY_SET()
                gi.TransformShapeToPolygon(ps, pcbnew.Edge_Cuts, 0, ARC_ERR, pcbnew.ERROR_INSIDE)
                edges.append(ps)
            except Exception:
                pass

    pour_layers = {z.GetLayer() for z in b.Zones() if z.GetNetname() == a.net}

    def legal(x, y, layer, pad_bbox):
        r = VIA_D / 2.0 + CLEAR
        if not (0.8 < x < 71.3 and 0.8 < y < 79.3):
            return False
        # A TRACK ON THE OTHER LAYER IS STILL AN OBSTACLE. A via is drilled through the whole stack,
        # so the annulus collides with copper on EVERY layer, not just the one being tapped.
        # Measured 2026-11-03: filtering tracks by `layer` put a /VSCAP via straight onto a
        # /W1_SOLAR_N B.Cu track -- an actual short, not a clearance nibble.
        for (x1, y1, x2, y2, rw, lay) in segs:
            if seg_pt(x, y, x1, y1, x2, y2) < r + rw:
                return False
        for (px, py, pr) in pts:
            if math.hypot(x - px, y - py) < r + pr:
                return False
        for (l, t_, rr, bo, dr, own) in rects:
            d = math.hypot(max(l - x, 0, x - rr), max(t_ - y, 0, y - bo))
            if d < r and not own:
                return False
            if dr > 0:
                pcx, pcy = (l + rr) / 2.0, (t_ + bo) / 2.0
                if math.hypot(x - pcx, y - pcy) < VIA_DRILL / 2.0 + dr + 0.25:
                    return False
        pt = pcbnew.VECTOR2I(int(x * UM), int(y * UM))
        for es in edges:
            try:
                if es.Distance(pt) < int((EDGE + VIA_D / 2.0) * UM):
                    return False
            except Exception:
                pass
        return True

    def stub_ok(cx, cy, x, y, layer, pad_bbox):
        r = TRACK_W / 2.0 + CLEAR
        steps = max(2, int(math.hypot(x - cx, y - cy) / 0.05))
        for s in range(steps + 1):
            t = s / steps
            px, py = cx + t * (x - cx), cy + t * (y - cy)
            l, t2, rr, bo = pad_bbox
            if l - 0.01 <= px <= rr + 0.01 and t2 - 0.01 <= py <= bo + 0.01:
                continue
            for (x1, y1, x2, y2, rw, lay) in segs:
                if lay == layer and seg_pt(px, py, x1, y1, x2, y2) < r + rw:
                    return False
            # VIAS ARE HOLES THROUGH EVERY LAYER: the stub must clear them on its own layer too.
            # Measured 2026-11-03: a /VSCAP F.Cu stub passed 0.008 mm from a GND stitching via.
            for (px2, py2, pr2) in pts:
                if math.hypot(px - px2, py - py2) < r + pr2:
                    return False
            for (pl, pt_, prr, pbo, dr, own) in rects:
                if own:
                    continue
                if pl <= px <= prr and pt_ <= py <= pbo:
                    return False
                if math.hypot(max(pl - px, 0, px - prr), max(pt_ - py, 0, py - pbo)) < r:
                    return False
        return True

    added, failed = 0, []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != code:
                continue
            # only pads that are NOT on a pour layer need a tap
            pad_layers = {l for l in pad.GetLayerSet().Seq()}
            if pad_layers & pour_layers:
                continue
            if pad.GetDrillSize().x > 0:
                continue                      # PTH already spans everything
            c = pad.GetPosition()
            cx, cy = c.x / UM, c.y / UM
            bb = pad.GetBoundingBox()
            pbb = (bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM, bb.GetBottom() / UM)
            lay = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            half_diag = 0.5 * math.hypot(pbb[2] - pbb[0], pbb[3] - pbb[1])
            r0 = max(VIA_D / 2.0 + CLEAR, half_diag + VIA_D / 2.0 + CLEAR)
            site = None
            for k in range(48):
                ang = 2 * math.pi * k / 48
                for step in [r0 + 0.15 * s for s in range(0, int(max(0.0, R_MAX - r0) / 0.15) + 1)]:
                    x, y = cx + step * math.cos(ang), cy + step * math.sin(ang)
                    if legal(x, y, lay, pbb) and stub_ok(cx, cy, x, y, lay, pbb):
                        site = (x, y)
                        break
                if site:
                    break
            if not site:
                failed.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(int(site[0] * UM), int(site[1] * UM)))
            v.SetWidth(int(VIA_D * UM))
            v.SetDrill(int(VIA_DRILL * UM))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(net)
            b.Add(v)
            tr = pcbnew.PCB_TRACK(b)
            tr.SetStart(pcbnew.VECTOR2I(int(cx * UM), int(cy * UM)))
            tr.SetEnd(pcbnew.VECTOR2I(int(site[0] * UM), int(site[1] * UM)))
            tr.SetWidth(int(TRACK_W * UM))
            tr.SetLayer(lay)
            tr.SetNet(net)
            b.Add(tr)
            added += 1

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(a.out)
    after, uafter = run_drc(a.out, a.dru, os.path.join(a.report, "tapnet-after.json"))
    print(f"{a.net} taps added: {added}   pads with no legal site: {len(failed)} {failed[:8]}")
    print(f"BEFORE {dict(before)} unconnected={ubefore}")
    print(f"AFTER  {dict(after)} unconnected={uafter}")
    new = set(after) - set(before)
    print(f"NEW classes: {sorted(new) if new else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
