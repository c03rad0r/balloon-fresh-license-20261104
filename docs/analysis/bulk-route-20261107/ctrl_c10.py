#!/usr/bin/env python3
"""CONTROL EXPERIMENT -- which tool is wrong about C10.1 (+3V3)?

Native DRC: 38 opens, and +3V3 contributes exactly ONE record (J_PROG.2 vs R_F1.1).
Shapely shape graph: C10.1 (+3V3) has NO same-net copper within 1.5 mm and is an island,
which would require a SECOND +3V3 record.

Decidable by one experiment: delete C10 from a THROWAWAY copy and re-run native DRC.
  opens 38 -> 37  => C10.1 was counted as unconnected; the graph is right and DRC merged
                     the pairing away (or reported it as one record for a 3-island net).
  opens 38 -> 38  => C10.1 was already part of +3V3; the graph is the wrong tool here
                     (most likely because GetEffectiveShape/TransformShapeToPolygon on an
                     SMD pad yields a shape on layers the pad cannot actually bridge).

Never touches the candidate board. Diagnostic only.
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

UM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))


def opens(path):
    out = os.path.join(HERE, "_ctrl", os.path.basename(path) + ".drc.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out, path], capture_output=True)
    d = json.load(open(out))
    recs = d["unconnected_items"]
    names = []
    for r in recs:
        names.append(sorted(i["description"] for i in r["items"]))
    return len(recs), names


def main(src):
    base = os.path.join(HERE, "_ctrl")
    os.makedirs(base, exist_ok=True)
    tgt = os.path.join(base, "no_c10.kicad_pcb")
    for ext in (".kicad_pro", ".kicad_dru"):
        shutil.copy(os.path.join(os.path.dirname(src), "board" + ext), base + "/no_c10" + ext)
    b = pcbnew.LoadBoard(src)
    fp = b.FindFootprintByReference("C10")
    print("C10 found:", fp is not None, "pads:",
          [(p.GetNumber(), p.GetNetname()) for p in fp.Pads()] if fp else None)
    b.Remove(fp)
    pcbnew.SaveBoard(tgt, b)
    n0, recs0 = opens(src)
    n1, recs1 = opens(tgt)
    print(f"opens with C10   = {n0}")
    print(f"opens without C10= {n1}")
    print(f"delta = {n1 - n0:+d}")
    gone = [r for r in recs0 if r not in recs1]
    new = [r for r in recs1 if r not in recs0]
    print("records that disappeared:")
    for r in gone:
        print("   ", r)
    print("records that appeared (must be none):")
    for r in new:
        print("   ", r)


if __name__ == "__main__":
    main(sys.argv[1])
