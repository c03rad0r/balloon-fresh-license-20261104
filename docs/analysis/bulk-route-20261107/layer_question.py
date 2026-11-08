#!/usr/bin/env python3
"""layer_question.py -- would In1/In2 help these six nets, and why does via_ok refuse?

Facts to establish before answering the operator:
  1. which copper layers does the board actually have, and how much copper is on each,
  2. for each of the six pads: which layers can a route legally START on,
  3. at the best via site, WHICH RULE refuses. If it is hole or edge clearance rather than a
     neighbour, then moving to an inner layer changes nothing, because the via is still needed.
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
b = W.b
UM = 1e6

print("=== COPPER LAYERS ON THIS BOARD")
for lid in b.GetEnabledLayers().CuStack():
    name = b.GetLayerName(lid)
    ntrk = sum(1 for t in b.GetTracks()
               if isinstance(t, __import__("pcbnew").PCB_TRACK)
               and not isinstance(t, __import__("pcbnew").PCB_VIA)
               and t.GetLayer() == lid)
    nz = 0
    for z in b.Zones():
        if z.GetLayerSet().Contains(lid):
            nz += 1
    print(f"  {name:8s} id={lid:2d}  tracks={ntrk:4d}  zones={nz}")
print(f"  vias={sum(1 for t in b.GetTracks() if isinstance(t, __import__('pcbnew').PCB_VIA))}"
      f"  (all through-vias: a via costs the same whichever inner layer it lands on)")

NAMES = {0: "F.Cu", 1: "B.Cu"}
SIX = [("/EN", "U1", "3"), ("/SPI2_SCK", "U1", "4"), ("/SPI1_MISO", "U3", "3"),
       ("/SPI1_MOSI", "U3", "4"), ("/VSCAP", "R_BAL1", "1"),
       ("/F33_VSENSE", "U1", "21")]

print("\n=== PAD LAYER ACCESS AND THE EXACT VIA REFUSAL")
for net, ref, num in SIX:
    p = [q for q in W.pads if q["ref"] == ref and q["num"] == num and q["net"] == net][0]
    x0, y0, x1, y1 = p["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lay = int(p["layers"][0]) if p["layers"] else R.F
    print(f"\n{net}  {ref}.{num}  layers={[NAMES.get(l, l) for l in p['layers']]} "
          f"pth={p['pth']} drill={p['drill']:.2f}")

    # best track corridor
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
    print(f"  best track corridor {free:.2f} mm at {ang} deg")

    # walk it and report the FIRST distinct refusal reason per rule family
    vr = R.VIA_D / 2
    seen = {}
    for k in range(1, int(free / 0.025) + 1):
        L = k * 0.025
        vx, vy = cx + dx * L, cy + dy * L
        ok, why = W.via_ok(vx, vy, net)
        if ok:
            seen["LEGAL"] = (round(L, 3), "")
            break
        fam = why.split()[0]
        if fam not in seen:
            seen[fam] = (round(L, 3), why)
    for fam, (L, why) in seen.items():
        print(f"    at {L:5.3f} mm: {fam:18s} {why}")
    if "LEGAL" not in seen:
        print("    -> no legal via on this corridor; a layer change is impossible HERE")
        print(f"    -> using In1/In2 would add a SECOND layer change, not remove this one")
