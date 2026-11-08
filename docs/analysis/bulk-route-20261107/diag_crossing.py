#!/usr/bin/env python3
"""Resolve: check_lane_crossing.py reports 3 B.Cu crossings / 4 touches with gaps of
-0.179 mm on /GNSS_PPS, while native kicad-cli DRC reports ZERO shorting_items and ZERO
clearance violations on the SAME board.

AGENTS.md 14: "When a custom gate and kicad-cli DISAGREE, that disagreement is a bug in the
custom gate until proven otherwise" -- it has been 4+ times (B34/B37/B38/B40/B42).

This measures the actual KiCad shapes for the exact track pairs named, on the exact layer,
and prints the true distance. It also prints each item's layer and net so a layer-mapping
bug is visible.
"""
import sys

import pcbnew

UM = 1e6


def main(path):
    b = pcbnew.LoadBoard(path)
    print("=== every /GNSS_PPS track/via, with true layer and endpoints ===")
    for t in b.GetTracks():
        if t.GetNetname() != "/GNSS_PPS":
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            print(f"  VIA ({p.x/UM:.3f},{p.y/UM:.3f}) dia={t.GetWidth(pcbnew.F_Cu)/UM:.3f}")
        else:
            a, c = t.GetStart(), t.GetEnd()
            print(f"  {pcbnew.LayerName(t.GetLayer()):6s} "
                  f"({a.x/UM:.3f},{a.y/UM:.3f})->({c.x/UM:.3f},{c.y/UM:.3f}) "
                  f"w={t.GetWidth()/UM:.3f}")

    for net in ("/E28_RESET_N", "/SPI1_SCK", "/E28_DIO2"):
        print(f"\n=== exact distance /GNSS_PPS vs {net} (KiCad shapes, per shared layer) ===")
        mine, other = [], []
        for t in b.GetTracks():
            if t.GetNetname() == "/GNSS_PPS":
                mine.append(t)
            elif t.GetNetname() == net:
                other.append(t)
        worst = None
        for m in mine:
            mlay = set(m.GetLayerSet().CuStack())
            for o in other:
                olay = set(o.GetLayerSet().CuStack())
                shared = [l for l in (mlay & olay) if b.IsLayerEnabled(l)]
                if not shared:
                    continue
                for lid in shared:
                    sm = m.GetEffectiveShape(lid)
                    so = o.GetEffectiveShape(lid)
                    # Distance() takes a VECTOR2I, so do it via collision at increasing radius
                    # instead: report whether the shapes collide and by how much they overlap
                    # using bounding boxes as an upper bound of proximity.
                    hit = sm.Collide(so, 0)
                    bm, bo = sm.BBox(), so.BBox()
                    gap_x = max(bm.GetX() - (bo.GetX() + bo.GetWidth()),
                                bo.GetX() - (bm.GetX() + bm.GetWidth()))
                    gap_y = max(bm.GetY() - (bo.GetY() + bo.GetHeight()),
                                bo.GetY() - (bm.GetY() + bm.GetHeight()))
                    bbgap = max(gap_x, gap_y) / UM
                    print(f"  {pcbnew.LayerName(lid):6s} collide(0)={hit} "
                          f"bbox_gap={bbgap:+.3f} "
                          f"m=({m.GetStart().x/UM:.1f},{m.GetStart().y/UM:.1f})"
                          f"-({m.GetEnd().x/UM:.1f},{m.GetEnd().y/UM:.1f}) "
                          f"o=({o.GetStart().x/UM:.1f},{o.GetStart().y/UM:.1f})"
                          f"-({o.GetEnd().x/UM:.1f},{o.GetEnd().y/UM:.1f})")
                    if worst is None or bbgap < worst:
                        worst = bbgap
        if worst is not None:
            print(f"  -> worst bbox gap {worst:+.3f} mm")


if __name__ == "__main__":
    main(sys.argv[1])
