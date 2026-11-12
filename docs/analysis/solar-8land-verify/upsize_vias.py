#!/usr/bin/env python3
"""Upsize vias to the frozen JLCPCB S1 rules, then let DRC decide.

Measured 2026-11-03 on hub_board_v10_lora1280_7of9 (candidate): 41 of 41 vias fail the frozen
rules -- 35 below the 0.60 mm via_diameter minimum and 22 below the 0.30 mm hole_size minimum.
Those numbers are invisible under the project's global rules (0.50 / 0.20), which is why earlier
DRC runs showed 40 violations and none of them said "via".

WHAT THIS DOES: sets every via to at least 0.30 mm drill / 0.60 mm pad, refills, runs DRC with the
frozen .kicad_dru actually loaded (same-stem), and reports the trade. Enlarging pads costs
clearance, so the honest question is not "did the via violations clear" but "what did the extra
0.05 mm of copper radius collide with". Not fab approval: a candidate and a measurement.

Usage: upsize_vias.py <src.kicad_pcb> <out.kicad_pcb> --dru <frozen.kicad_dru> [--report dir]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import pcbnew

UM = 1_000_000.0
MIN_DRILL, MIN_PAD = 0.30, 0.60


def drc(pcb, dru, out_json):
    stem = os.path.splitext(pcb)[0]
    shutil.copyfile(dru, stem + ".kicad_dru")
    r = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                        "-o", out_json, pcb], capture_output=True, text=True)
    if not os.path.exists(out_json):
        print("DRC FAILED:", r.stderr[-400:])
        return None
    d = json.load(open(out_json))
    from collections import Counter
    return (Counter(v["type"] for v in d.get("violations", [])),
            len(d.get("unconnected_items", [])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--dru", required=True)
    ap.add_argument("--report", default=".")
    a = ap.parse_args()

    before = drc(a.src, a.dru, os.path.join(a.report, "drc-before.json"))
    b = pcbnew.LoadBoard(a.src)

    changed, already = [], []
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            continue
        d, w = round(t.GetDrillValue() / UM, 3), round(t.GetWidth(pcbnew.B_Cu) / UM, 3)
        nd, nw = max(d, MIN_DRILL), max(w, MIN_PAD)
        if (nd, nw) != (d, w):
            t.SetDrill(int(nd * UM))
            t.SetWidth(int(nw * UM))
            changed.append((round(t.GetPosition().x / UM, 2), round(t.GetPosition().y / UM, 2),
                            d, w, nd, nw, t.GetNetname()))
        else:
            already.append(t)

    # refill zones before judgement -- stale fills make DRC lie
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(a.out)
    print(f"vias changed: {len(changed)}  already conformant: {len(already)}")
    os.makedirs(a.report, exist_ok=True)
    after = drc(a.out, a.dru, os.path.join(a.report, "drc-after.json"))

    print(f"\nBEFORE {dict(before[0])} unconnected={before[1]}")
    print(f"AFTER  {dict(after[0])} unconnected={after[1]}")
    new = set(after[0]) - set(before[0])
    print(f"new violation classes: {sorted(new) if new else 'none'}")
    print("\nVERDICT is the DRC's, not this script's. A clearance or short appearing here means the")
    print("0.05 mm of extra radius collided with neighbouring copper and the via must move first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
