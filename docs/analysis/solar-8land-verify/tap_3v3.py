#!/usr/bin/env python3
"""Tap +3V3 pads down to the In2.Cu plane with vias, or prove there is no room.

The 3V3 plane added by add_3v3_plane.py is geometrically legal but electrically orphaned: 16 +3V3
pads sit on F.Cu/B.Cu and nothing connects them to In2.Cu, so unconnected stays at 60. A plane with
no tap is not a connection. This drops a via beside each +3V3 pad (offset search, like the GND
stitcher) so the pad reaches the plane.

RULES IT WILL NOT BREAK
  - never a via smaller than 0.60 mm pad / 0.30 mm drill (frozen S1; ADR-142 keeps this)
  - never on a PTH pad (that pad already spans every layer; a via there is two drills at one XY)
  - never closer than the frozen clearance to a foreign net
  - if no site fits, the pad is reported UNRESOLVABLE rather than silently skipped

Usage: tap_3v3.py <src.kicad_pcb> <out.kicad_pcb> --dru <frozen.kicad_dru> --report DIR
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
NET = "+3V3"
VIA_D, VIA_DRILL = 0.60, 0.30
CLEAR = 0.20
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
    ap.add_argument("--dru", required=True)
    ap.add_argument("--report", default=".")
    a = ap.parse_args()

    before, ubefore = run_drc(a.src, a.dru, os.path.join(a.report, "tap-before.json"))
    board = pcbnew.LoadBoard(a.src)
    net = board.FindNet(NET)
    if net is None:
        print(f"REFUSE: {NET} not on board")
        return 2
    code = net.GetNetCode()

    # obstacles = every copper object NOT on +3V3
    segs, pts, rects = [], [], []
    for t in board.GetTracks():
        if t.GetNetname() == NET:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            pts.append((p.x / UM, p.y / UM, t.GetWidth(pcbnew.F_Cu) / UM / 2.0))
        else:
            if t.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu,
                                    board.GetLayerID("In1.Cu"), board.GetLayerID("In2.Cu")):
                continue
            segs.append((t.GetStart().x / UM, t.GetStart().y / UM,
                         t.GetEnd().x / UM, t.GetEnd().y / UM, t.GetWidth() / UM / 2.0,
                         t.GetLayer()))
    segs_l = segs
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == code:
                continue
            bb = p.GetBoundingBox()
            rects.append((bb.GetLeft() / UM, bb.GetTop() / UM,
                          bb.GetRight() / UM, bb.GetBottom() / UM, p.GetDrillSize().x / UM / 2.0))

    def free(x, y):
        r = VIA_D / 2.0 + CLEAR
        for (x1, y1, x2, y2, rw, _lay) in segs:
            if seg_pt(x, y, x1, y1, x2, y2) < r + rw:
                return False
        for (px, py, pr) in pts:
            if math.hypot(x - px, y - py) < r + pr:
                return False
        for (l, t, rr, b, dr) in rects:
            if math.hypot(max(l - x, 0, x - rr), max(t - y, 0, y - b)) < r:
                return False
            # hole-to-hole: frozen 0.25 mm between drill edges
            if dr > 0 and ((l <= x <= rr) and (t <= y <= b)):
                if math.hypot(max(l - x, 0, x - rr), max(t - y, 0, y - b)) < VIA_DRILL / 2 + dr + 0.25:
                    return False
        return True

    def stub_clear(cx, cy, x, y, layer, pad_bbox):
        """The STUB from pad centre to via site must itself be clear of foreign copper.

        Measured 2026-11-03: checking only the via site produced 4 tracks_crossing, 1 clearance and
        1 solder_mask_bridge, every one of them a +3V3 stub running through /SPI1_SCK, /F33_RESET_N,
        /GNSS_VCC or U1.8. A via site being free says nothing about the line that reaches it.
        The pad's own bbox is exempt -- the stub legitimately starts inside its own pad.
        """
        r = 0.20 / 2.0 + CLEAR
        steps = max(2, int(math.hypot(x - cx, y - cy) / 0.05))
        for s in range(steps + 1):
            t = s / steps
            px, py = cx + t * (x - cx), cy + t * (y - cy)
            if (pad_bbox[0] - 0.01 <= px <= pad_bbox[2] + 0.01
                    and pad_bbox[1] - 0.01 <= py <= pad_bbox[3] + 0.01):
                continue
            for (x1, y1, x2, y2, rw, lay) in segs_l:
                if lay != layer:
                    continue
                if seg_pt(px, py, x1, y1, x2, y2) < r + rw:
                    return False
            for (k, t2, rr, b, dr) in rects:
                if (k <= px <= rr and t2 <= py <= b):
                    return False
                if math.hypot(max(k - px, 0, px - rr), max(t2 - py, 0, py - b)) < r:
                    return False
        return True

    added, unres, pth_skip = 0, [], 0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != code:
                continue
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                pth_skip += 1
                continue
            c = pad.GetPosition()
            cx, cy = c.x / UM, c.y / UM
            bb = pad.GetBoundingBox()
            pbb = (bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM, bb.GetBottom() / UM)
            lay = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            # A via at the pad centre needs its annular ring INSIDE the pad. Measured 2026-11-03:
            # without this, 11 +3V3 vias landed on SMD pads including 0.62 x 0.56 mm ones -- via
            # overhanging the pad, solder wicking down the barrel. DRC does not check it.
            fits = (pbb[2] - pbb[0] >= VIA_D + 0.20 and pbb[3] - pbb[1] >= VIA_D + 0.20)
            site = None
            # START OUTSIDE THE PAD for offset vias: an unfilled via in an SMD pad wicks solder.
            # Measured 2026-11-03: 11 +3V3 vias landed inside pads including 0.62 x 0.56 mm ones.
            half_diag = 0.5 * math.hypot(pbb[2] - pbb[0], pbb[3] - pbb[1])
            r_start = max(VIA_D / 2.0 + CLEAR, half_diag + VIA_D / 2.0 + CLEAR)
            steps = [r_start + 0.15 * s for s in range(0, int((R_MAX - r_start) / 0.15) + 1)]
            for k in range(48):
                ang = 2 * math.pi * k / 48
                for step in steps:
                    x, y = cx + step * math.cos(ang), cy + step * math.sin(ang)
                    if not (0.8 < x < 71.3 and 0.8 < y < 79.3):
                        continue
                    if step == 0.0 and not fits:
                        continue
                    if not free(x, y):
                        continue
                    # the stub must reach the via, not just exist
                    if step > 0.0 and not stub_clear(cx, cy, x, y, lay, pbb):
                        continue
                    site = (x, y)
                    break
                if site:
                    break
            if not site:
                unres.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(site[0] * UM), int(site[1] * UM)))
            v.SetWidth(int(VIA_D * UM))
            v.SetDrill(int(VIA_DRILL * UM))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(net)
            board.Add(v)
            added += 1
            # stub track on the pad's own layer if the via is offset
            if math.hypot(site[0] - cx, site[1] - cy) > 0.01:
                lay = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(pcbnew.VECTOR2I(int(cx * UM), int(cy * UM)))
                tr.SetEnd(pcbnew.VECTOR2I(int(site[0] * UM), int(site[1] * UM)))
                tr.SetWidth(int(0.20 * UM))
                tr.SetLayer(lay)
                tr.SetNet(net)
                board.Add(tr)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(a.out)
    after, uafter = run_drc(a.out, a.dru, os.path.join(a.report, "tap-after.json"))
    print(f"3V3 vias added: {added}   PTH pads skipped: {pth_skip}   unresolvable: {len(unres)}")
    if unres:
        print("  unresolved:", ", ".join(unres))
    print(f"BEFORE {dict(before)} unconnected={ubefore}")
    print(f"AFTER  {dict(after)} unconnected={uafter}")
    new = set(after) - set(before)
    print(f"NEW classes: {sorted(new) if new else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
