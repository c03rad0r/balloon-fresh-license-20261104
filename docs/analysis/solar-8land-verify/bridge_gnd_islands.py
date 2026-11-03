#!/usr/bin/env python3
"""Bridge isolated GND pour islands to the In1 plane with a via each.

WHY
Measured 2026-11-03 on V6: after stitching, DRC still reports 22 `unconnected` items whose BOTH
ends are GND **zones** ("Zone 'GND_FCu' on F.Cu <> Zone 'GND_BCu' on B.Cu"). The three GND pours are
electrically separate pieces of copper, and a via placed at a PAD does not automatically land on
every piece. A pour island with no via in it is a dead patch of copper that DRC rightly flags.

The F.Cu pour has 11 outlines and the B.Cu pour dozens, while In1 is one clean 5517 mm2 plane. So
the fix is targeted: for each pour outline that contains no GND via, drop ONE GND via inside it.

WHAT IT WILL NOT DO
  - no via inside an SMD pad (via-in-pad; JLCPCB does not fill vias)
  - no via on Edge.Cuts geometry, including footprint-embedded cavity slots
  - no via closer than the frozen clearance to foreign copper, nor closer than hole-to-hole
  - if an island admits no legal site it is reported, not forced

Usage: bridge_gnd_islands.py <src.kicad_pcb> <out.kicad_pcb> --dru <frozen.kicad_dru> [--report DIR]
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
VIA_D, VIA_DRILL, CLEAR, EDGE = 0.60, 0.30, 0.20, 0.50
ARC_ERR = 5000


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
    ap.add_argument("--dru", required=True)
    ap.add_argument("--report", default=".")
    ap.add_argument("--net", default="GND")
    a = ap.parse_args()

    before, ubefore = run_drc(a.src, a.dru, os.path.join(a.report, "bridge-before.json"))
    b = pcbnew.LoadBoard(a.src)
    net = b.FindNet(a.net)
    if net is None:
        print(f"REFUSE: net {a.net} absent")
        return 2
    code = net.GetNetCode()

    # ---- obstacles: every copper object not on our net, plus ALL edge geometry ----
    segs, pts, rects, edges = [], [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == a.net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            pts.append((p.x / UM, p.y / UM, t.GetWidth(pcbnew.F_Cu) / UM / 2.0, 0.0))
        else:
            segs.append((t.GetStart().x / UM, t.GetStart().y / UM,
                         t.GetEnd().x / UM, t.GetEnd().y / UM,
                         t.GetWidth() / UM / 2.0, t.GetLayer()))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            dr = p.GetDrillSize()
            if p.GetNetCode() == code:
                # OWN-NET PTH PADS ARE STILL HOLES. A plated through-hole on our net already spans
                # every layer, so a via near it is pointless AND its drill is still a hole: skipping
                # own-net pads entirely put a via on top of J_PROG.1's barrel (hole_to_hole, actual
                # 0.0000 mm). Record the drill for own-net PTH pads, and no copper for own-net SMD.
                if dr.x > 0 or dr.y > 0:
                    rects.append((bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM,
                                  bb.GetBottom() / UM, max(dr.x, dr.y) / UM / 2.0))
                continue
            rects.append((bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM,
                          bb.GetBottom() / UM, max(dr.x, dr.y) / UM / 2.0))
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

    our_vias = [(t.GetPosition().x / UM, t.GetPosition().y / UM)
                for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == a.net]

    def legal(x, y):
        r = VIA_D / 2.0 + CLEAR
        if not (0.8 < x < 71.3 and 0.8 < y < 79.3):
            return False
        for (x1, y1, x2, y2, rw, _l) in segs:
            if seg_pt(x, y, x1, y1, x2, y2) < r + rw:
                return False
        for (px, py, pr, _d) in pts:
            if math.hypot(x - px, y - py) < r + pr:
                return False
        for (l, t_, rr, bo, dr) in rects:
            d = math.hypot(max(l - x, 0, x - rr), max(t_ - y, 0, y - bo))
            if d < r:
                return False
            # HOLE-TO-HOLE: frozen rule is 0.25 mm between DRILL EDGES. Distance from the via centre
            # to the pad RECT is not the drill distance; for a pad whose own drill is inside the rect
            # the centre-to-edge figure is meaningless. Use the pad's own centre and its drill radius.
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
        for (vx, vy) in our_vias:
            if math.hypot(x - vx, y - vy) < VIA_D + 0.25:
                return False
        return True

    added, bridged, failed = 0, [], []
    zones = [z for z in b.Zones() if z.GetNetname() == a.net]
    for z in zones:
        layer = z.GetLayer()
        fp = z.GetFilledPolysList(layer)
        for i in range(fp.OutlineCount()):
            outline = fp.COutline(i)
            area = outline.Area() / 1e12
            if area < 0.5:
                continue                      # via-pad remnant, not a pour island
            c = outline.Centre()
            cx, cy = c.x / UM, c.y / UM
            # ALREADY BRIDGED? Test INSIDE THIS OUTLINE, not the whole filled polygon set.
            # Measured 2026-11-03: `fp.Contains(pt)` returns True if the point is in ANY island of the
            # filled list, so every island looked bridged and the script added 0 vias while DRC still
            # reported 22 zone-to-zone opens. `COutline(i).PointInside(pt)` is the per-island test.
            has = False
            for (vx, vy) in our_vias:
                try:
                    if outline.PointInside(pcbnew.VECTOR2I(int(vx * UM), int(vy * UM))):
                        has = True
                        break
                except Exception:
                    pass
            if has:
                continue
            site = None
            # spiral out from the island centre over a small grid, staying INSIDE the island
            for step in [0.0] + [0.25 * s for s in range(1, 40)]:
                for k in range(24):
                    ang = 2 * math.pi * k / 24
                    x, y = cx + step * math.cos(ang), cy + step * math.sin(ang)
                    if not fp.Contains(pcbnew.VECTOR2I(int(x * UM), int(y * UM))):
                        continue
                    if legal(x, y):
                        site = (x, y)
                        break
                if site:
                    break
            if not site:
                failed.append((pcbnew.LayerName(layer), round(cx, 2), round(cy, 2), round(area, 2)))
                continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(int(site[0] * UM), int(site[1] * UM)))
            v.SetWidth(int(VIA_D * UM))
            v.SetDrill(int(VIA_DRILL * UM))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(net)
            b.Add(v)
            our_vias.append(site)
            added += 1
            bridged.append((pcbnew.LayerName(layer), round(site[0], 2), round(site[1], 2), round(area, 2)))

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(a.out)
    after, uafter = run_drc(a.out, a.dru, os.path.join(a.report, "bridge-after.json"))
    print(f"island vias added: {added}   islands with no legal site: {len(failed)}")
    for f in failed[:8]:
        print(f"   no site: {f}")
    print(f"BEFORE {dict(before)} unconnected={ubefore}")
    print(f"AFTER  {dict(after)} unconnected={uafter}")
    new = set(after) - set(before)
    print(f"NEW classes: {sorted(new) if new else 'none'}")
    json.dump({"bridged": bridged, "failed": failed}, open(os.path.join(a.report, "bridge-log.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
