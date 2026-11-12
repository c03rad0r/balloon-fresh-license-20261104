#!/usr/bin/env python3
"""Independently check the consultant's edge-hugging claim: nearest approach of every NEW track to
EVERY Edge.Cuts graphic (board rectangle AND the J_W footprint slots), in mm.

DRC reports `copper_edge_clearance` only where the rule is violated; this reports the actual minimum
distance per added segment, so "it runs along the edge" becomes a number.
"""
import json
import math
import sys

import pcbnew

UM = 1_000_000.0


def seg_pt(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def seg_seg(a1, a2, b1, b2):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2 = o(a1, a2, b1), o(a1, a2, b2)
    o3, o4 = o(b1, b2, a1), o(b1, b2, a2)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return 0.0
    return min(seg_pt(*b1, *a1, *a2), seg_pt(*b2, *a1, *a2),
               seg_pt(*a1, *b1, *b2), seg_pt(*a2, *b1, *b2))


def edge_segments(board):
    out = []
    for d in board.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        out.append(("BOARD", (d.GetStart().x / UM, d.GetStart().y / UM,
                              d.GetEnd().x / UM, d.GetEnd().y / UM)))
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.Edge_Cuts:
                out.append((fp.GetReference(), (g.GetStart().x / UM, g.GetStart().y / UM,
                                                g.GetEnd().x / UM, g.GetEnd().y / UM)))
    return out


def main():
    before = pcbnew.LoadBoard(sys.argv[1])
    after = pcbnew.LoadBoard(sys.argv[2])

    def sig(b):
        s = set()
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                continue
            s.add((round(t.GetStart().x / UM, 3), round(t.GetStart().y / UM, 3),
                   round(t.GetEnd().x / UM, 3), round(t.GetEnd().y / UM, 3),
                   t.GetNetname(), pcbnew.LayerName(t.GetLayer())))
        return s

    new = sig(after) - sig(before)
    removed = sig(before) - sig(after)
    print(f"new segments: {len(new)}   removed segments: {len(removed)}")
    edges = edge_segments(after)
    print(f"Edge.Cuts graphics considered: {len(edges)} "
          f"({sum(1 for e in edges if e[0] == 'BOARD')} board, "
          f"{sum(1 for e in edges if e[0] != 'BOARD')} footprint slots)")

    worst = []
    for (x1, y1, x2, y2, net, lay) in new:
        best = None
        who = None
        for name, (ex1, ey1, ex2, ey2) in edges:
            d = seg_seg((x1, y1), (x2, y2), (ex1, ey1), (ex2, ey2))
            if best is None or d < best:
                best, who = d, name
        worst.append((best, net, who, (x1, y1, x2, y2)))
    worst.sort()
    print("\nnearest approach of each NEW segment to any Edge.Cuts graphic (mm):")
    for d, net, who, seg in worst[:12]:
        print(f"   {d:6.3f}  {net:14s} to {who:6s}  seg=({seg[0]:.2f},{seg[1]:.2f})-"
              f"({seg[2]:.2f},{seg[3]:.2f})")
    if worst:
        d, net, who, seg = worst[0]
        print(f"\nMINIMUM: {d:.3f} mm ({net} to {who})")
        print("rule: copper_edge_clearance requires 0.50 mm; the J_W* PADS are allow-listed by ref, "
              "TRACKS are not. A new track below 0.50 mm is a real violation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
