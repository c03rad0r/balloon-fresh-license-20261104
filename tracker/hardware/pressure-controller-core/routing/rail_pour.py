#!/usr/bin/env python3
"""rail_pour.py -- close the two rail nets with copper pours, in bounded measured stages.

WHAT THIS IS. A pour driver, not a router. It adds zone geometry only: no track, no via
unless a stage explicitly declares one, no placement, net, keep-out or rule change. Each stage
is refilled with KiCad's own ZONE_FILLER and judged by native `kicad-cli pcb drc`. The tools
already in this directory are reused rather than re-implemented:

  pour_stage.add_pour / set_pad_connection   zone + pad-local connection overrides
  verify_batch.main                          native DRC deltas, per-net opens, broken pairs
  check_preservation.main                    every pre-existing object byte-identical
  physical_partitions.partitions/splits      physical polygon partition proof
  test_physical_partitions.py                negative controls (gap-fill and via removal)

WHY THE STAGES LOOK LIKE THIS (measured on this board, 2026-11-11, native DRC):

  * /GND on B.Cu alone            63 -> 58 opens (closes 5, all through-hole or B.Cu pads)
  * /GND on B.Cu + F.Cu           63 -> 35 opens, /GND 30 -> 2
  * /GND F.Cu at priority over nothing, /+3V3 full F.Cu pour instead
                                  /+3V3 19 -> 3 but /GND 30 -> 23: a same-layer rail loses
  * /+3V3 local priority-1 windows under a GND F.Cu plane
                                  closes 11 /+3V3 opens but strands 4 GND SMD pads that lose
                                  their only copper contact, and GND goes 2 -> 6. Rejected.
The board is 2-layer and both rails want F.Cu; there is no arrangement where a full-board
pour of each rail coexists. So GND takes B.Cu as a plane and F.Cu as a plane, and +3V3 gets a
measured local treatment in the stage that can prove it costs GND nothing.

Connection style: THERMAL by default. Pads whose thermal cannot physically resolve two spokes
(0.50 x 0.25 mm pad in a 0.20 mm clearance pocket) are overridden to a solid connection
PAD-LOCALLY and listed. That is an assembly consequence and is reported, never hidden.
"""
import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pour_stage as PS      # noqa: E402
import verify_batch as VB    # noqa: E402
import physical_partitions as PP  # noqa: E402

UM = 1_000_000
RESERVATION = (33.0, 24.0, 63.0, 48.0)   # motor/protection rule area: no rail copper inside
STRIPS = ((47.45, 7.5, 48.55, 12.5), (59.45, 7.5, 60.55, 12.5))  # MS5611 inter-pad keep-outs


# ---------------------------------------------------------------- geometry facts

def filled(board, net, layer):
    lay = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}[layer]
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsOnLayer(lay):
            continue
        ps = z.GetFilledPolysList(lay)
        for i in range(ps.OutlineCount()):
            r = ps.COutline(i)
            ext = [(r.CPoint(k).x, r.CPoint(k).y) for k in range(r.PointCount())]
            holes = []
            for h in range(ps.HoleCount(i)):
                hr = ps.CHole(i, h)
                holes.append([(hr.CPoint(k).x, hr.CPoint(k).y) for k in range(hr.PointCount())])
            out.append((z, i, ext, holes))
    return out


def island_report(board, net, layer, min_width=0.25):
    """Every filled island: area, bbox, whether it bridges pads, and width vs house minimum."""
    from shapely.geometry import Polygon
    lay = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}[layer]
    pads = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != net or not p.IsOnLayer(lay):
                continue
            s = pcbnew.SHAPE_POLY_SET()
            p.TransformShapeToPolygon(s, lay, 0, 100, pcbnew.ERROR_INSIDE)
            for i in range(s.OutlineCount()):
                r = s.COutline(i)
                pads.append((f.GetReference(), p.GetNumber(),
                             Polygon([(r.CPoint(k).x, r.CPoint(k).y)
                                      for k in range(r.PointCount())])))
    rows = []
    for z, idx, ext, holes in filled(board, net, layer):
        poly = Polygon(ext, holes)
        minx, miny, maxx, maxy = poly.bounds
        # LOCAL width: 2 * largest inscribed-circle radius, by far the honest measure for a
        # plane with holes. A global min-width test on a 2 mm strip is not a pour defect test.
        width = 2 * poly.buffer(0).minimum_clearance if not poly.is_empty else 0.0
        touching = sorted({"%s.%s" % (r, n) for r, n, pp in pads if pp.intersects(poly)})
        rows.append({
            "layer": layer, "area_mm2": round(poly.area / UM / UM, 4),
            "bbox_mm": [round(minx / UM, 3), round(miny / UM, 3),
                        round(maxx / UM, 3), round(maxy / UM, 3)],
            "holes": len(poly.interiors),
            "min_clearance_mm": round(width / UM, 4),
            "pads_bridged": len(touching), "pads": touching[:8],
            "isolated": len(touching) == 0,
        })
    return rows


