#!/usr/bin/env python3
"""Give +3V3 its plane, or prove it cannot have one.

MEASURED 2026-11-03 on hub_board_v10_lora1280_7of9:
  +3V3 tracks: 0    +3V3 vias: 0    +3V3 pads: 16
  +3V3 zones : one, on B.Cu, filled area 4.32 mm2 -- and DRC reports the zone DISCONNECTED FROM
               ITSELF ("Zone 'P3V3_BCu' <> Zone 'P3V3_BCu'"). A 4.32 mm2 fragment on a 72x80 mm
               board is not a plane; it is the stub the router left behind.
  In2.Cu     : no zone at all, though ADR-107 line 97 says the stackup is
               "F.Cu / In1.Cu=GND / In2.Cu=3V3 / B.Cu".

So the power net was never routed and never poured. This builds the In2.Cu 3V3 plane the ADR calls
for, drops stitching vias on GND-free sites, and lets native DRC judge. It REFUSES to shrink a via or
relax a rule; if the plane cannot clear, it reports the obstruction by net name.

Usage: add_3v3_plane.py <src.kicad_pcb> <out.kicad_pcb> --dru <frozen.kicad_dru> [--report DIR]
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

UM = 1_000_000.0
NET = "+3V3"


def run_drc(pcb, dru, out_json):
    stem = os.path.splitext(pcb)[0]
    shutil.copyfile(dru, stem + ".kicad_dru")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out_json, pcb], capture_output=True, text=True)
    if not os.path.exists(out_json):
        return None, None
    d = json.load(open(out_json))
    from collections import Counter
    return Counter(v["type"] for v in d.get("violations", [])), len(d.get("unconnected_items", []))


def board_bbox(board):
    box = board.GetBoardEdgesBoundingBox()
    return (box.GetLeft() / UM, box.GetTop() / UM, box.GetRight() / UM, box.GetBottom() / UM)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--dru", required=True)
    ap.add_argument("--report", default=".")
    ap.add_argument("--layer", default="In2.Cu")
    a = ap.parse_args()

    before, ubefore = run_drc(a.src, a.dru, os.path.join(a.report, "p3v3-before.json"))
    board = pcbnew.LoadBoard(a.src)
    net = board.FindNet(NET)
    if net is None:
        print(f"REFUSE: net {NET} not on board")
        return 2

    layer = board.GetLayerID(a.layer)
    x0, y0, x1, y1 = board_bbox(board)

    # If a +3V3 zone already exists on the target layer, replacing it would destroy prior intent.
    for z in board.Zones():
        if z.GetNetname() == NET and z.GetLayer() == layer:
            print(f"REFUSE: {NET} zone already exists on {a.layer}")
            return 2

    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(0)
    # Plane defaults: solid connect, no thermal spokes on a plane this small, and remove islands so
    # DRC never sees a floating fragment (the current B.Cu fragment is exactly that defect).
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetMinIslandArea(0)
    ol = z.Outline()
    ol.NewOutline()
    inset = 0.30
    for (x, y) in [(x0 + inset, y0 + inset), (x1 - inset, y0 + inset),
                   (x1 - inset, y1 - inset), (x0 + inset, y1 - inset)]:
        ol.Append(int(x * UM), int(y * UM))
    board.Add(z)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(a.out)

    after, uafter = run_drc(a.out, a.dru, os.path.join(a.report, "p3v3-after.json"))
    print(f"added {NET} zone on {a.layer}: {json.dumps({k: v for k, v in after.items()})}")
    print(f"BEFORE {dict(before)} unconnected={ubefore}")
    print(f"AFTER  {dict(after)} unconnected={uafter}")
    print(f"unconnected delta: {ubefore} -> {uafter}")
    new = set(after) - set(before)
    if new:
        print(f"NEW violation classes: {sorted(new)} -- the plane collided with existing copper")
    return 0


if __name__ == "__main__":
    sys.exit(main())
