#!/usr/bin/env python3
"""verify_via_in_pad.py -- the check kicad-cli CANNOT do.

KiCad has no via-in-pad rule. A via whose 0.600 mm disc sits 0.25 mm inside a same-net pad
produces **zero** DRC violations, so every downstream gate passes while the board carries a
defect that costs money at fab time (resin fill + plating over) and can wick solder off a
reflowing pad.

This measures the real geometry: for every via, the distance from its DISC (centre buffered by
via_d/2) to every pad polygon, and reports overlaps split by same-net / foreign-net.

  foreign-net overlap  = short or clearance breach (blocking; DRC would also catch it)
  same-net overlap     = via-in-pad (blocking for a no-resin-fill process; DRC is blind)

Exit 1 if any foreign-net overlap exists, or if --forbid-via-in-pad was given and any
same-net overlap exists. Prints per-item detail; nothing is aggregated away.

Usage:
    verify_via_in_pad.py BOARD [--forbid-via-in-pad] [--baseline OTHER_BOARD]
"""
from __future__ import annotations

import argparse
import sys

import pcbnew
from shapely.geometry import Point, Polygon

UM = 1e6


def pad_polys(board):
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            ps = pcbnew.SHAPE_POLY_SET()
            try:
                p.TransformShapeToPolygon(ps, pcbnew.F_Cu, 0, 100, pcbnew.ERROR_INSIDE)
            except Exception:
                continue
            for i in range(ps.OutlineCount()):
                pts = [(v.x / UM, v.y / UM) for v in ps.COutline(i).CPoints()]
                if len(pts) >= 3:
                    poly = Polygon(pts)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    out.append((f"{fp.GetReference()}.{p.GetNumber()}",
                                p.GetNetname() or "", poly))
    return out


def scan(path):
    b = pcbnew.LoadBoard(path)
    if b is None:
        raise SystemExit(f"REFUSED: cannot load {path}")
    pads = pad_polys(b)
    same, foreign, nv = [], [], 0
    for t in b.GetTracks():
        if not isinstance(t, pcbnew.PCB_VIA):
            continue
        nv += 1
        c = (t.GetPosition().x / UM, t.GetPosition().y / UM)
        r = t.GetWidth(pcbnew.F_Cu) / UM / 2
        disc = Point(c).buffer(r, quad_segs=24)
        for name, net, poly in pads:
            if not poly.intersects(disc):
                continue
            depth = r - Point(c).distance(poly)          # + = disc penetrates the pad
            item = (round(c[0], 3), round(c[1], 3), round(2 * r, 3), name, net,
                    round(depth, 4), t.GetNetname() or "")
            (same if net == (t.GetNetname() or "") else foreign).append(item)
    return {"path": path, "vias": nv, "same": same, "foreign": foreign}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--forbid-via-in-pad", action="store_true")
    ap.add_argument("--baseline", help="also scan this board, for delta reporting")
    a = ap.parse_args()

    r = scan(a.board)
    print(f"{a.board}: vias={r['vias']} same-net-via-in-pad={len(r['same'])} "
          f"FOREIGN-net={len(r['foreign'])}")
    for c in r["foreign"]:
        print(f"  FOREIGN via {c[0]},{c[1]} d={c[2]} in pad {c[3]} (pad net {c[4]!r}, "
              f"via net {c[6]!r}) depth={c[5]} mm")
    for c in r["same"]:
        print(f"  same-net via {c[0]},{c[1]} d={c[2]} overlaps {c[3]} depth={c[5]} mm")

    if a.baseline:
        rb = scan(a.baseline)
        print(f"\nbaseline {a.baseline}: vias={rb['vias']} "
              f"same-net={len(rb['same'])} FOREIGN={len(rb['foreign'])}")
        d = len(r["same"]) - len(rb["same"])
        print(f"delta same-net via-in-pad vs baseline: {d:+d}")

    bad = False
    if r["foreign"]:
        print(f"\nBLOCKING: {len(r['foreign'])} foreign-net via/pad overlap(s) -- "
              f"this is a short or clearance breach")
        bad = True
    if a.forbid_via_in_pad and r["same"]:
        print(f"\nBLOCKING: {len(r['same'])} same-net via-in-pad (constraint was "
              f"--forbid-via-in-pad)")
        bad = True
    print("\nVERDICT:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