def copper_in_reservation(board):
    from shapely.geometry import Polygon, box as sbox
    region = sbox(*RESERVATION)
    hits = []
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        for lay, nm in ((pcbnew.F_Cu, "F.Cu"), (pcbnew.B_Cu, "B.Cu")):
            if not z.IsOnLayer(lay):
                continue
            ps = z.GetFilledPolysList(lay)
            for i in range(ps.OutlineCount()):
                r = ps.COutline(i)
                poly = Polygon([(r.CPoint(k).x / UM, r.CPoint(k).y / UM)
                                for k in range(r.PointCount())])
                inter = poly.intersection(region)
                if inter.area > 0:
                    hits.append({"net": z.GetNetname(), "layer": nm,
                                 "area_mm2": round(inter.area, 4)})
    for t in board.GetTracks():
        for lay, nm in ((pcbnew.F_Cu, "F.Cu"), (pcbnew.B_Cu, "B.Cu")):
            if not t.IsOnLayer(lay):
                continue
            s = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(s, lay, 0, 100, pcbnew.ERROR_INSIDE)
            for i in range(s.OutlineCount()):
                r = s.COutline(i)
                poly = Polygon([(r.CPoint(k).x / UM, r.CPoint(k).y / UM)
                                for k in range(r.PointCount())])
                if poly.intersection(region).area > 0:
                    hits.append({"net": t.GetNetname(), "layer": nm, "kind": "track"})
    return hits


def copper_in_strips(board):
    from shapely.geometry import Polygon, box as sbox
    hits = []
    for i, strip in enumerate(STRIPS):
        region = sbox(*strip)
        for z in board.Zones():
            if z.GetIsRuleArea():
                continue
            for lay, nm in ((pcbnew.F_Cu, "F.Cu"), (pcbnew.B_Cu, "B.Cu")):
                if not z.IsOnLayer(lay):
                    continue
                ps = z.GetFilledPolysList(lay)
                for k in range(ps.OutlineCount()):
                    r = ps.COutline(k)
                    poly = Polygon([(r.CPoint(j).x / UM, r.CPoint(j).y / UM)
                                    for j in range(r.PointCount())])
                    a = poly.intersection(region).area
                    if a > 0:
                        hits.append({"strip": i, "net": z.GetNetname(), "layer": nm,
                                     "area_mm2": round(a, 4)})
    return hits


# ---------------------------------------------------------------- stage machinery

def drc_summary(path, tag, tmpdir):
    j = os.path.join(tmpdir, "drc-%s.json" % tag)
    d = VB.drc(str(path), j)
    cnt = collections.Counter(v["type"] for v in d["violations"] if v["type"])
    return {"opens": len(d["unconnected_items"]),
            "opens_by_net": VB.opens_by_net(d["unconnected_items"]),
            "violations": dict(cnt)}, d


def starved_pads(d):
    out = []
    for v in d["violations"]:
        if v["type"] != "starved_thermal":
            continue
        zdesc = next(i["description"] for i in v["items"] if i["description"].startswith("Zone "))
        pdesc = next(i["description"] for i in v["items"] if "ad " in i["description"]
                     and "[" in i["description"])
        m = re.match(r"(?:PTH )?[Pp]ad (\S+) \[.*?\] of (\S+)", pdesc)
        out.append({"net": re.search(r"\[(.*?)\]", zdesc).group(1),
                    "ref": m.group(2), "pad": m.group(1), "record": pdesc})
    return out


def refill(board):
    return pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def copy_siblings(src, dst):
    """A board's .kicad_pro/.kicad_prl must travel with it or DRC reads different rules."""
    for ext in (".kicad_pro", ".kicad_prl"):
        s = Path(os.path.splitext(str(src))[0] + ext)
        if s.exists():
            Path(os.path.splitext(str(dst))[0] + ext).write_bytes(s.read_bytes())


def render(board_path, side, out_base):
    import subprocess
    lay = ("F.Cu,F.Silkscreen,F.Fab,F.Courtyard,Edge.Cuts" if side == "top"
           else "B.Cu,B.Silkscreen,B.Fab,B.Courtyard,Edge.Cuts")
    svg = str(out_base) + ".svg"
    cmd = ["kicad-cli", "pcb", "export", "svg", "--layers", lay, "--mode-single",
           "--exclude-drawing-sheet", "--page-size-mode", "2", "-o", svg]
    if side == "bottom":
        cmd.append("--mirror")
    cmd.append(str(board_path))
    subprocess.run(cmd, check=True, capture_output=True)
    subprocess.run(["rsvg-convert", "-w", "1200", "-o", str(out_base) + ".png", svg],
                   check=True, capture_output=True)
    return svg, str(out_base) + ".png"


if __name__ == "__main__":
    print("this module is driven by rail_batch.py; see its docstring")
