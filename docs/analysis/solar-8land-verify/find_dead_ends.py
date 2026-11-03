#!/usr/bin/env python3
"""Find track ends that reach nothing, and map image coordinates to board millimetres.

A spatial reviewer keeps flagging "a track ends in empty space near (235, 950) px" across several
renders. A pixel is not a coordinate, so this reports every real dead end in BOARD millimetres and
also prints the exact pixel each would land at, given the render geometry. That way the reviewer's
claim can be confirmed or dismissed against a specific object rather than a region.

DEAD END definition, deliberately strict:
  a track endpoint that is (a) not shared with any other track on the same layer+net,
  (b) not inside or within 0.05 mm of a pad on that net, and (c) not within 0.05 mm of a via
  on that net. Anything looser reported 750 false positives earlier, because most endpoints are
  legitimate track-to-track joints.

Usage: find_dead_ends.py <board> [--render-w 1200 --render-h 1328 --margin-px 20 --scale-px-per-mm 12]
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

UM = 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--margin-px", type=float, default=20.0)
    ap.add_argument("--scale-px-per-mm", type=float, default=12.0)
    ap.add_argument("--tol", type=float, default=0.05)
    a = ap.parse_args()

    b = pcbnew.LoadBoard(a.board)
    pads = [(fp, p) for fp in b.GetFootprints() for p in fp.Pads()]
    vias = []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            vias.append((p.x / UM, p.y / UM, t.GetNetname()))
    tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]

    def pad_at(x, y, net):
        for fp, pd in pads:
            if pd.GetNetname() != net:
                continue
            bb = pd.GetBoundingBox()
            if (bb.GetLeft() / UM - a.tol <= x <= bb.GetRight() / UM + a.tol
                    and bb.GetTop() / UM - a.tol <= y <= bb.GetBottom() / UM + a.tol):
                return f"{fp.GetReference()}.{pd.GetNumber()}"
        return None

    # count endpoints per (rounded point, layer, net)
    ends = {}
    for t in tracks:
        for e in (t.GetStart(), t.GetEnd()):
            k = (round(e.x / UM, 2), round(e.y / UM, 2), t.GetLayer(), t.GetNetname())
            ends[k] = ends.get(k, 0) + 1

    dead = []
    for (x, y, lay, net), n in ends.items():
        if n > 1:
            continue
        if pad_at(x, y, net):
            continue
        if any(math.hypot(x - vx, y - vy) <= a.tol and vn == net for vx, vy, vn in vias):
            continue
        dead.append((x, y, lay, net))

    print(f"board: {a.board}")
    print(f"dead ends (1 segment, no pad, no via): {len(dead)}")
    S, M = a.scale_px_per_mm, a.margin_px

    def px(x, y):
        return (M + x * S, M + y * S)

    for (x, y, lay, net) in sorted(dead):
        ix, iy = px(x, y)
        print(f"  {net:16s} {pcbnew.LayerName(lay):6s} mm=({x:6.2f},{y:6.2f})  "
              f"px=({ix:6.0f},{iy:6.0f})")

    print("\n(image px assumed = margin + mm * scale; verify scale from the render's own geometry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
