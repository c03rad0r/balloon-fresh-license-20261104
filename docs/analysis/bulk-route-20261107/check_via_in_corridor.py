#!/usr/bin/env python3
"""check_via_in_corridor.py -- does a legal via exist INSIDE the free track corridor?

The drawing revealed a contradiction I have to settle: /EN has a 1.10 mm free TRACK corridor
east, and a 0.60 mm via only needs its centre 0.500 mm from foreign copper. Those numbers
suggest a via should fit. reachability.py says the net is UNREACHABLE.

This walks the corridor and reports, at each distance, whether a via is legal there and why not.
The distinction that matters: a TRACK corridor is clear ALONG A LINE, but a via needs 0.500 mm
clear in EVERY direction around its centre. A narrow slot admits a 0.2 mm track and refuses a
0.6 mm via.
"""
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

W = R.World(os.path.join(HERE, "latest.kicad_pcb"))

for net, ref, num in (("/EN", "U1", "3"), ("/SPI2_SCK", "U1", "4"),
                      ("/VSCAP", "R_BAL1", "1")):
    p = [q for q in W.pads if q["ref"] == ref and q["num"] == num and q["net"] == net][0]
    x0, y0, x1, y1 = p["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lay = int(p["layers"][0]) if p["layers"] else R.F
    print(f"\n=== {net} {ref}.{num}  centre ({cx:.3f},{cy:.3f})")

    # best TRACK corridor direction
    best = (0.0, 0)
    for ang in range(0, 360, 15):
        dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        free = 0.0
        for k in range(1, 100):
            L = k * 0.05
            ok, _ = W.seg_ok(lay, (cx, cy), (cx + dx * L, cy + dy * L), net, set())
            if not ok:
                break
            free = L
        if free > best[0]:
            best = (free, ang)
    free, ang = best
    dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    print(f"  best TRACK corridor: {free:.3f} mm at {ang} deg")

    # walk that corridor; at each point ask whether a VIA is legal
    legal = []
    first_blocker = None
    for k in range(1, int(free / 0.025) + 1):
        L = k * 0.025
        vx, vy = cx + dx * L, cy + dy * L
        ok, why = W.via_ok(vx, vy, net)
        if ok:
            legal.append((round(L, 3), why))
        elif first_blocker is None:
            first_blocker = (round(L, 3), why)
    print(f"  legal VIA sites along that corridor: {len(legal)}")
    if legal:
        print(f"    first at {legal[0][0]} mm; a via CAN sit there")
    else:
        print(f"    NONE. first refusal at {first_blocker[0]} mm: {first_blocker[1]}")
        print("    -> a 0.2 mm track fits, a 0.6 mm via does not: the slot is narrower than a via")
