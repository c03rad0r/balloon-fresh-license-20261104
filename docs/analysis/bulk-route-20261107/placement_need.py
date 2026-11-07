#!/usr/bin/env python3
"""placement_need.py -- how far would each blocked pad have to move?

READ-ONLY. This moves nothing and writes no board. It answers one question per blocked net:
given the board's own rules, what is the SMALLEST displacement of the blocking neighbour (or of
the pad itself) that would create a legal escape?

The six blocked nets are all the same shape: a 0.30 mm pad in a fine-pitch field, needing its
centre 0.30 mm from foreign copper for a 0.20 mm track. For each, this reports:
  - the pad's own free corridor in 8 directions,
  - the neighbouring item that blocks each direction and how much overlap there is,
  - the shortfall: (needed clearance) - (available corridor),
  - the minimum uniform nudge that would clear the worst direction.

Output is a proposal table for review, not a decision applied to copper.
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

BOARD = os.path.join(HERE, "latest.kicad_pcb")

# The six free-space-UNREACHABLE records, from reachability.py.
BLOCKED = [
    ("/EN", "U1", "3"),
    ("/SPI2_SCK", "U1", "4"),
    ("/SPI1_MISO", "U3", "3"),
    ("/SPI1_MOSI", "U3", "4"),
    ("/VSCAP", "R_BAL1", "1"),
    ("/F33_VSENSE", "U1", "21"),
]

W = R.World(BOARD)
NEEDED = R.CLEAR + R.TRACK_W / 2          # 0.30 mm for a 0.20 track at 0.20 clearance
VIA_NEEDED = R.CLEAR + R.VIA_D / 2        # 0.50 mm for a 0.60/0.30 via

print(f"rules: track needs {NEEDED:.3f} mm centre-to-copper, "
      f"via needs {VIA_NEEDED:.3f} mm")
print(f"board: {os.path.basename(BOARD)}   pads={len(W.pads)}\n")

for net, ref, num in BLOCKED:
    ps = [p for p in W.pads if p["ref"] == ref and p["num"] == num and p["net"] == net]
    if not ps:
        print(f"{net} {ref}.{num}: NOT FOUND on this board\n")
        continue
    p = ps[0]
    x0, y0, x1, y1 = p["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = x1 - x0, y1 - y0
    lay = int(p["layers"][0]) if p["layers"] else R.F
    print(f"{net}  {ref}.{num}  pad {w:.2f}x{h:.2f} mm  centre ({cx:.3f},{cy:.3f})  "
          f"layers={p['layers']} pth={p['pth']}")

    worst = None
    for ang in (0, 45, 90, 135, 180, 225, 270, 315):
        dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        block = None
        for k in range(1, 80):
            L = k * 0.025
            ok, why = W.seg_ok(lay, (cx, cy), (cx + dx * L, cy + dy * L), net, set())
            if not ok:
                block = (round(L, 3), why)
                break
        avail = block[0] if block else 3.0
        short = max(0.0, NEEDED - avail)
        who = block[1] if block else "clear"
        print(f"   {ang:3d}°  free {avail:5.2f} mm  short {short:5.2f}  {who}")
        if worst is None or short > worst[1]:
            worst = (ang, short, who)
    print(f"   -> worst: {worst[0]}° short by {worst[1]:.3f} mm ({worst[2]})")
    print(f"   -> via escape would need {VIA_NEEDED:.3f} mm; worst free corridor is "
          f"{max(0.0, NEEDED - worst[1]):.3f} mm\n")
