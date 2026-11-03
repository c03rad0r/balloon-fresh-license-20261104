#!/usr/bin/env python3
"""Why did a pad pair come back "no path"? Name the wall instead of guessing.

`route_scoped.py` reports "no path" for pairs its 14 mm corridor cannot close. That is not a verdict:
it could be the corridor, or a real wall. This probes the start and target pads directly — how many
of four 0.40 mm moves out of each pad are legal — so a failure is attributed to geometry rather than
to the search.

Usage: why_no_path.py <board> REF1.PAD1 REF2.PAD2 [...]
"""
import math
import sys

sys.path.insert(0, "docs/analysis/solar-8land-verify")
import pcbnew  # noqa: E402
import route_scoped as RS  # noqa: E402

UM = 1e6


def main():
    board_path = sys.argv[1]
    pairs = [a.split(":") for a in sys.argv[2:]]
    b = pcbnew.LoadBoard(board_path)
    w = RS.World(b)
    for spec in pairs:
        r1, n1 = spec[0].rsplit(".", 1)
        r2, n2 = spec[1].rsplit(".", 1)
        p1, p2 = w.pads.get((r1, n1)), w.pads.get((r2, n2))
        if not p1 or not p2:
            print(f"{r1}.{n1}->{r2}.{n2}: PAD MISSING")
            continue
        s, e = p1.GetPosition(), p2.GetPosition()
        d = math.hypot(s.x / UM - e.x / UM, s.y / UM - e.y / UM)
        code = b.FindNet(p1.GetNetname()).GetNetCode()
        l0 = 0 if p1.IsOnLayer(pcbnew.F_Cu) else 2

        def frees(pt, lay):
            n = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                x, y = pt.x / UM + dx * 0.4, pt.y / UM + dy * 0.4
                if not w.blocked(x, y, lay, code):
                    n += 1
            return n

        # both pads may sit on either layer; try the layer each is on
        l1 = 0 if p1.IsOnLayer(pcbnew.F_Cu) else 2
        l2 = 0 if p2.IsOnLayer(pcbnew.F_Cu) else 2
        print(f"{r1}.{n1}->{r2}.{n2}  dist={d:6.2f}mm  "
              f"start_free={frees(s, l1)}/4 (L{pcbnew.LayerName(l1)})  "
              f"target_free={frees(e, l2)}/4 (L{pcbnew.LayerName(l2)})  "
              f"{'BOTH BLOCKED' if frees(s, l1) == 0 and frees(e, l2) == 0 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
