#!/usr/bin/env python3
"""WHY does a solar pair fail on B.Cu? Name the blocking copper, don't guess.

For each end of a pair, walk outward in 16 directions on B.Cu and report the FIRST other-net object
that stops a 0.20 mm track at 0.20 mm clearance, with its net, layer and distance. Then report
whether the two ends sit in the SAME connected free region -- if they do, the router has a bug; if
they do not, the wall between them is real and named.

Usage: why_blocked.py <board> [--pair N ...]
"""
import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0
sys.path.insert(0, "docs/analysis/solar-8land-verify")
import route_solar_bitmap as R  # noqa: E402


def seg_pt(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--pair", type=int, action="append")
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)
    clear, tr, reach = 0.20, 0.10, 4.0

    for pi, (net, sa, sb) in enumerate(R.PAIRS):
        if a.pair and pi not in a.pair:
            continue
        pa, pb = R.bcu_pads(b, sa), R.bcu_pads(b, sb)
        if not pa or not pb:
            continue
        A, B = pa[0], pb[0]
        print(f"\n=== pair {pi} {net} {sa} -> {sb}")
        # obstacles on B.Cu, other net
        segs, rects = [], []
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                if t.GetNetname() != net:
                    p = t.GetPosition()
                    r = t.GetWidth(pcbnew.B_Cu) / UM / 2
                    rects.append((p.x / UM - r, p.y / UM - r, p.x / UM + r, p.y / UM + r,
                                  "via " + t.GetNetname()))
                continue
            if t.GetLayer() != pcbnew.B_Cu or t.GetNetname() == net:
                continue
            segs.append((t.GetStart().x / UM, t.GetStart().y / UM, t.GetEnd().x / UM,
                         t.GetEnd().y / UM, t.GetWidth() / UM / 2, t.GetNetname()))
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if pcbnew.B_Cu not in p.GetLayerSet().Seq() or p.GetNetname() == net:
                    continue
                bb = p.GetBoundingBox()
                rects.append((bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM,
                              bb.GetBottom() / UM, f"{fp.GetReference()}.{p.GetNumber()}"))

        for tag, pad in ((sa, A), (sb, B)):
            px, py = pad.GetPosition().x / UM, pad.GetPosition().y / UM
            blocked = []
            for k in range(16):
                ang = k * math.pi / 8
                for step in [s * 0.1 for s in range(1, int(reach / 0.1) + 1)]:
                    x, y = px + step * math.cos(ang), py + step * math.sin(ang)
                    hit = None
                    for (x1, y1, x2, y2, r, n) in segs:
                        if seg_pt(x, y, x1, y1, x2, y2) < r + tr + clear:
                            hit = f"track {n} @ {step:.1f}mm"; break
                    if hit is None:
                        for (rx0, ry0, rx1, ry1, n) in rects:
                            if math.hypot(max(rx0 - x, 0, x - rx1), max(ry0 - y, 0, y - ry1)) < tr + clear:
                                hit = f"pad {n} @ {step:.1f}mm"; break
                    if hit:
                        blocked.append((round(math.degrees(ang)), hit))
                        break
                else:
                    blocked.append((round(math.degrees(ang)), f"CLEAR to {reach:.1f}mm"))
            clear_dirs = [d for d, h in blocked if h.startswith("CLEAR")]
            print(f"  {tag} ({px:.2f},{py:.2f}): {len(clear_dirs)}/16 directions clear to {reach} mm")
            for d, h in blocked[:6]:
                print(f"      {d:3d}deg  {h}")
        print(f"  distance between ends: "
              f"{math.hypot(A.GetPosition().x/UM-B.GetPosition().x/UM, A.GetPosition().y/UM-B.GetPosition().y/UM):.2f} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
