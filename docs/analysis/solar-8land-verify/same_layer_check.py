#!/usr/bin/env python3
"""Same-layer geometric crossing check for the solar routes.

A 2D render flattens F.Cu and B.Cu together, so a vision reviewer sees "crossings" that are
legal different-layer crossings. This answers the question the image cannot: does any solar track
intersect another net's copper **on the same layer**?

Method: segment-segment intersection on B.Cu only, plus via-to-track and via-to-pad distance, with
the real widths. Reports geometry, and states plainly that kicad-cli DRC is the authority.

Usage: same_layer_check.py <board>
"""
import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0


def seg_int(p, q, r, s):
    """True if segment pq properly intersects rs (shared endpoints / collinear touching excluded)."""
    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1, d2 = cr(r, s, p), cr(r, s, q)
    d3, d4 = cr(p, q, r), cr(p, q, s)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def seg_seg_dist(p, q, r, s):
    def pt_seg(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    return min(pt_seg(p[0], p[1], r[0], r[1], s[0], s[1]),
               pt_seg(q[0], q[1], r[0], r[1], s[0], s[1]),
               pt_seg(r[0], r[1], p[0], p[1], q[0], q[1]),
               pt_seg(s[0], s[1], p[0], p[1], q[0], q[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--net", default="SOLAR")
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)

    solar, other = [], []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        if t.GetLayer() != pcbnew.B_Cu:
            continue
        seg = ((t.GetStart().x / UM, t.GetStart().y / UM),
               (t.GetEnd().x / UM, t.GetEnd().y / UM), t.GetWidth() / UM / 2.0,
               t.GetNetname())
        (solar if a.net.upper() in t.GetNetname().upper() else other).append(seg)

    print(f"B.Cu segments: solar={len(solar)} other={len(other)}")

    xs, cl, mn = 0, 0, (9e9, None)
    for (p, q, rp, n1) in solar:
        for (r, s, rr, n2) in other:
            if seg_int(p, q, r, s):
                xs += 1
                print(f"  CROSS {n1} x {n2} at {p}->{q}")
                continue
            d = seg_seg_dist(p, q, r, s) - (rp + rr)
            if d < 0.20:
                cl += 1
                print(f"  CLOSE {d:+.3f}mm {n1} vs {n2}")
            if d < mn[0]:
                mn = (d, f"{n1} vs {n2}")

    # vias of any net against solar tracks
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    vmin = (9e9, None)
    for v in vias:
        vp = (v.GetPosition().x / UM, v.GetPosition().y / UM)
        vr = v.GetWidth(pcbnew.B_Cu) / UM / 2.0
        for (p, q, rp, n1) in solar:
            if v.GetNetname() == n1:
                continue
            d = seg_seg_dist(vp, vp, p, q) - (vr + rp)
            if d < vmin[0]:
                vmin = (d, f"via {v.GetNetname()} vs {n1}")

    print(f"\nsame-layer crossings (B.Cu solar vs B.Cu other): {xs}")
    print(f"same-layer pairs closer than 0.20 mm: {cl}")
    print(f"closest same-layer approach: {mn[0]:.4f} mm  ({mn[1]})")
    print(f"closest via-to-solar-track: {vmin[0]:.4f} mm  ({vmin[1]})")
    print("\nAuthority for pass/fail is kicad-cli DRC ('shorting_items', 'clearance').")
    print("This script exists to explain a 2D render, not to overrule the DRC.")
    return 0 if xs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
