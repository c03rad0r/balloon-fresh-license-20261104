#!/usr/bin/env python3
"""check_hv_lanes.py -- H/V lane discipline gate (ADR-143).

Direction is assigned by STACK POSITION, never by KiCad layer ID. On the boards in this project
every copper layer carries an even ID (F.Cu=0, B.Cu=2, In1=4, In2=6), so an "odd/even layer
number" rule assigns all four layers the same direction and is inert.

  F.Cu = horizontal    In1.Cu = vertical    In2.Cu = horizontal    B.Cu = vertical

MODES
  default   report-only. Prints conformance per layer and the worst offenders, exits 0.
            This is the only safe default: the board it was written against conforms at 50.5 %,
            so a blocking gate would refuse every commit on day one (ADR-143 section 3).
  --strict  exit 1 when conformance is below --min. Use on a FRESH layout, or per-board once a
            baseline file records the achieved figure.
  --min N   threshold for --strict (default 90.0).

EXEMPTION, and it is part of the rule: segments shorter than --escape (default 1.5 mm) are pad
exits and bends. They are never H or V and a rule without this clause flags every fanout --
measured: 1018 such segments exist on the reference board.

Usage:
    check_hv_lanes.py BOARD [--strict] [--min 90] [--escape 1.5] [--verbose]
"""
from __future__ import annotations

import argparse
import collections
import math
import sys

import pcbnew

UM = 1e6
TOL = 22.5              # degrees from axis

# stack position -> direction. Keyed by NAME so a renamed layer cannot silently change meaning.
DIR_BY_NAME = {
    "F.Cu": "H",
    "In1.Cu": "V",
    "In2.Cu": "H",
    "B.Cu": "V",
}


def classify(ax, ay, bx, by, escape_mm):
    """Return (kind, length_mm, angle_deg) for one track."""
    length = math.hypot(bx - ax, by - ay)
    if length <= 0:
        return None, 0.0, 0.0
    ang = math.degrees(math.atan2(abs(by - ay), abs(bx - ax)))   # 0 = horizontal
    if length < escape_mm:
        return "escape", length, ang
    if ang <= TOL:
        return "H", length, ang
    if ang >= 90 - TOL:
        return "V", length, ang
    return "DIAG", length, ang


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 below --min; default is report-only")
    ap.add_argument("--min", type=float, default=90.0)
    ap.add_argument("--escape", type=float, default=1.5,
                    help="mm; segments shorter than this are exempt (pad exits, bends)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    b = pcbnew.LoadBoard(a.board)
    if b is None:
        print(f"REFUSED: cannot load {a.board}")
        return 2

    per = collections.defaultdict(lambda: collections.Counter())
    worst = collections.defaultdict(list)

    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) or not isinstance(t, pcbnew.PCB_TRACK):
            continue
        name = b.GetLayerName(t.GetLayer())
        if name not in DIR_BY_NAME:
            continue
        ax, ay = t.GetStart().x / UM, t.GetStart().y / UM
        bx, by = t.GetEnd().x / UM, t.GetEnd().y / UM
        kind, length, ang = classify(ax, ay, bx, by, a.escape)
        if kind is None:
            continue
        per[name][kind] += 1
        if kind in ("H", "V") and kind != DIR_BY_NAME[name]:
            worst[name].append((round(length, 2), round(ang, 1),
                                round(ax, 2), round(ay, 2)))

    print(f"board: {a.board}")
    print(f"rule: F.Cu=H  In1.Cu=V  In2.Cu=H  B.Cu=V   "
          f"(+/-{TOL} deg, exempt < {a.escape} mm)\n")
    print(f"{'layer':8s} {'want':>4s} {'H':>5s} {'V':>5s} {'DIAG':>5s} {'escape':>6s} "
          f"{'conforms':>9s}")

    ok = checked = 0
    below = []
    for name in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
        c = per.get(name)
        if not c:
            print(f"{name:8s} {DIR_BY_NAME[name]:>4s} {'-':>5s} {'-':>5s} {'-':>5s} "
                  f"{'-':>6s} {'(no tracks)':>9s}")
            continue
        want = DIR_BY_NAME[name]
        good = c["H"] if want == "H" else c["V"]
        n = c["H"] + c["V"] + c["DIAG"]
        ok += good
        checked += n
        pct = (good / n * 100) if n else 100.0
        print(f"{name:8s} {want:>4s} {c['H']:5d} {c['V']:5d} {c['DIAG']:5d} "
              f"{c['escape']:6d} {pct:8.1f}%")
        if n and pct < a.min:
            below.append((name, pct))

    total = (ok / checked * 100) if checked else 100.0
    print(f"\nwhole board: {ok}/{checked} = {total:.1f}%   (threshold {a.min:.0f}%)")

    if a.verbose:
        for name, items in worst.items():
            items.sort(reverse=True)
            print(f"\nworst offenders on {name} (want {DIR_BY_NAME[name]}):")
            for length, ang, x, y in items[:8]:
                print(f"  {length:6.2f} mm at {ang:5.1f} deg  near ({x},{y})")

    if a.strict:
        if total < a.min:
            print(f"\nFAIL: {total:.1f}% < {a.min:.0f}%. "
                  f"Layers below threshold: {[f'{n} {p:.1f}%' for n, p in below]}")
            return 1
        print("\nPASS")
        return 0

    print("\nreport-only: no exit code set (ADR-143 ships this in warn mode). "
          "Use --strict on a fresh layout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
