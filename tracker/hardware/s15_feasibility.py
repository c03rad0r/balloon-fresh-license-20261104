#!/usr/bin/env python3
"""s15_feasibility.py -- is a pad-scoped 0.150 mm clearance rule EXPRESSIBLE in KiCad 9?

The JLCPCB finding says the four trapped pads only fail against S1's self-imposed 0.200 mm, and
would clear at 0.150 mm (still 1.7x the fab's 0.09 mm). Before proposing that to the operator, the
rule has to be proved to BIND -- not merely to parse.

ADR-142 already established a related negative: no .kicad_dru form reaches a TRACK crossing a
socket cavity, not even a conditionless edge_clearance waiver. The rule engine, not the syntax, was
the limit. So "0.15 mm scoped to four pads" cannot be assumed to work.

METHOD. Three candidate forms, each applied to a copy of the live board, then kicad-cli DRC. A form
that binds on the four pads will REDUCE the relevant violations; a form that does not bind changes
nothing. Comparing against the live-board baseline (16 violations) makes a no-op visible.

  A  conditionless 0.15 mm clearance      -- widest possible scope; if this does not move anything,
                                             no narrower form can
  B  net-scoped: A.NetName == '/EN'       -- scoped to one of the four nets
  C  pad-vs-track type scope              -- scoped to pad->track pairs only

Nothing here modifies the live board. All work is on /tmp copies.
"""
import json
import os
import shutil
import subprocess
import sys

LIVE = "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107"
WORK = "/tmp/s15"
BASE_DRU = open(os.path.join(LIVE, "latest.kicad_dru")).read()

FORMS = {
    "A_no_condition":
        '(rule "S15 conditionless 0.15" (constraint clearance (min 0.15mm)))',
    "B_net_scope":
        '(rule "S15 EN net 0.15" (constraint clearance (min 0.15mm))\n'
        '  (condition "A.NetName == \'/EN\'"))',
    "C_pad_track":
        '(rule "S15 pad to track 0.15" (constraint clearance (min 0.15mm))\n'
        '  (condition "A.Type == \'Pad\' && B.Type == \'Track\'"))',
}


def drc(board, out):
    r = subprocess.run(
        ["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
         "--units", "mm", "--output", out, board],
        capture_output=True, text=True, timeout=900)
    txt = (r.stdout or "") + (r.stderr or "")
    n_v = n_u = None
    for line in txt.splitlines():
        if "violations" in line.lower() and "Found" in line:
            n_v = line
        if "unconnected" in line.lower() and "Found" in line:
            n_u = line
    return n_v, n_u, r.returncode


def counts(path):
    d = json.load(open(path))
    return len(d.get("violations", [])), len(d.get("unconnected_items", []))


print("=== baseline (live board, live dru):")
shutil.copy(os.path.join(LIVE, "latest.kicad_pcb"), os.path.join(WORK, "base.kicad_pcb"))
shutil.copy(os.path.join(LIVE, "latest.kicad_pro"), os.path.join(WORK, "base.kicad_pro"))
shutil.copy(os.path.join(LIVE, "latest.kicad_dru"), os.path.join(WORK, "base.kicad_dru"))
_v, _u, _rc = drc(os.path.join(WORK, "base.kicad_pcb"), os.path.join(WORK, "base.json"))
bv, bu = counts(os.path.join(WORK, "base.json"))
print(f"  {_v} / {_u}   -> violations={bv} unconnected={bu}")

for name, rule in FORMS.items():
    bd = os.path.join(WORK, name)
    os.makedirs(bd, exist_ok=True)
    shutil.copy(os.path.join(LIVE, "latest.kicad_pcb"), os.path.join(bd, "b.kicad_pcb"))
    shutil.copy(os.path.join(LIVE, "latest.kicad_pro"), os.path.join(bd, "b.kicad_pro"))
    open(os.path.join(bd, "b.kicad_dru"), "w").write(BASE_DRU + "\n\n" + rule + "\n")
    v, u, rc = drc(os.path.join(bd, "b.kicad_pcb"), os.path.join(bd, "drc.json"))
    jp = os.path.join(bd, "drc.json")
    if not os.path.exists(jp):
        print(f"\n{name}: DRC produced no JSON (rc={rc}) -- form may be rejected outright")
        print(f"  {v} / {u}")
        continue
    try:
        nv, nu = counts(jp)
    except Exception as e:
        print(f"\n{name}: unreadable JSON ({e})")
        continue
    delta = nv - bv
    verdict = ("BINDS (violations changed)" if delta < 0
               else "NO EFFECT -- does not bind")
    print(f"\n{name}: violations={nv} (delta {delta:+d})  unconnected={nu}   {verdict}")
