#!/usr/bin/env python3
"""Verify a claim about a board PLOT by measurement, not by eye.

Two independent measurements:
  1. same-layer silk text proximity  — every visible silk text pair closer than --tol mm, with the
     layer named, so a "these labels collide" claim resolves to specific refs and a distance.
  2. reference-to-part distance      — how far each visible designator sits from its own footprint
     body. A label parked in the board margin is unreadable by an assembler but violates no DRC rule,
     and no gate in this repo reports it.
  3. ink coverage per NxN cell of a plotted PNG, so a "this region looks unrouted" claim becomes a
     number instead of an impression.

Usage: verify_visual_claims.py <board.kicad_pcb> [plot.png ...] [--tol 0.15] [--grid 8]
"""
import argparse
import itertools
import sys
from collections import Counter

import pcbnew

UM = 1_000_000.0


def visible_silk_texts(board):
    b = pcbnew.LoadBoard(board)
    items = []
    for fp in b.GetFootprints():
        for kind, f in (("ref", fp.Reference()), ("val", fp.Value())):
            if f.IsVisible() and "Silkscreen" in f.GetLayerName():
                items.append((fp.GetReference(), kind, f.GetText(), f.GetLayerName(),
                              f.GetBoundingBox()))
        for g in fp.GraphicalItems():
            if g.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX") and "Silkscreen" in g.GetLayerName():
                items.append((fp.GetReference(), "user", g.GetText(), g.GetLayerName(),
                              g.GetBoundingBox()))
    for d in b.GetDrawings():
        if d.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX") and "Silkscreen" in d.GetLayerName():
            items.append(("BOARD", "board", d.GetText(), d.GetLayerName(), d.GetBoundingBox()))
    return b, items


def box_gap(a, c):
    """Signed gap in mm between two boxes: >0 separated, <0 overlapping on both axes."""
    dx = max(a.GetLeft() - c.GetRight(), c.GetLeft() - a.GetRight()) / UM
    dy = max(a.GetTop() - c.GetBottom(), c.GetTop() - a.GetBottom()) / UM
    return max(dx, dy)


def part_gap(reference_field, footprint_box):
    f = reference_field.GetBoundingBox()
    dx = max(footprint_box.GetLeft() - f.GetRight(), f.GetLeft() - footprint_box.GetRight()) / UM
    dy = max(footprint_box.GetTop() - f.GetBottom(), f.GetTop() - footprint_box.GetBottom()) / UM
    return max(dx, dy)


def ink_grid(png, n):
    from PIL import Image
    im = Image.open(png).convert("RGB")
    W, H = im.size
    px = im.load()
    rows = []
    for gy in range(n):
        row = []
        for gx in range(n):
            x0, x1 = gx * W // n, (gx + 1) * W // n
            y0, y1 = gy * H // n, (gy + 1) * H // n
            ink = tot = 0
            for y in range(y0, y1, 3):
                for x in range(x0, x1, 3):
                    r, g, bl = px[x, y]
                    tot += 1
                    if r < 230 or g < 230 or bl < 230:
                        ink += 1
            row.append(ink / max(tot, 1))
        rows.append(row)
    return W, H, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("plots", nargs="*")
    ap.add_argument("--tol", type=float, default=0.15)
    ap.add_argument("--grid", type=int, default=8)
    ap.add_argument("--detached-mm", type=float, default=2.0)
    a = ap.parse_args()

    b, items = visible_silk_texts(a.board)
    print(f"visible silk texts: {len(items)}  "
          f"{dict(Counter(i[3] for i in items))}")

    for layer in ("F.Silkscreen", "B.Silkscreen"):
        sub = [i for i in items if i[3] == layer]
        close = []
        for x, y in itertools.combinations(sub, 2):
            g = box_gap(x[4], y[4])
            if g < a.tol:
                close.append((round(g, 3), x[0], x[2], y[0], y[2]))
        close.sort()
        print(f"\n{layer}: {len(sub)} texts; pairs closer than {a.tol} mm: {len(close)}")
        for c in close[:12]:
            print(f"   {c[0]:+.3f} mm  {c[1]} {c[2]!r}  <->  {c[3]} {c[4]!r}")

    print(f"\nreference-to-own-part distance (flag > {a.detached_mm} mm):")
    rows = []
    for fp in b.GetFootprints():
        f = fp.Reference()
        if not (f.IsVisible() and "Silkscreen" in f.GetLayerName()):
            continue
        rows.append((round(part_gap(f, fp.GetBoundingBox(False, False)), 2),
                     fp.GetReference(), f.GetLayerName()))
    rows.sort(reverse=True)
    detached = 0
    for g, r, lay in rows:
        if g > a.detached_mm:
            detached += 1
            print(f"   {g:+7.2f} mm  {r:<12} {lay}   DETACHED")
    print(f"   visible references: {len(rows)}   detached: {detached}")

    for png in a.plots:
        W, H, rows_ink = ink_grid(png, a.grid)
        flat = [v for row in rows_ink for v in row]
        print(f"\nink coverage per {a.grid}x{a.grid} cell of {png} ({W}x{H}):")
        for gy, row in enumerate(rows_ink):
            print(f"   row {gy}: " + " ".join(f"{v * 100:5.1f}%" for v in row))
        print(f"   mean {sum(flat) / len(flat) * 100:.1f}%  "
              f"min {min(flat) * 100:.1f}%  max {max(flat) * 100:.1f}%")
        empty = [(gx, gy, round(rows_ink[gy][gx] * 100, 1))
                 for gy in range(a.grid) for gx in range(a.grid) if rows_ink[gy][gx] < 0.12]
        print(f"   cells below 12% ink: {len(empty)} -> {empty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
