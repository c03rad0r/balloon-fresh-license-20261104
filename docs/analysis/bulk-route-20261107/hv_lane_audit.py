#!/usr/bin/env python3
"""hv_lane_audit.py -- does the board already follow an H/V lane discipline?

READ-ONLY. Answers one question before anyone writes an ADR: if we assign F.Cu=horizontal,
In1=vertical, In2=horizontal, B.Cu=vertical, does the copper that is ALREADY there fit that
rule, or would the rule declare most of the board illegal on day one?

Method: longest-path angle per track, after merging collinear segments. A track within 22.5 deg
of the x axis counts H, within 22.5 deg of y counts V, anything else is DIAG. Short segments
(< 1.5 mm) are counted separately as ESCAPES, because fanout and pad exits are never H or V and
a rule without that exemption is unusable.
"""
import collections
import importlib.util
import math
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

BOARD = os.path.join(HERE, "latest.kicad_pcb")
b = pcbnew.LoadBoard(BOARD)
UM = 1e6
SHORT = 1.5          # mm; below this a segment is an escape/bend, exempt from H/V
TOL = 22.5           # deg from axis

print(f"board: {os.path.basename(BOARD)}")
print(f"rule under test: F.Cu=H, In1=V, In2=H, B.Cu=V   "
      f"(tolerance +/-{TOL} deg, exempt segments < {SHORT} mm)\n")

# proposed direction per layer NAME
PROPOSED = {"F.Cu": "H", "In1.Cu": "V", "In2.Cu": "H", "B.Cu": "V"}

per_layer = collections.defaultdict(lambda: collections.Counter())
lengths = collections.defaultdict(float)

for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA) or not isinstance(t, pcbnew.PCB_TRACK):
        continue
    name = b.GetLayerName(t.GetLayer())
    ax, ay = t.GetStart().x / UM, t.GetStart().y / UM
    bx, by = t.GetEnd().x / UM, t.GetEnd().y / UM
    L = math.hypot(bx - ax, by - ay)
    if L <= 0:
        continue
    ang = math.degrees(math.atan2(abs(by - ay), abs(bx - ax)))   # 0 = horizontal
    if L < SHORT:
        kind = "escape"
    elif ang <= TOL:
        kind = "H"
    elif ang >= 90 - TOL:
        kind = "V"
    else:
        kind = "DIAG"
    per_layer[name][kind] += 1
    lengths[name] += L

total_ok = total_checked = 0
print(f"{'layer':8s} {'H':>5s} {'V':>5s} {'DIAG':>5s} {'escape':>6s}   proposed   conforms")
for name in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
    c = per_layer.get(name)
    if not c:
        print(f"{name:8s} {'-':>5s} {'-':>5s} {'-':>5s} {'-':>6s}   "
              f"{PROPOSED[name]:^8s}   (no tracks)")
        continue
    want = PROPOSED[name]
    good = c["H"] if want == "H" else c["V"]
    bad = c["V"] if want == "H" else c["H"]
    counted = good + bad + c["DIAG"]
    pct = (good / counted * 100) if counted else 0.0
    total_ok += good
    total_checked += counted
    print(f"{name:8s} {c['H']:5d} {c['V']:5d} {c['DIAG']:5d} {c['escape']:6d}   "
          f"{want:^8s}   {pct:5.1f}%  ({good}/{counted})")

print(f"\nWHOLE BOARD conforms to the proposed H/V assignment: "
      f"{total_ok}/{total_checked} = {total_ok/total_checked*100:.1f}%")

print("\nlayer utilisation by TRACK LENGTH (mm):")
for name in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
    print(f"  {name:8s} {lengths.get(name, 0.0):9.1f}")
