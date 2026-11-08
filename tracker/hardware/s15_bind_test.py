#!/usr/bin/env python3
"""s15_bind_test.py -- does lowering the clearance rule to 0.15 mm actually change the DRC?

The first attempt appended a 0.15 mm rule while the 0.200 mm rule was still present, and got
delta +0 for all three forms. That is uninformative: a looser rule sitting beside a tighter one may
simply never win, so "no effect" could mean "shadowed" rather than "does not bind".

This test REPLACES the S1 clearance value in place (0.20mm -> 0.15mm), which cannot be shadowed.
If the violation count does not drop, the rule is not the thing gating these pads and the JLCPCB
finding cannot be applied through .kicad_dru at all.

Two arms, to separate the cause:
  arm 1  clearance 0.200 -> 0.150, track width untouched
  arm 2  clearance 0.200 -> 0.090, track width untouched   (the fab floor, as a bound)
  arm 3  clearance 0.200 -> 0.150 AND track_width 0.200 -> 0.150

Also re-runs the UNMODIFIED board a second time, because kicad-cli DRC was measured 16 vs 20
violations on identical input in this session (multi-threaded / zone refill). Quoting a delta
without knowing the run-to-run spread would be exactly the mistake this campaign keeps making.
"""
import json
import os
import re
import shutil
import subprocess

LIVE = "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107"
WORK = "/tmp/s15b"
os.makedirs(WORK, exist_ok=True)
BASE = open(os.path.join(LIVE, "latest.kicad_dru")).read()


def counts(p):
    d = json.load(open(p))
    return len(d.get("violations", [])), len(d.get("unconnected_items", []))


def run(tag, dru_text, board_src=None):
    d = os.path.join(WORK, tag)
    os.makedirs(d, exist_ok=True)
    shutil.copy(board_src or os.path.join(LIVE, "latest.kicad_pcb"), os.path.join(d, "b.kicad_pcb"))
    shutil.copy(os.path.join(LIVE, "latest.kicad_pro"), os.path.join(d, "b.kicad_pro"))
    open(os.path.join(d, "b.kicad_dru"), "w").write(dru_text)
    out = os.path.join(d, "drc.json")
    r = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                        "--units", "mm", "--output", out, os.path.join(d, "b.kicad_pcb")],
                       capture_output=True, text=True, timeout=900)
    if not os.path.exists(out):
        return None, None, r.returncode
    v, u = counts(out)
    return v, u, r.returncode


print("=== baseline, run 3 times on the UNMODIFIED board (measures run-to-run spread):")
for i in range(3):
    v, u, rc = run(f"base{i}", BASE)
    print(f"  run {i+1}: violations={v} unconnected={u}")

print("\n=== arms (clearance replaced in place, cannot be shadowed):")
arm1 = BASE.replace("(constraint clearance (min 0.20mm))", "(constraint clearance (min 0.15mm))", 1)
arm2 = BASE.replace("(constraint clearance (min 0.20mm))", "(constraint clearance (min 0.09mm))", 1)
arm3 = arm1.replace("(constraint track_width (min 0.20mm))",
                    "(constraint track_width (min 0.15mm))", 1)

for tag, txt, label in (
        ("c150", arm1, "clearance 0.15"),
        ("c090", arm2, "clearance 0.09"),
        ("c150t150", arm3, "clearance 0.15 + track 0.15")):
    changed = txt != BASE
    v, u, rc = run(tag, txt)
    print(f"  {label:28s} text_changed={changed}  violations={v}  unconnected={u}")

print("\n=== did the substitution actually happen?")
for tag, txt, label in (("c150", arm1, "clearance 0.15"), ("c090", arm2, "clearance 0.09")):
    print(f"  {label}: 0.15mm present={'(min 0.15mm)' in txt}  "
          f"0.20mm clearance still present={'(constraint clearance (min 0.20mm))' in txt}")
