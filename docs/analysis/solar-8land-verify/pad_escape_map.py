#!/usr/bin/env python3
"""Is a pad BOXED, or just tight? Sweep radii and 16 directions before declaring it unroutable.

`why_no_path.py` tests four moves at 0.40 mm. A pad can be surrounded at 0.40 mm and still be
reachable through a 0.21 mm gap, so a 0/4 result is not proof of a wall — it is proof that this
probe at this radius found none. This sweeps the radius so the answer is a number, not a shrug.

Usage: pad_escape_map.py <board> REF.PAD [REF.PAD ...]
"""
import math
import sys

sys.path.insert(0, "docs/analysis/solar-8land-verify")
import pcbnew  # noqa: E402
import route_scoped as RS  # noqa: E402

UM = 1e6


def main():
    b = pcbnew.LoadBoard(sys.argv[1])
    w = RS.World(b)
    for spec in sys.argv[2:]:
        ref, num = spec.rsplit(".", 1)
        pad = w.pads.get((ref, num))
        if not pad:
            print(f"{spec}: PAD MISSING")
            continue
        code = b.FindNet(pad.GetNetname()).GetNetCode()
        lay = 0 if pad.IsOnLayer(pcbnew.F_Cu) else 2
        p = pad.GetPosition()
        cx, cy = p.x / UM, p.y / UM
        print(f"\n=== {spec}  net={pad.GetNetname()}  layer={pcbnew.LayerName(lay)}  at ({cx:.2f},{cy:.2f})")
        for radius in (0.30, 0.40, 0.60, 1.00, 1.50, 2.00, 3.00):
            free = []
            for k in range(16):
                ang = 2 * math.pi * k / 16
                x, y = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
                if not w.blocked(x, y, lay, code):
                    free.append(round(math.degrees(ang)))
            print(f"  r={radius:.2f}mm  free={len(free):2d}/16  {free if free else 'ALL BLOCKED'}")
        # what is blocking at the first radius?
        r = 0.40
        r0 = RS.TRACK_W / 2.0 + RS.CLEAR
        blockers = []
        for (x1, y1, x2, y2, rw, l, c) in w.segs:
            if c == code:
                continue
            for k in range(16):
                ang = 2 * math.pi * k / 16
                x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
                if RS.seg_pt(x, y, x1, y1, x2, y2) < r0 + rw:
                    blockers.append((pcbnew.LayerName(l), b.FindNet(c).GetNetname()
                                     if b.FindNet(c) else c, round(r, 2)))
                    break
        seen = []
        for bl in blockers:
            if bl not in seen:
                seen.append(bl)
        if seen:
            print("  blocking at r=0.40:", seen[:6])
    return 0


if __name__ == "__main__":
    sys.exit(main())
