#!/usr/bin/env python3
"""APPLY the proven B.Cu solar routes to a COPY of the board, then grade with native DRC.

Only the 7 pairs whose path is proven by route_solar_bitmap.py are applied; the 2 that failed are
reported and skipped. Nothing here invents a route: the geometry comes from the same rasterised
BFS that the negative control gates, re-run in-process.

What it does, in order:
  1. loads the source board, copies it to --out (NEVER edits the source)
  2. for each candidate pair: re-runs the router; on NO PATH it records the failure and moves on
  3. converts the grid path to PCB_TRACK segments on B.Cu, net assigned, width --track-w,
     simplified with collinear-point removal so the file does not grow by hundreds of 0.15 mm stubs
  4. saves, copies the .kicad_pro/.kicad_prl/.kicad_dru sidecars, refills zones, runs native DRC
  5. prints the DRC delta against an untouched refilled control

Gate: the run only reports a candidate as PROMOTABLE when DRC shows NO new violation class, NO new
unconnected item, and clearance/shorting_items stay 0. Anything else is reported as a refusal.

Usage: apply_solar_routes.py <src.kicad_pcb> <out.kicad_pcb> [--grid 0.15] [--track-w 0.20]
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew  # noqa: E402
import route_solar_bitmap as R  # noqa: E402

UM = 1_000_000.0
REPO_HW = "/home/c08r4d0r/worktrees/flight-readiness-20261102/tracker/hardware"


def simplify(path, grid):
    """Drop collinear interior points so a 300-point grid walk becomes a few real segments."""
    if len(path) < 3:
        return path
    out = [path[0]]
    for i in range(1, len(path) - 1):
        ax, ay = path[i - 1]
        bx, by = path[i]
        cx, cy = path[i + 1]
        # cross product of the two direction vectors in grid units
        if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) != 0:
            out.append(path[i])
    out.append(path[-1])
    return out


def push_off_edge(pts, board, clear, track_r, edge, iters=60):
    """Walk the path away from the board outline wherever it is too close.

    WHY: the endpoint exemption lets the router START on a J_W land that sits on Edge.Cuts by
    design. It does not license the ROUTE to run along the edge. Measured on the first application:
    4 new `copper_edge_clearance` errors were my own tracks, 7.5-8.25 mm long, hugging the edge —
    and the repo's allow-list scopes that rule to J_W* PADS only, so a TRACK at the edge is exactly
    the defect class the scope exists to catch.

    This nudges only the interior vertices: each one is moved along the local outward normal until
    it is `track_r + edge` inside the outline, and left alone if it already is. Endpoints are never
    moved (they are the pads).
    """
    bb = board.GetBoardEdgesBoundingBox()
    ex0, ey0 = bb.GetLeft() / UM, bb.GetTop() / UM
    ex1, ey1 = bb.GetRight() / UM, bb.GetBottom() / UM
    need = track_r + edge
    pts = list(pts)
    for _ in range(iters):
        moved = False
        for i in range(1, len(pts) - 1):
            x, y = pts[i]
            dx = min(x - ex0, ex1 - x)
            dy = min(y - ey0, ey1 - y)
            if dx < need:
                x += (need - dx) if (x - ex0) < (ex1 - x) else -(need - dx)
            if dy < need:
                y += (need - dy) if (y - ey0) < (ey1 - y) else -(need - dy)
            if (x, y) != pts[i]:
                pts[i] = (x, y)
                moved = True
        if not moved:
            break
    return pts


def refill(src, dst):
    subprocess.run(["python3", os.path.join(REPO_HW, "refill_zones.py"), src, dst],
                   capture_output=True, text=True)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = os.path.splitext(src)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(dst)[0] + ext)
    return os.path.exists(dst)


def drc(board):
    out = os.path.splitext(board)[0] + "-drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out, board], capture_output=True, text=True)
    with open(out) as fh:
        d = json.load(fh)
    errs, warns = {}, {}
    for v in d["violations"]:
        tgt = errs if v["severity"] == "error" else warns
        tgt[v["type"]] = tgt.get(v["type"], 0) + 1
    return {"errors": errs, "warnings": warns, "total_err": sum(errs.values()),
            "total_warn": sum(warnings_ := warns.values()) if False else sum(warns.values()),
            "unconnected": len(d["unconnected_items"]), "json": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--grid", type=float, default=0.15)
    ap.add_argument("--track-w", type=float, default=0.20)
    ap.add_argument("--clearance", type=float, default=0.20)
    ap.add_argument("--edge", type=float, default=0.50)
    ap.add_argument("--window-pad", type=float, default=12.0)
    a = ap.parse_args()

    # ---- control: refilled, untouched ----
    base, ext = os.path.splitext(a.out)
    ctrl_raw, ctrl = f"{base}-ctrl-raw{ext}", f"{base}-ctrl{ext}"
    shutil.copy(a.src, ctrl_raw)
    for e2 in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = os.path.splitext(a.src)[0] + e2
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(ctrl_raw)[0] + e2)
    if not refill(ctrl_raw, ctrl):
        print("FAIL: control refill")
        return 1
    c = drc(ctrl)
    print(f"CONTROL (refilled, untouched): {c['total_err']} errors "
          f"{json.dumps(c['errors'], sort_keys=True)} | {c['total_warn']} warnings | "
          f"{c['unconnected']} unconnected")

    # ---- route and apply ----
    # TWO PASSES, and the order matters. Measured 2026-11-03: routing and adding in one pass made
    # pair 3 fail in this script while the standalone router found it, because pairs 0-2 had already
    # added /W1_SOLAR_N copper that blocks /W2_SOLAR_N. The routes INTERACT, so every path is
    # computed against the PRISTINE board first and only then added. Same board state, same result
    # as route_solar_bitmap.py, and no pair is judged against a board half-modified by its siblings.
    board = pcbnew.LoadBoard(a.src)
    applied, skipped, planned = [], [], []
    for pi, (net, sa, sb) in enumerate(R.PAIRS):
        pa, pb = R.bcu_pads(board, sa), R.bcu_pads(board, sb)
        if not pa or not pb:
            skipped.append((pi, net, sa, sb, "no B.Cu pad on one end"))
            continue
        A, B = pa[0], pb[0]
        ax, ay = A.GetPosition().x / UM, A.GetPosition().y / UM
        bx, by = B.GetPosition().x / UM, B.GetPosition().y / UM
        win = (min(ax, bx) - a.window_pad, min(ay, by) - a.window_pad,
               max(ax, bx) + a.window_pad, max(ay, by) + a.window_pad)
        blocked, edge_blocked, nx, ny, (wx0, wy0) = R.rasterise(
            board, net, a.grid, a.clearance, a.track_w / 2.0, a.edge, win)
        s = (int(round((ax - wx0) / a.grid)), int(round((ay - wy0) / a.grid)))
        g = (int(round((bx - wx0) / a.grid)), int(round((by - wy0) / a.grid)))
        exempt = set()
        for pad in (A, B):
            bb = pad.GetBoundingBox()
            pbb = (bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM, bb.GetBottom() / UM)
            i0 = int((pbb[0] - a.grid - wx0) / a.grid)
            i1 = int((pbb[2] + a.grid - wx0) / a.grid)
            j0 = int((pbb[1] - a.grid - wy0) / a.grid)
            j1 = int((pbb[3] + a.grid - wy0) / a.grid)
            for j in range(max(0, j0), min(ny - 1, j1) + 1):
                for i in range(max(0, i0), min(nx - 1, i1) + 1):
                    px, py = wx0 + i * a.grid, wy0 + j * a.grid
                    if (pbb[0] - a.grid <= px <= pbb[2] + a.grid
                            and pbb[1] - a.grid <= py <= pbb[3] + a.grid):
                        exempt.add((i, j))
        blocked[s[1] * nx + s[0]] = 0
        blocked[g[1] * nx + g[0]] = 0
        path = R.bfs(blocked, edge_blocked, nx, ny, s, g, exempt)
        if path is None:
            skipped.append((pi, net, sa, sb, "NO PATH on B.Cu"))
            continue

        pts = [(wx0 + i * a.grid, wy0 + j * a.grid) for i, j in path]
        pts = simplify(pts, a.grid)
        # snap the ends onto the real pad centres so the track actually lands on copper
        pts[0] = (ax, ay)
        pts[-1] = (bx, by)
        # The router may walk inside the edge keep-out ONLY to leave/enter a J_W land. Everything
        # between must respect the edge rule, so push interior vertices out. Measured on the first
        # application: without this, 4 new copper_edge_clearance errors were my own tracks running
        # 7.5-8.25 mm along the edge — the exact defect the repo's J_W*-pad-scoped allow-list
        # exists to distinguish from legal edge connectors.
        pts = push_off_edge(pts, board, a.clearance, a.track_w / 2.0, a.edge)
        # DEFER the write: collect every path first (all searched on the pristine board), then add
        # them in one pass below. Adding inside this loop let each route block the next.
        planned.append((pi, net, sa, sb, pts))
        continue

    for (pi, net, sa, sb, pts) in planned:
        netobj = board.FindNet(net)
        if netobj is None:
            skipped.append((pi, net, sa, sb, f"net {net!r} not found on board"))
            continue
        added = 0
        for k in range(len(pts) - 1):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(int(pts[k][0] * UM), int(pts[k][1] * UM)))
            t.SetEnd(pcbnew.VECTOR2I(int(pts[k + 1][0] * UM), int(pts[k + 1][1] * UM)))
            t.SetWidth(int(a.track_w * UM))
            t.SetLayer(pcbnew.B_Cu)
            t.SetNet(netobj)
            board.Add(t)
            added += 1
        applied.append((pi, net, sa, sb, added, len(pts)))

    for row in applied:
        print(f"  APPLIED pair {row[0]} {row[1]:14s} {row[2]} -> {row[3]}: "
              f"{row[4]} segments, {row[5]} vertices")
    for row in skipped:
        print(f"  SKIPPED pair {row[0]} {row[1]:14s} {row[2]} -> {row[3]}: {row[4]}")

    raw = f"{base}-raw{ext}"
    pcbnew.SaveBoard(raw, board)
    for e2 in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s2 = os.path.splitext(a.src)[0] + e2
        if os.path.exists(s2):
            shutil.copy(s2, os.path.splitext(raw)[0] + e2)
    if not refill(raw, a.out):
        print("FAIL: refill of result")
        return 1
    f = drc(a.out)
    print(f"RESULT  (refilled): {f['total_err']} errors {json.dumps(f['errors'], sort_keys=True)} "
          f"| {f['total_warn']} warnings | {f['unconnected']} unconnected")
    print(f"  delta: errors {c['total_err']} -> {f['total_err']}, "
          f"unconnected {c['unconnected']} -> {f['unconnected']}, "
          f"warnings {c['total_warn']} -> {f['total_warn']}")

    checks = [
        ("no new error class", not (set(f["errors"]) - set(c["errors"])),
         sorted(set(f["errors"]) - set(c["errors"])) or "none"),
        ("clearance still 0", f["errors"].get("clearance", 0) == 0,
         f["errors"].get("clearance", 0)),
        ("shorting_items still 0", f["errors"].get("shorting_items", 0) == 0,
         f["errors"].get("shorting_items", 0)),
        ("unconnected did not rise", f["unconnected"] <= c["unconnected"],
         f"{c['unconnected']} -> {f['unconnected']}"),
    ]
    print("\nGATE:")
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:28} {detail}")
        ok = ok and passed
    print("\nGATE: " + ("PASS -- candidate produced (NOT fab-approved, NOT frozen-rule-verified, "
                        "NOT a flight build)" if ok else "FAIL -- do not promote"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
