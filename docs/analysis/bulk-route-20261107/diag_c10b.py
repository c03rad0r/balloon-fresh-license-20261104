#!/usr/bin/env python3
"""Probe the KiCad 9 python connectivity API, then print what C10.1 is actually attached to.

Two earlier checks disagreed (shapely island vs native DRC 38 opens) and one of them is a
CHECKER bug. `diag_c10.py` measured distance to track ENDPOINTS only, so a track whose BODY
passes a pad reads as far away. This file asks KiCad instead of re-deriving, and uses exact
segment distance for the geometric cross-check.
"""
import math
import sys

import pcbnew

UM = 1e6


def seg_pt_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_rect_dist(x0, y0, x1, y1, r):
    rx0, ry0, rx1, ry1 = r
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(L / 0.01) + 2)
    for i in range(n + 1):
        t = i / n
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if rx0 <= px <= rx1 and ry0 <= py <= ry1:
            return 0.0
    best = 1e9
    for ex0, ey0, ex1, ey1 in ((rx0, ry0, rx1, ry0), (rx1, ry0, rx1, ry1),
                               (rx1, ry1, rx0, ry1), (rx0, ry1, rx0, ry0)):
        best = min(best, seg_pt_dist(ex0, ey0, x0, y0, x1, y1))
        best = min(best, seg_pt_dist(x0, y0, ex0, ey0, ex1, ey1))
    return best


def main(board_path):
    b = pcbnew.LoadBoard(board_path)
    names = [n for n in dir(pcbnew) if n.endswith("_T") and "PCB" in n]
    print("pcbnew *_T constants:", sorted(names)[:40])
    conn = b.GetConnectivity()
    print("unconnected (KiCad):", conn.GetUnconnectedCount(False))
    print("GetConnectedItems signature:",
          conn.GetConnectedItems.__doc__)

    r = (9.070, 42.920, 9.690, 43.480)   # C10.1 F.Cu pad rect, measured
    print(f"\n+3V3 copper within 1.5 mm of C10.1 rect {r} (EXACT segment distance):")
    for t in b.GetTracks():
        if t.GetNetname() != "+3V3":
            continue
        if "VIA" in str(type(t)):
            p = t.GetPosition()
            d = seg_rect_dist(p.x / UM, p.y / UM, p.x / UM, p.y / UM, r) - t.GetWidth(pcbnew.F_Cu) / UM / 2
            what = f"VIA ({p.x/UM:.3f},{p.y/UM:.3f}) dia={t.GetWidth(pcbnew.F_Cu)/UM:.2f}"
        else:
            a, c = t.GetStart(), t.GetEnd()
            d = (seg_rect_dist(a.x / UM, a.y / UM, c.x / UM, c.y / UM, r)
                 - t.GetWidth() / UM / 2)
            what = (f"TRK {pcbnew.LayerName(t.GetLayer())} "
                    f"({a.x/UM:.2f},{a.y/UM:.2f})-({c.x/UM:.2f},{c.y/UM:.2f}) "
                    f"w={t.GetWidth()/UM:.2f}")
        if d < 1.5:
            print(f"   gap {d:+.4f} mm  {what}")

    print("\n+3V3 pads within 2 mm of C10.1 rect:")
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != "+3V3":
                continue
            bb = p.GetBoundingBox()
            pr = (bb.GetX() / UM, bb.GetY() / UM,
                  (bb.GetX() + bb.GetWidth()) / UM, (bb.GetY() + bb.GetHeight()) / UM)
            d = math.hypot(max(0, max(r[0] - pr[2], pr[0] - r[2])),
                           max(0, max(r[1] - pr[3], pr[1] - r[3])))
            if d < 2.0 and (f.GetReference(), p.GetNumber()) != ("C10", "1"):
                print(f"   gap {d:+.4f} mm  {f.GetReference()}.{p.GetNumber()} "
                      f"layers={[pcbnew.LayerName(x) for x in p.GetLayerSet().Seq() if x in (0, 31)]}")

    print("\nzones whose filled polygon touches C10.1 rect:")
    for z in b.Zones():
        for lid in z.GetLayerSet().CuStack():
            ps = z.GetFilledPolysList(lid)
            if ps.OutlineCount() == 0:
                continue
            for i in range(ps.OutlineCount()):
                sub = ps.UnitSet(i)
                bb = sub.BBox()
                zr = (bb.GetX() / UM, bb.GetY() / UM,
                      (bb.GetX() + bb.GetWidth()) / UM, (bb.GetY() + bb.GetHeight()) / UM)
                if not (zr[0] < r[2] + 1.5 and zr[2] > r[0] - 1.5
                        and zr[1] < r[3] + 1.5 and zr[3] > r[1] - 1.5):
                    continue
                print(f"   zone {z.GetZoneName() or '?'} net={z.GetNetname()} "
                      f"{pcbnew.LayerName(lid)} poly{i} bbox={tuple(round(v,2) for v in zr)}")


if __name__ == "__main__":
    main(sys.argv[1])
