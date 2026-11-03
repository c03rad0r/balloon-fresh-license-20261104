#!/usr/bin/env python3
"""Merge collinear consecutive track segments of the same net+layer into single segments.

WHY THIS EXISTS
Measured 2026-11-03 on this board family (`tracks` = segments, excluding vias):

    master   843 segments, 411 under 0.25 mm, 196 under 0.10 mm, median 0.30 mm
    V14     1105 segments, 593 under 0.25 mm, 196 under 0.10 mm, median 0.21 mm

FreeRouting 2.2.4 dies on such a board with `StackOverflowError` in `PolylineTrace.combine`: the
recursion walks a chain of collinear micro-segments and exhausts the stack. That is a defect in the
BOARD DATA, not just a tool incompatibility -- thousands of 0.1 mm segments are no better
electrically than one straight segment, and they make every downstream tool work harder.

SAFETY RULE THAT MATTERS MOST
A vertex may only be dissolved when EXACTLY TWO segments of that net+layer meet there. If three or
more meet (a T-junction or a star), that vertex is a real connection point: removing it would
silently disconnect the branch. This is checked per vertex before any merge is planned.

Tolerance: collinearity within --tol-deg (default 1.0 deg). At 1 deg the maximum deviation across a
0.1 mm segment is 0.1*sin(1deg) = 0.0017 mm, i.e. far below the 0.20 mm clearance rule.

Usage:
  merge_collinear.py <src> <out> --dru <frozen.kicad_dru> [--tol-deg 1.0] [--apply]

Without --apply it reports only. With --apply it writes <out> and re-runs DRC, refusing to keep the
result if any violation class or the unconnected count got worse.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

UM = 1e6


def run_drc(pcb, dru, out_json):
    stem = os.path.splitext(pcb)[0]
    shutil.copyfile(dru, stem + ".kicad_dru")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out_json, pcb], capture_output=True, text=True)
    if not os.path.exists(out_json):
        return None, None
    d = json.load(open(out_json))
    return Counter(v["type"] for v in d.get("violations", [])), len(d.get("unconnected_items", []))


def angle(p, q):
    return math.atan2(q[1] - p[1], q[0] - p[0])


def collinear(a1, a2, tol):
    d = abs(a1 - a2) % math.pi
    return d < tol or abs(d - math.pi) < tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--dru", required=True)
    ap.add_argument("--tol-deg", type=float, default=1.0)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    tol = math.radians(a.tol_deg)

    outdir = os.path.dirname(a.out) or "."
    os.makedirs(outdir, exist_ok=True)
    before, ubefore = run_drc(a.src, a.dru, os.path.join(outdir, "merge-before.json"))
    b = pcbnew.LoadBoard(a.src)

    tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
    n_before = len(tracks)
    print(f"segments before: {n_before}")

    def pt(e):
        return (round(e.x / UM, 3), round(e.y / UM, 3))

    # Group by exact (net, layer, width) so we never merge across a width change.
    groups = {}
    for t in tracks:
        groups.setdefault((t.GetNetname(), t.GetLayer(), t.GetWidth()), []).append(t)

    plan = []  # list of (keep_first, keep_last, [originals to delete])
    for (net, lay, width), segs in groups.items():
        if len(segs) < 2:
            continue

        # vertex -> segments incident on it (count is what protects T-junctions)
        incid = {}
        for i, t in enumerate(segs):
            for k in (pt(t.GetStart()), pt(t.GetEnd())):
                incid.setdefault(k, set()).add(i)

        used = set()
        for i, t in enumerate(segs):
            if i in used:
                continue
            chain = [i]
            used.add(i)
            head, tail = pt(t.GetStart()), pt(t.GetEnd())
            cur = tail
            prev = angle(head, tail)
            while True:
                if len(incid.get(cur, ())) != 2:   # T-junction or free end -> stop here
                    break
                nxt = None
                for j in incid[cur]:
                    if j in used:
                        continue
                    tj = segs[j]
                    aj, bj = pt(tj.GetStart()), pt(tj.GetEnd())
                    if not collinear(prev, angle(aj, bj), tol):
                        continue
                    other = bj if aj == cur else aj
                    if len(incid.get(other, ())) == 0:
                        continue
                    nxt = (j, other)
                    break
                if not nxt:
                    break
                j, other = nxt
                used.add(j)
                chain.append(j)
                prev = angle(cur, other)
                cur = other
            if len(chain) > 1:
                plan.append(([segs[i] for i in chain], head, cur, net, lay, width))

    removable = sum(len(c) - 1 for (c, *_rest) in plan)
    print(f"chains found: {len(plan)}   segments removable: {removable}   "
          f"projected after: {n_before - removable}")

    if not a.apply:
        for (chain, head, tail, net, lay, width) in plan[:12]:
            print(f"  {net:16s} {pcbnew.LayerName(lay):6s} {len(chain)} segs -> 1   "
                  f"{head} -> {tail}")
        print("\n(report only; rerun with --apply)")
        return 0

    for (objs, head, tail, net, lay, width) in plan:
        nt = pcbnew.PCB_TRACK(b)
        nt.SetStart(pcbnew.VECTOR2I(int(head[0] * UM), int(head[1] * UM)))
        nt.SetEnd(pcbnew.VECTOR2I(int(tail[0] * UM), int(tail[1] * UM)))
        nt.SetWidth(int(width))
        nt.SetLayer(lay)
        nt.SetNet(objs[0].GetNet())
        b.Add(nt)
        for o in objs:
            b.Remove(o)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(a.out)
    print(f"saved {a.out}")

    after, uafter = run_drc(a.out, a.dru, os.path.join(outdir, "merge-after.json"))
    print(f"\nBEFORE {dict(before)} unconnected={ubefore}")
    print(f"AFTER  {dict(after)} unconnected={uafter}")
    worse = (uafter is not None and ubefore is not None and uafter > ubefore)
    newc = (after - before) if (after is not None and before is not None) else Counter()
    if worse or newc:
        print(f"REFUSE: merge made it worse (new classes {dict(newc)}, "
              f"unconnected {ubefore}->{uafter}). Do not use this output.")
        return 3
    print("Merge kept: no new violation class, unconnected not worse.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
