#!/usr/bin/env python3
"""diag_discrim.py -- does any site near U1.3 have disc-reaching-pad but centre-outside?

The discrimination assertion returned >0 on clean code yet the poison still passed, which is
impossible if the assertion is measuring what I think. Print the buckets so the real numbers
are visible instead of inferred.
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(HERE, "..", "..", "..", "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

W = R.World(os.path.join(HERE, "candidate", "board.kicad_pcb"))
p = [q for q in W.pads if q["ref"] == "U1" and q["num"] == "3"][0]
x0, y0, x1, y1 = p["rect"]
cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2
print(f"U1.3 rect={[round(v,3) for v in p['rect']]}  VIA_D={R.VIA_D} r={R.VIA_D/2}")

n = 50
buckets = {"centre_in_pad": 0, "disc_reaches_centre_out": 0, "disc_misses": 0}
named = 0
for a in range(-n, n + 1):
    for b in range(-n, n + 1):
        cx, cy = cx0 + a * 0.05, cy0 + b * 0.05
        gap = R.seg_rect(cx, cy, cx, cy, p["rect"]) - R.VIA_D / 2
        cen = (x0 <= cx <= x1 and y0 <= cy <= y1)
        if cen:
            buckets["centre_in_pad"] += 1
        elif gap < -R.EPS:
            buckets["disc_reaches_centre_out"] += 1
            ok, why = W.via_ok(cx, cy, "/EN")
            if not ok and "via-in-pad" in why:
                named += 1
        else:
            buckets["disc_misses"] += 1
print(buckets)
print("of disc_reaches_centre_out, refused BY via-in-pad name:", named)

print("\nsample of disc-reaches/centre-out sites, with the refusal they actually get:")
shown = 0
for a in range(-n, n + 1):
    for b in range(-n, n + 1):
        cx, cy = cx0 + a * 0.05, cy0 + b * 0.05
        gap = R.seg_rect(cx, cy, cx, cy, p["rect"]) - R.VIA_D / 2
        if (x0 <= cx <= x1 and y0 <= cy <= y1) or gap >= -R.EPS:
            continue
        ok, why = W.via_ok(cx, cy, "/EN")
        print(f"  ({cx:.2f},{cy:.2f}) gap={gap:+.3f} ok={ok} why={why!r}")
        shown += 1
        if shown >= 12:
            break
    if shown >= 12:
        break
