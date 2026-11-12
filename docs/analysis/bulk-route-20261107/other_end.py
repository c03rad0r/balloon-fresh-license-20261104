#!/usr/bin/env python3
"""other_end.py -- does the FAR end of the blocked SPI1 nets have a legal via site?

The previous measurement found illegal via sites on the U3.3/U3.4 side only out to 1.275 mm,
then LEGAL at 1.725 mm. So one end of /SPI1_MISO is escapable. My router still fails, which
means the search is deficient, not the board.

This asks the complementary question: can the FAR end (U_C.3, U_C.4) also reach a via? If BOTH
ends can reach a via and the board has two nearly-empty inner layers, then a 4-layer router
should close these nets and my 2-layer router is the bottleneck.
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

for net, ref, num in (("/SPI1_MISO", "U_C", "3"), ("/SPI1_MOSI", "U_C", "4"),
                      ("/EN", "J_PROG", "3"), ("/SPI2_SCK", "U2", "12"),
                      ("/VSCAP", "C_CAP1", "1"), ("/F33_VSENSE", "R_MON1", "2")):
    ps = [q for q in W.pads if q["ref"] == ref and q["num"] == num and q["net"] == net]
    if not ps:
        print(f"{net} {ref}.{num}: not found on this net")
        continue
    p = ps[0]
    x0, y0, x1, y1 = p["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    layers = p["layers"] if p["layers"] else [R.F, R.B]
    print(f"\n{net}  far end {ref}.{num}  layers={layers} pth={p['pth']}")

    found = []
    for lay in layers:
        for ang in range(0, 360, 15):
            dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            free = 0.0
            for k in range(1, 80):
                L = k * 0.05
                ok, _ = W.seg_ok(lay, (cx, cy), (cx + dx * L, cy + dy * L), net, set())
                if not ok:
                    break
                free = L
            # is there a legal via anywhere along this corridor?
            for k in range(1, int(free / 0.05) + 1):
                L = k * 0.05
                vok, _ = W.via_ok(cx + dx * L, cy + dy * L, net)
                if vok:
                    found.append((round(L, 2), ang, lay))
                    break
    if found:
        found.sort()
        print(f"  legal via reachable: YES  nearest {found[0][0]} mm at {found[0][1]} deg "
              f"(layer {found[0][2]})")
        print(f"  {len(found)} legal directions")
    else:
        print("  legal via reachable: NO  -- this end cannot change layer at all")
