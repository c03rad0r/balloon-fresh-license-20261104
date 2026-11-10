#!/usr/bin/env python3
"""Compare two Gerber/Excellon exports as GEOMETRY SETS, not as text.

Gerber tool numbers (D10, D11...) and the ORDER of flashes are not part of the
artwork: KiCad renumbers apertures and reorders flashes between runs and between
builds without changing a single feature. A text diff therefore reports a change
that does not exist, and — worse — buries a real one.

This tool normalises each file to a sorted multiset of (aperture, x, y) features
and compares those. Exit 0 = same artwork.

    python3 tools/gerber_geom_diff.py DIR_A DIR_B [--quiet]
"""
import argparse
import os
import re
import sys

APERTURE_RE = re.compile(r'%ADD(\d+)([^,*]+),?([^*]*)\*%')
FLASH_RE = re.compile(r'^(?:X(-?\d+))?(?:Y(-?\d+))?D03\*$')
DRAW_RE = re.compile(r'^(?:X(-?\d+))?(?:Y(-?\d+))?D0([12])\*$')
TOOL_RE = re.compile(r'^D(\d+)\*$')


def parse_excellon(path):
    """Normalise an Excellon drill file to a sorted list of ('hole', dia, x, y).

    A bare `Tn` line SELECTS a tool; `TnCd` DEFINES one. Getting that backwards is
    how an earlier parser in this project reported 0 holes at 0.200 mm when there
    were 12.
    """
    tools, feats, cur = {}, [], None
    for raw in open(path, errors='replace'):
        line = raw.strip()
        if not line or line.startswith(';'):
            continue
        m = re.match(r'^T(\d+)(?:C([0-9.]+))?$', line)
        if m:
            if m.group(2) is not None:
                tools[m.group(1)] = m.group(2)
            else:
                cur = tools.get(m.group(1), f'?{m.group(1)}')
            continue
        m = re.match(r'^X(-?[0-9.]+)Y(-?[0-9.]+)', line)
        if m:
            feats.append(('hole', cur, m.group(1), m.group(2)))
    return sorted(feats, key=repr)


def parse(path):
    """Return a sorted list of normalised features.

    A feature is ('flash', aperture_spec, x, y) or ('draw', aperture_spec,
    x0, y0, x1, y1). Coordinates are kept as the integer strings KiCad emits so
    no precision is lost to float formatting. Excellon drill files have their
    own grammar and are normalised to ('hole', dia, x, y).
    """
    if path.lower().endswith('.drl'):
        return parse_excellon(path)
    apertures = {}
    feats = []
    tool = None
    last = None
    for raw in open(path, errors='replace'):
        line = raw.strip()
        if not line or line.startswith('G04'):
            continue
        m = APERTURE_RE.match(line)
        if m:
            apertures[m.group(1)] = (m.group(2) + m.group(3)).strip()
            continue
        m = TOOL_RE.match(line)
        if m:
            tool = apertures.get(m.group(1), f'?{m.group(1)}')
            continue
        m = FLASH_RE.match(line)
        if m:
            feats.append(('flash', tool, m.group(1) or '', m.group(2) or ''))
            continue
        m = DRAW_RE.match(line)
        if m:
            x, y, op = m.group(1) or '', m.group(2) or '', m.group(3)
            if op == '2':
                last = (x, y)
                continue
            if last is not None:
                feats.append(('draw', tool, last[0], last[1], x, y))
                last = (x, y)
            continue
        if line.startswith('M02'):
            break
    return sorted(feats, key=repr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--ext', default='.gtl,.gbl,.gts,.gbs,.gto,.gbo,.gtp,.gbp,.gm1,.drl')
    args = ap.parse_args()

    exts = tuple(args.ext.split(','))
    names = sorted({f for f in os.listdir(args.a) if f.endswith(exts)} |
                   {f for f in os.listdir(args.b) if f.endswith(exts)})
    bad = 0
    for name in names:
        pa, pb = os.path.join(args.a, name), os.path.join(args.b, name)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print(f'  {name:<40} ONLY IN {"B" if os.path.exists(pb) else "A"}')
            bad += 1
            continue
        fa, fb = parse(pa), parse(pb)
        if fa == fb:
            if not args.quiet:
                print(f'  {name:<40} same artwork ({len(fa)} features)')
        else:
            aa, bb = set(fa), set(fb)
            print(f'  {name:<40} DIFFERS: {len(bb - aa)} only in B, {len(aa - bb)} only in A')
            for f in sorted(bb - aa, key=repr)[:6]:
                print(f'      +B {f}')
            for f in sorted(aa - bb, key=repr)[:6]:
                print(f'      -A {f}')
            bad += 1
    print(f'VERDICT: {"SAME ARTWORK" if bad == 0 else f"{bad} file(s) differ"}')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
