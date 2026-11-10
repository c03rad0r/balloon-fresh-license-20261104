#!/usr/bin/env python3
"""v11 corner reservation: find a top-side site for each D_BP diode.

ADR-146 moves D_BP1..4 to the top face. On v10 they are B.Cu-only, so each needs both
connections re-made on F.Cu. This searches the whole top face, not a window around the v10
site, because v11 is a re-layout and D_BP3 had NO viable site near its v10 position (its two
nets occupy opposite halves of the board).

Usage:  /usr/bin/python3 tracker/hardware/v11_diode_sites.py [board]
"""
import sys
import math
from collections import defaultdict

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "docs/analysis/bulk-route-20261107/work.kicad_pcb"
PAD_SEP = 4.0      # SMA: pads are exactly 4.00 mm apart
MAX_REACH = 6.0    # acceptable pad-to-nearest-same-net-copper
FP_CLEAR = 3.0     # keep clear of existing footprint centres
EDGE_KEEP = 3.0    # stay off the board edge


def main():
    b = pcbnew.LoadBoard(BOARD)
    bb = b.GetBoardEdgesBoundingBox()
    W, H = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())

    fcu = defaultdict(list)
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != pcbnew.F_Cu:
            continue
        for pt in (t.GetStart(), t.GetEnd()):
            fcu[t.GetNetname()].append((pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)))

    occupied = []
    for f in b.GetFootprints():
        if f.GetReference().startswith("D_BP"):
            continue
        p = f.GetPosition()
        occupied.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), f.GetReference()))

    def nearest(net, x, y):
        pts = fcu.get(net)
        if not pts:
            return None
        return min(math.hypot(a - x, c - y) for a, c in pts)

    def is_free(x, y):
        return all(math.hypot(x - ox, y - oy) > FP_CLEAR for ox, oy, _ in occupied)

    pairs = [
        ("D_BP1", "/W1_SOLAR_P", "/W1_SOLAR_N"),
        ("D_BP2", "/W1_SOLAR_N", "/W2_SOLAR_N"),
        ("D_BP3", "/W2_SOLAR_N", "/W3_SOLAR_N"),
        ("D_BP4", "/W3_SOLAR_N", "GND"),
    ]

    print(f"board {W:.1f} x {H:.1f} mm   pad separation {PAD_SEP} mm   reach limit {MAX_REACH} mm")
    print()
    for ref, n1, n2 in pairs:
        best = []
        xi = int(EDGE_KEEP * 10)
        while xi <= int((W - EDGE_KEEP) * 10):
            yi = int(EDGE_KEEP * 10)
            while yi <= int((H - EDGE_KEEP) * 10):
                x, y = xi / 10.0, yi / 10.0
                if is_free(x, y):
                    for rot in (0, 90, 180, 270):
                        th = math.radians(rot)
                        worst = 0.0
                        ok = True
                        for net, sgn in ((n1, -1), (n2, 1)):
                            px = x + sgn * PAD_SEP * math.cos(th)
                            py = y + sgn * PAD_SEP * math.sin(th)
                            d = nearest(net, px, py)
                            if d is None:
                                ok = False
                                break
                            worst = max(worst, d)
                        if ok and worst <= MAX_REACH:
                            best.append((worst, x, y, rot))
                yi += 5
            xi += 5
        best.sort()
        print(f"{ref}  ({n1} / {n2})   {len(best)} site(s) within {MAX_REACH} mm")
        for worst, x, y, rot in best[:3]:
            print(f"    ({x:5.1f}, {y:5.1f}) rot={rot:>3}   worst pad-to-copper {worst:.2f} mm")
        if not best:
            print("    NONE — needs new copper on the top face either way")
        print()


if __name__ == "__main__":
    main()
