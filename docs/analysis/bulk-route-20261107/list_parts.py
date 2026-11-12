#!/usr/bin/env python3
"""list_parts.py -- every footprint on the board, with the fields a PCBA order needs.

Read-only. Used to build the partial-assembly split: what JLCPCB places, what is DNP and
hand-soldered, and what has no part number at all.
"""
import sys
from collections import defaultdict

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb"

b = pcbnew.LoadBoard(BOARD)
rows = []
for fp in b.GetFootprints():
    rows.append((
        fp.GetReference(),
        fp.GetFPID().GetLibItemName(),
        fp.GetValue(),
        "B" if fp.IsFlipped() else "F",
        fp.GetAttributes(),
    ))

print(f"board: {BOARD.split('/')[-1]}   footprints: {len(rows)}\n")
print(f"{'ref':12s} {'footprint':34s} {'value':30s} side")
print("-" * 88)
for ref, fpn, val, side, attrs in sorted(rows):
    print(f"{ref:12s} {fpn[:34]:34s} {val[:30]:30s} {side}")

# group by value so identical parts collapse, which is what an order needs
groups = defaultdict(list)
for ref, fpn, val, side, attrs in rows:
    groups[(val, fpn)].append(ref)

print(f"\n{len(groups)} distinct (value, footprint) groups:")
for (val, fpn), refs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(refs):2d}x {val[:40]:40s} {fpn[:30]:30s} {','.join(sorted(refs))}")
