#!/usr/bin/env python3
"""Gate: no copper TRACK may cross a wing-socket cavity edge.

ADR-142 (Accepted 2026-11-03) rules that a track crossing a `J_W` socket's
Edge.Cuts cavity is never acceptable — the exemption is pad-only because the
pads ARE the edge-launched interface, while a track over the cavity is copper
physically cut by a board edge. That ruling is worth nothing if the next routing
pass can reintroduce the defect, so it is enforced here rather than trusted.

Why a geometric gate and not a DRC severities edit: measured in ADR-142 §2, **no
.kicad_dru condition form can suppress a track-vs-edge item** — not even a
conditionless `edge_clearance (min 0.00mm)` waiver, which removes all 16 pad
items (20 -> 4) and leaves every track item intact. DRC reports these correctly.
The failure mode to prevent is therefore not "DRC missed it" but "someone reads a
count of 16 pad items as the whole story and treats the 4 track items as noise".

Exit codes: 0 clean, 1 violations found, 2 cannot run (refuses, never passes).
"""
from __future__ import annotations

import argparse
import math
import pathlib
import sys

UM = 1_000_000
SOCKET_REFS = ("J_W1", "J_W2", "J_W3", "J_W4")


def _seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def socket_edges(board):
    """Edge.Cuts segments belonging to the wing sockets, with the owning ref."""
    out = []
    cid = board.GetLayerID("Edge.Cuts")
    for ref in SOCKET_REFS:
        try:
            fp = board.FindFootprintByReference(ref)
        except Exception:
            continue
        if fp is None:
            continue
        for g in fp.GraphicalItems():
            if g.GetLayer() != cid:
                continue
            out.append((ref, g.GetStart().x / UM, g.GetStart().y / UM,
                        g.GetEnd().x / UM, g.GetEnd().y / UM))
    return out


def scan(path: pathlib.Path, min_gap: float, step: float):
    import pcbnew as k

    board = k.LoadBoard(str(path))
    edges = socket_edges(board)
    if not edges:
        return None, "no wing-socket Edge.Cuts found — refusing to report clean"

    bad = []
    for t in board.GetTracks():
        if t.Type() != k.PCB_TRACE_T:
            continue
        a, c = t.GetStart(), t.GetEnd()
        ax, ay, cx, cy = a.x / UM, a.y / UM, c.x / UM, c.y / UM
        length = math.hypot(cx - ax, cy - ay)
        n = max(2, int(length / step))
        half = t.GetWidth() / UM / 2.0
        best, where = 9e9, None
        for i in range(n + 1):
            px, py = ax + (cx - ax) * i / n, ay + (cy - ay) * i / n
            for (ref, x1, y1, x2, y2) in edges:
                d = _seg_dist(px, py, x1, y1, x2, y2) - half
                if d < best:
                    best, where = d, ref
        if best < min_gap:
            bad.append({"net": t.GetNetname(), "layer": board.GetLayerName(t.GetLayer()),
                        "socket": where, "gap_mm": round(best, 4),
                        "from": [round(ax, 3), round(ay, 3)],
                        "to": [round(cx, 3), round(cy, 3)]})
    return bad, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--min-gap", type=float, default=0.5,
                    help="required copper-to-socket-edge gap in mm (board rule is 0.50)")
    ap.add_argument("--step", type=float, default=0.02,
                    help="sampling step along each track, mm")
    a = ap.parse_args()

    path = pathlib.Path(a.board)
    if not path.exists():
        print(f"REFUSE: board not found: {path}")
        return 2
    try:
        bad, err = scan(path, a.min_gap, a.step)
    except Exception as exc:                      # noqa: BLE001
        print(f"REFUSE: cannot scan {path.name}: {exc.__class__.__name__}: {exc}")
        return 2
    if err:
        print(f"REFUSE: {err}")
        return 2
    if not bad:
        print(f"PASS: no track within {a.min_gap} mm of a wing-socket cavity edge "
              f"({path.name})")
        return 0
    print(f"FAIL: {len(bad)} track(s) too close to / across a wing-socket cavity "
          f"(ADR-142):")
    for b in bad:
        verdict = "CROSSES EDGE" if b["gap_mm"] < 0 else "too close"
        print(f"  {b['net']:14s} {b['layer']:5s} {b['socket']:5s} "
              f"gap {b['gap_mm']:+.3f} mm  {verdict}  "
              f"({b['from'][0]},{b['from'][1]})->({b['to'][0]},{b['to'][1]})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
