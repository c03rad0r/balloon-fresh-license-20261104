#!/usr/bin/env python3
"""diag_via_probe.py -- why did the poison test not fail?

The poison test reintroduced the shipped via-in-pad bug (point test instead of disc test) and
test_reject_via_disc_overlap_centre_outside still PASSED. That means its assertion cannot
observe the defect. This prints the actual per-site arithmetic so the reason is visible.
"""
import importlib.util
import os
import sys

HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tracker", "hardware")
spec = importlib.util.spec_from_file_location("R", os.path.join(HW, "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

W = R.World(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "candidate", "board.kicad_pcb"))
u13 = [p for p in W.pads if p["ref"] == "U1" and p["num"] == "3"][0]
x0, y0, x1, y1 = u13["rect"]
print(f"U1.3 rect = {[round(v, 3) for v in u13['rect']]}")
print(f"VIA_D={R.VIA_D}  radius={R.VIA_D/2}  CLEAR={R.CLEAR}  EPS={R.EPS}")
print()
for site in ((10.2, 36.7), (10.25, 36.43), (9.9, 36.43), (9.7, 36.43)):
    ok, why = W.via_ok(site[0], site[1], "/EN")
    gap = R.seg_rect(site[0], site[1], site[0], site[1], u13["rect"]) - R.VIA_D / 2
    print(f"site {site}: via_ok={ok:<5} gap={gap:+.3f}  why={why!r}")
print()
print("Sweep the region the test sweeps, count sites whose disc overlaps U1.3 AND via_ok:")
overlap_accepted = 0
for a in range(-50, 51):
    for b in range(-50, 51):
        cx, cy = (x0 + x1) / 2 + a * 0.05, (y0 + y1) / 2 + b * 0.05
        ok, _ = W.via_ok(cx, cy, "/EN")
        if not ok:
            continue
        gap = R.seg_rect(cx, cy, cx, cy, u13["rect"]) - R.VIA_D / 2
        if gap < -R.EPS:
            overlap_accepted += 1
print(f"  overlap-accepted sites = {overlap_accepted}")
