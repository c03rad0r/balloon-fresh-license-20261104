#!/usr/bin/env python3
"""Measure label collisions in the generated schematic from the layout model itself.

KiCad's SVG export draws text as stroked paths, so there is no text to parse out of a render
and no way to "see" a collision in a picture at sheet scale. This measures the labels the
generator actually emitted, using the same coordinates, and reports every pair of net labels
whose bounding boxes intersect. It is the legibility gate for this milestone.

Run: /usr/bin/python3 verify_label_layout.py [--verbose]
Exit 0 == no two net labels overlap. Exit 1 == collisions, listed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCH = HERE / "base_station_v1.kicad_sch"
MAP = HERE / "symbol-mapping.json"

CHAR_W = 1.0        # conservative mm per character at 1.27 mm font
TEXT_H = 1.6


def sheet_body(text):
    """The schematic text with the (lib_symbols ...) block removed.

    Library symbol definitions carry their own Reference/Value properties at local
    coordinates around (0, 0). Those are templates, not text on the sheet; leaving them in
    made every symbol appear to collide with every other symbol at the origin.
    """
    start = text.index("(lib_symbols")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[:start] + text[i + 1:]
    raise SystemExit("REFUSED: (lib_symbols block is unterminated; cannot isolate the sheet")


def labels():
    """[(text, kind, x, y, rot, justify, box)] for every net label AND caption on the sheet."""
    text = sheet_body(SCH.read_text())
    out = []
    for m in re.finditer(r'\(label "([^"]+)" \(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*'
                         r'\(effects \(font \(size 1.27 1.27\)\) \(justify (\w+) bottom\)\)',
                         text):
        net, x, y, rot, just = m.group(1), float(m.group(2)), float(m.group(3)), \
            int(float(m.group(4))), m.group(5)
        out.append((net, "label", x, y, rot, just, _box(net, x, y, rot, just)))
    # Reference and Value captions are centred on their (at) point and were the last thing
    # still colliding with the vertical supply labels; measure them too.
    for m in re.finditer(r'\(property "(Reference|Value)" "([^"]*)" \(at ([-\d.]+) ([-\d.]+) '
                         r'[-\d.]+\)\s*\(effects \(font \(size 1\.27 1\.27\)\)\)', text):
        prop, txt, x, y = m.group(1), m.group(2), float(m.group(3)), float(m.group(4))
        if not txt or txt.endswith(".pretty") or "/" in txt:
            continue  # Footprint properties are hidden
        w, h = len(txt) * CHAR_W, TEXT_H
        out.append((txt, prop, x, y, 0, "center",
                    (x - w / 2, x + w / 2, y - TEXT_H / 2, y + TEXT_H / 2)))
    return out


def _box(text, x, y, rot, just):
    w, h = len(text) * CHAR_W, TEXT_H
    if rot % 180 == 90:
        w, h = h, w
    if rot % 180 == 90:
        # a 90-degree label grows UP from its anchor when justified left, DOWN when right
        y0 = y - h if just == "left" else y
        return (x - TEXT_H / 2, x + TEXT_H / 2, y0, y0 + h)
    x0 = x if just == "left" else x - w
    return (x0, x0 + w, y - TEXT_H, y)


def overlaps(a, b, tol=0.05):
    ax0, ax1, ay0, ay1 = a
    bx0, bx1, by0, by1 = b
    return (ax0 + tol < bx1 and bx0 + tol < ax1
            and ay0 + tol < by1 and by0 + tol < ay1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if not SCH.exists():
        print(f"REFUSED: no schematic at {SCH}")
        return 2
    ls = labels()
    if not ls:
        print("REFUSED: parsed 0 labels -- the schematic format changed and this gate is blind")
        return 2
    bad = []
    for i in range(len(ls)):
        for j in range(i + 1, len(ls)):
            if overlaps(ls[i][6], ls[j][6]):
                bad.append((ls[i][0], ls[j][0], ls[i][1], ls[j][1],
                            round(ls[i][2], 2), round(ls[i][3], 2),
                            round(ls[j][2], 2), round(ls[j][3], 2)))
    print(f"text items measured : {len(ls)}")
    print(f"colliding pairs     : {len(bad)}")
    if bad:
        for b in bad[:25]:
            print(f"   COLLIDE  {b[0]:<18} ({b[2]}) vs {b[1]:<18} ({b[3]}) "
                  f"at ({b[4]},{b[5]}) / ({b[6]},{b[7]})")
        if len(bad) > 25:
            print(f"   ... {len(bad) - 25} more")
        print("LAYOUT: FAIL -- text overlaps; a reviewer cannot read this sheet")
        return 1
    if args.verbose:
        for txt, kind, x, y, rot, just, box in sorted(ls, key=lambda r: (r[3], r[2]))[:40]:
            print(f"   {txt:<18} {kind:<9} at ({x:7.2f},{y:7.2f}) rot {rot:3d} {just:<6} {box}")
    print("LAYOUT: PASS -- no net label or caption overlaps another")
    return 0


if __name__ == "__main__":
    sys.exit(main())
