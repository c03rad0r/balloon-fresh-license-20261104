#!/usr/bin/env python3
"""DECISIVE control: is C10.1 (+3V3, SMD F.Cu) actually connected, or is a checker wrong?

Two previous probes disagreed:
  * native kicad-cli DRC  -> +3V3 contributes exactly ONE record (J_PROG.2 vs R_F1.1), and
                             no record anywhere names C10.
  * shapely shape graph   -> C10.1 has no same-net copper within 0.25 mm; an isolated island
                             would need its own record.
  * removing C10 entirely -> still 38 opens (delta 0), which is ambiguous because the net
                             loses a pad AND an island at the same time.

This file runs two throwaway variants and compares against the untouched baseline:
  V1  move C10 to the far corner  -> if opens 38 -> 39, C10.1 WAS connected
  V2  delete the +3V3 In2.Cu zone -> tests the only same-net inner-layer copper near it

Nothing here writes to the candidate board; every variant is a copy under `_ctrl/`.
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

UM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))
CTRL = os.path.join(HERE, "_ctrl")


def run_drc(path):
    out = path + ".drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out, path], capture_output=True)
    d = json.load(open(out))
    return d


def summary(d):
    recs = [[sorted(i["description"] for i in r["items"])] for r in d["unconnected_items"]]
    return len(d["unconnected_items"]), recs


def variant(src, name, mutate):
    os.makedirs(CTRL, exist_ok=True)
    dst = os.path.join(CTRL, name + ".kicad_pcb")
    for ext in (".kicad_pro", ".kicad_dru"):
        shutil.copy(os.path.join(os.path.dirname(src), "board" + ext),
                    os.path.join(CTRL, name + ext))
    b = pcbnew.LoadBoard(src)
    mutate(b)
    pcbnew.SaveBoard(dst, b)
    d = run_drc(dst)
    n, recs = summary(d)
    return n, recs


def main(src):
    d0 = run_drc(src)
    n0, recs0 = summary(d0)
    print(f"baseline opens = {n0}")
    print("baseline +3V3 records:",
          [r for r in recs0 if any("+3V3" in x for x in r[0])])

    def move(b):
        fp = b.FindFootprintByReference("C10")
        fp.SetPosition(pcbnew.VECTOR2I(int(60.0 * UM), int(30.0 * UM)))
    n1, recs1 = variant(src, "c10_moved", move)
    print(f"\nV1 C10 moved to (60,30): opens = {n1} (delta {n1-n0:+d})")
    print("   +3V3 records:",
          [r for r in recs1 if any("+3V3" in x for x in r[0])])
    print("   C10 records:",
          [r for r in recs1 if any("C10" in x for x in r[0])])

    def drop_vscap_and_3v3_inner(b):
        for z in list(b.Zones()):
            if z.GetNetname() == "+3V3":
                b.Remove(z)
    n2, recs2 = variant(src, "no_3v3_zones", drop_vscap_and_3v3_inner)
    print(f"\nV2 all +3V3 zones removed: opens = {n2} (delta {n2-n0:+d})")
    print("   +3V3 records:",
          [r for r in recs2 if any("+3V3" in x for x in r[0])])

    print("\nVERDICT")
    if n1 > n0:
        print(f"  C10.1 WAS connected: isolating it adds {n1-n0} open(s). "
              "The shapely graph (which said 'island') is the wrong tool for this pad; "
              "native DRC is authoritative.")
    else:
        print("  C10.1 was NOT adding to the open count either way -- the graph and DRC "
              "still disagree; reported as an unresolved checker discrepancy, not acted on.")


if __name__ == "__main__":
    main(sys.argv[1])
