#!/usr/bin/env python3
"""Nudge vias off their neighbours by the minimum, with connected track ends following.

Why this exists: upsize_vias.py takes the board from 81 frozen-rule violations to 13 -- but 4 of
those 13 are `clearance` at exactly 0.150 mm against a 0.200 mm rule. That is 0.05 mm short, which
is the extra radius the 0.60 mm via pad added. Shrinking the via back would restore the
via_diameter violation, so the only honest fix is to MOVE the copper: shift the offending via and
drag every track endpoint that lands on it.

Search: for each offending via, try 32 directions x a 0.02 mm..0.60 mm ladder, score each candidate
by the minimum clearance it achieves against NON-net copper, keep the first that reaches the rule
with a margin and does not exceed the board outline. DRC remains the judge; this only proposes.

Usage: nudge_vias.py <src.kicad_pcb> <out.kicad_pcb> --dru <frozen.kicad_dru> --report <dir>
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
CLEAR = 0.20
MARGIN = 0.02


def drc(pcb, dru, out_json):
    stem = os.path.splitext(pcb)[0]
    shutil.copyfile(dru, stem + ".kicad_dru")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out_json, pcb], capture_output=True, text=True)
    if not os.path.exists(out_json):
        return None
    d = json.load(open(out_json))
    from collections import Counter
    return Counter(v["type"] for v in d.get("violations", [])), d


def seg_pt(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def obstacles(board, skip_net):
    """(kind, geometry, radius, net) for every copper object not on skip_net."""
    out = []
    for t in board.GetTracks():
        net = t.GetNetname()
        if net == skip_net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            out.append(("pt", (p.x / UM, p.y / UM), t.GetWidth(pcbnew.B_Cu) / UM / 2.0, net))
        else:
            lay = t.GetLayer()
            if lay not in (pcbnew.F_Cu, pcbnew.B_Cu):
                continue
            out.append(("seg", (t.GetStart().x / UM, t.GetStart().y / UM,
                                t.GetEnd().x / UM, t.GetEnd().y / UM),
                        t.GetWidth() / UM / 2.0, net))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == skip_net:
                continue
            if pcbnew.B_Cu not in p.GetLayerSet().Seq() and \
               pcbnew.F_Cu not in p.GetLayerSet().Seq():
                continue
            bb = p.GetBoundingBox()
            out.append(("rect", (bb.GetLeft() / UM, bb.GetTop() / UM,
                                 bb.GetRight() / UM, bb.GetBottom() / UM), 0.0,
                        f"{fp.GetReference()}.{p.GetNumber()}"))
    return out


def clearance_at(x, y, r, obs):
    best = (9e9, None)
    for kind, g, rad, net in obs:
        if kind == "pt":
            d = math.hypot(x - g[0], y - g[1]) - (r + rad)
        elif kind == "seg":
            d = seg_pt(x, y, *g) - (r + rad)
        else:
            d = math.hypot(max(g[0] - x, 0, x - g[2]), max(g[1] - y, 0, y - g[3])) - r
        if d < best[0]:
            best = (d, net)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--dru", required=True)
    ap.add_argument("--report", default=".")
    a = ap.parse_args()

    before, d = drc(a.src, a.dru, os.path.join(a.report, "nudge-before.json"))
    board = pcbnew.LoadBoard(a.src)

    # which vias are named by a clearance violation?
    culprits = set()
    for v in d.get("violations", []):
        if v.get("type") != "clearance":
            continue
        for it in v.get("items", []):
            desc = it.get("description", "")
            if desc.startswith("Via ["):
                culprits.add(desc.split("[", 1)[1].split("]", 1)[0])

    print(f"clearance violations: {before.get('clearance', 0)}; vias named: {len(culprits)}")
    if not culprits:
        print("nothing to nudge")
        return 0

    moved = []
    for v in [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
        net = v.GetNetname()
        if net not in culprits:
            continue
        r = v.GetWidth(pcbnew.B_Cu) / UM / 2.0
        obs = obstacles(board, net)
        p0 = (v.GetPosition().x / UM, v.GetPosition().y / UM)
        base = clearance_at(p0[0], p0[1], r, obs)
        # The DRC names the NET, not the via, so several vias on that net can be implicated.
        # Only move one that is ACTUALLY tight -- measured 2026-11-03: keying on net alone moved 7
        # vias for 4 violations, two of which sat at 1.55 mm clearance and needed no change at all.
        if base[0] >= CLEAR:
            print(f"  skip {net} at ({p0[0]:.2f},{p0[1]:.2f}) cl={base[0]:.3f} already legal")
            continue
        best = None
        for k in range(32):
            ang = k * 2 * math.pi / 32
            for step in [0.02 * s for s in range(1, 31)]:
                x, y = p0[0] + step * math.cos(ang), p0[1] + step * math.sin(ang)
                if not (0.5 < x < 71.6 and 0.5 < y < 79.6):
                    continue
                cl, _ = clearance_at(x, y, r, obs)
                if cl >= CLEAR + MARGIN:
                    if best is None or step < best[0]:
                        best = (step, x, y, cl)
                    break
            if best:
                break
        if not best:
            print(f"  NO SAFE MOVE for via {net} at ({p0[0]:.2f},{p0[1]:.2f}) cl={base[0]:.3f}")
            continue
        step, x, y, cl = best
        # drag connected track endpoints
        dragged = 0
        for t in board.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                continue
            for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                pt = getter()
                if abs(pt.x / UM - p0[0]) < 1e-6 and abs(pt.y / UM - p0[1]) < 1e-6:
                    setter(pcbnew.VECTOR2I(int(x * UM), int(y * UM)))
                    dragged += 1
        v.SetPosition(pcbnew.VECTOR2I(int(x * UM), int(y * UM)))
        moved.append((net, p0, (x, y), step, base[0], cl, dragged))
        print(f"  MOVED {net} ({p0[0]:.2f},{p0[1]:.2f}) -> ({x:.2f},{y:.2f}) "
              f"+{step:.2f}mm  cl {base[0]:.3f} -> {cl:.3f}  tracks dragged={dragged}")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(a.out)
    after, _ = drc(a.out, a.dru, os.path.join(a.report, "nudge-after.json"))
    print(f"\nBEFORE {dict(before)}")
    print(f"AFTER  {dict(after)}")
    json.dump([{"net": n, "from": p, "to": t, "shift_mm": s, "cl_before": b, "cl_after": c,
                "tracks": dg} for n, p, t, s, b, c, dg in moved],
              open(os.path.join(a.report, "nudge-log.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
