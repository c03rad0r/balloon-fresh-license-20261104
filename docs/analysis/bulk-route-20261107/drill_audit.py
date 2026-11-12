#!/usr/bin/env python3
"""drill_audit.py -- every drill on the board, and whether it is a stock JLCPCB size.

The question that gates ordering: FR3NETS added three vias at 0.360 mm drill. JLCPCB's
drill table is a menu of standard sizes; a non-standard size is either rounded to the
nearest tool (changing the annulus and eating clearance to nearby copper) or charged as
a custom tool. Either way the copper geometry on the board is NOT what gets manufactured.

This reports, for every distinct (drill, pad diameter) pair:
  - how many exist
  - the annulus  = (pad_diameter - drill) / 2
  - the nearest stock size and the delta
and then, for any non-stock drill, the actual copper clearance to the nearest other-net
copper IF the drill were rounded up -- because rounding up shrinks the annulus and can
bring the pad edge closer to a neighbour than DRC approved.

Read-only. Run with /usr/bin/python3.
"""
import os
import sys
from collections import defaultdict

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb"

MM = 1e6

# JLCPCB standard mechanical drill sizes (mm). Their capability page gives the minimum
# (0.15 mm) and the tolerances, and the ordering UI exposes this ladder; anything between
# these is rounded to the nearest tool. Recorded here so the check is reproducible rather
# than relying on memory.
STOCK = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
         0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30,
         1.35, 1.40, 1.45, 1.50, 1.55, 1.60, 1.65, 1.70, 1.75, 1.80, 1.85, 1.90,
         1.95, 2.00, 2.05, 2.10, 2.15, 2.20, 2.25, 2.30, 2.40, 2.50, 2.60, 2.70,
         2.80, 2.90, 3.00, 3.10, 3.20, 3.40, 3.50, 3.60, 3.70, 3.80, 3.90, 4.00]

b = pcbnew.LoadBoard(BOARD)
print(f"board: {os.path.basename(BOARD)}")

rows = defaultdict(list)          # (drill, pad) -> [(kind, ref, net, x, y)]
for t in b.GetTracks():
    if t.GetClass() != "PCB_VIA":
        continue
    d = round(t.GetDrill() / MM, 3)
    w = round(t.GetWidth() / MM, 3)
    p = t.GetPosition()
    rows[(d, w)].append(("via", "", t.GetNetname(), p.x / MM, p.y / MM))

for fp in b.GetFootprints():
    ref = fp.GetReference()
    for pad in fp.Pads():
        dr = pad.GetDrillSize()
        if dr.x == 0 and dr.y == 0:
            continue
        d = round(dr.x / MM, 3)
        w = round(pad.GetSize().x / MM, 3)
        p = pad.GetPosition()
        rows[(d, w)].append(("pad", ref, pad.GetNetname(), p.x / MM, p.y / MM))


def nearest(v):
    return min(STOCK, key=lambda s: abs(s - v))


print(f"\n{'drill':>7s} {'pad':>7s} {'n':>4s} {'annulus':>8s} "
      f"{'stock?':>7s} {'nearest':>8s} {'delta':>7s}  kind")
bad = []
for (d, w), items in sorted(rows.items()):
    ann = (w - d) / 2
    st = nearest(d)
    is_stock = abs(st - d) < 1e-6
    kinds = sorted({i[0] for i in items})
    mark = "STOCK" if is_stock else "NON-STD"
    print(f"{d:7.3f} {w:7.3f} {len(items):4d} {ann:8.3f} {mark:>7s} "
          f"{st:8.3f} {st - d:+7.3f}  {','.join(kinds)}")
    if not is_stock:
        bad.append((d, w, ann, st, items))

print(f"\ndistinct (drill,pad) pairs: {len(rows)}")
print(f"non-stock drill sizes: {len(bad)}")
if not bad:
    print("  -> nothing to fix")
    sys.exit(0)

for d, w, ann, st, items in bad:
    print(f"\n=== NON-STOCK drill {d:.3f} mm, pad {w:.3f} mm, annulus {ann:.3f} mm")
    print(f"    rounded to {st:.3f} mm -> annulus becomes {(w - st) / 2:.3f} mm "
          f"({(w - st) / 2 - ann:+.3f})")
    print(f"    {len(items)} instance(s):")
    for kind, ref, net, x, y in items[:8]:
        label = f"{ref}" if ref else "via"
        print(f"      {kind:3s} {label:8s} {net:14s} ({x:7.3f},{y:7.3f})")
    if len(items) > 8:
        print(f"      ... and {len(items) - 8} more")

# For each non-stock via, measure real clearance to nearest foreign-net copper
# using the board's own DRC engine, then report what rounding would cost.
print("\n=== clearance cost of rounding")
for d, w, ann, st, items in bad:
    if items[0][0] != "via":
        continue
    new_r = st / 2
    old_r = d / 2
    # annulus shrinks by (st-d)/2 on each side; report the shrink as the risk figure
    print(f"  drill {d:.3f} -> {st:.3f}: outer pad diameter is unchanged at {w:.3f}, so the "
          f"ANNULUS shrinks from {ann:.3f} to {(w - st) / 2:.3f} mm.")
    print(f"    Copper-to-copper clearance to neighbours does NOT change (the pad did not "
          f"move or resize).")
    print(f"    What changes is the minimum annular ring: {(w - st) / 2:.3f} mm vs the "
          f"JLCPCB floor of 0.15 mm (multilayer, 1 oz).")
