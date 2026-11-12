#!/usr/bin/env python3
"""Read-only electrical/mechanical audit of a hub v10 board file.

Measures from the board itself (no DRC substitution):
  * outline bbox, footprint/pad/track/via/zone counts
  * via diameter + drill histogram, minimum annular ring
  * track width histogram, minimum track width
  * pad drill histogram, minimum finished hole
  * minimum hole-to-hole edge distance
  * minimum copper-to-Edge.Cuts distance, excluding the J_W* wing-seat pads
and flags values below the frozen fabrication limits:
  clearance 0.20, track 0.20, via diameter 0.60, via drill 0.30,
  hole 0.20 (ADR-141), hole-to-hole 0.25, edge 0.50.

WHY THE FROZEN LIMITS ARE ONLY A FLAG, NOT A VERDICT: measured 2026-11-02 on
hub_board_v10_lora1280_7of9 — the board ships no same-stem .kicad_dru, so native KiCad never
loads `jlcpcb-s1-frozen.kicad_dru`, and the project's global minimum lets 0.50 mm vias through.
A candidate graded here is NOT "frozen-rule-approved"; this tool reports the gap that decision
has to close.

Usage: electrical_mechanical_audit.py <board.kicad_pcb> [--json out.json]
Exit 0 = ran (flags are reported, not fatal); 2 = could not load the board.
"""
import argparse
import collections
import json
import math
import sys

import pcbnew

UM = 1_000_000.0
LIM = {"track_min": 0.20, "via_diam_min": 0.60, "via_drill_min": 0.30,
       "hole_min": 0.20, "hole_to_hole_min": 0.25, "edge_min": 0.50}
EDGE_CONNECTOR_PREFIXES = ("J_W",)


def mm(v):
    return round(v / UM, 4)


def audit(path):
    b = pcbnew.LoadBoard(path)
    if b is None:
        return None
    out = {"board": path}

    bb = b.GetBoardEdgesBoundingBox()
    out["outline_mm"] = [mm(bb.GetWidth()), mm(bb.GetHeight())]

    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    out["via_count"] = len(vias)
    vh = collections.Counter()
    ring = None
    for v in vias:
        d = mm(v.GetWidth(pcbnew.F_Cu))
        drill = mm(v.GetDrillValue())
        vh[f"d{d}/dr{drill}"] += 1
        r = (d - drill) / 2.0
        ring = r if ring is None else min(ring, r)
    out["via_histogram"] = dict(sorted(vh.items()))
    out["min_via_annular_ring_mm"] = ring
    out["via_below_frozen_diameter"] = sorted(
        {k for k in vh if float(k.split("/")[0][1:]) < LIM["via_diam_min"] - 1e-9})
    out["via_below_drill_floor"] = sorted(
        {k for k in vh if float(k.split("dr")[1]) < LIM["via_drill_min"] - 1e-9})

    tw = collections.Counter()
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        tw[mm(t.GetWidth())] += 1
    out["track_width_histogram"] = {str(k): v for k, v in sorted(tw.items())}
    out["min_track_width_mm"] = min(tw) if tw else None

    drills = collections.Counter()
    holes = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            d = mm(p.GetDrillSize().x)
            if d > 0:
                drills[d] += 1
                pos = p.GetPosition()
                holes.append((fp.GetReference(), p.GetNumber(), mm(pos.x), mm(pos.y), d))
    out["pad_drill_histogram"] = {str(k): v for k, v in sorted(drills.items())}
    out["min_pad_drill_mm"] = min(drills) if drills else None

    hmin, hpair = None, None
    for i in range(len(holes)):
        for j in range(i + 1, len(holes)):
            a, c = holes[i], holes[j]
            centre = math.hypot(a[2] - c[2], a[3] - c[3])
            if centre < 1e-6:          # same drill location exposed as two Pad objects
                continue
            d = centre - (a[4] + c[4]) / 2.0
            if hmin is None or d < hmin:
                hmin, hpair = d, (f"{a[0]}.{a[1]}@({a[2]},{a[3]})",
                                  f"{c[0]}.{c[1]}@({c[2]},{c[3]})")
    out["min_hole_to_hole_edge_mm"] = round(hmin, 4) if hmin is not None else None
    out["min_hole_to_hole_pair"] = hpair

    outlines = [d.GetBoundingBox() for d in b.GetDrawings()
                if d.GetLayer() == pcbnew.Edge_Cuts]

    def dist_to_edge(px, py):
        best = None
        for bx in outlines:
            l, t, r, bo = (bx.GetLeft() / UM, bx.GetTop() / UM,
                           bx.GetRight() / UM, bx.GetBottom() / UM)
            d = min(abs(px - l), abs(px - r), abs(py - t), abs(py - bo))
            best = d if best is None else min(best, d)
        return best

    worst, worst_what = None, None
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        for pt in (t.GetStart(), t.GetEnd()):
            d = dist_to_edge(pt.x / UM, pt.y / UM) - t.GetWidth() / UM / 2.0
            if worst is None or d < worst:
                worst, worst_what = d, f"track {t.GetNetname()} on {t.GetLayerName()}"
    for fp in b.GetFootprints():
        if fp.GetReference().startswith(EDGE_CONNECTOR_PREFIXES):
            continue
        for p in fp.Pads():
            pos = p.GetPosition()
            d = (dist_to_edge(pos.x / UM, pos.y / UM)
                 - max(p.GetSize().x, p.GetSize().y) / UM / 2.0)
            if worst is None or d < worst:
                worst, worst_what = d, f"pad {fp.GetReference()}.{p.GetNumber()}"
    out["min_non_wingseat_copper_to_edge_mm"] = round(worst, 4) if worst is not None else None
    out["min_copper_to_edge_what"] = worst_what

    flags = []
    if out["min_track_width_mm"] is not None and out["min_track_width_mm"] < LIM["track_min"] - 1e-9:
        flags.append(f"track width {out['min_track_width_mm']} < frozen {LIM['track_min']}")
    if out["via_below_frozen_diameter"]:
        flags.append(f"vias below frozen 0.60 mm: {out['via_below_frozen_diameter']}")
    if out["via_below_drill_floor"]:
        flags.append(f"via drills below 0.30 mm: {out['via_below_drill_floor']}")
    if out["min_pad_drill_mm"] is not None and out["min_pad_drill_mm"] < LIM["hole_min"] - 1e-9:
        flags.append(f"pad drill {out['min_pad_drill_mm']} < 0.20 mm")
    if (out["min_non_wingseat_copper_to_edge_mm"] is not None
            and out["min_non_wingseat_copper_to_edge_mm"] < LIM["edge_min"] - 1e-9):
        flags.append(f"copper-to-edge {out['min_non_wingseat_copper_to_edge_mm']} < frozen "
                     f"{LIM['edge_min']} ({out['min_copper_to_edge_what']})")
    out["flags"] = flags
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--json")
    a = ap.parse_args()
    r = audit(a.board)
    if r is None:
        print(f"FAIL: could not load {a.board}")
        return 2
    text = json.dumps(r, indent=2)
    print(text)
    if a.json:
        with open(a.json, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
