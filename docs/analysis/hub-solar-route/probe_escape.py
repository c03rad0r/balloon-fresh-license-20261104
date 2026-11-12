#!/usr/bin/env python3
"""Escape-width probe: for a pad on B.Cu, how wide a track can leave it?

For each heading in 1-degree steps we walk a ray 8 mm out from the pad centre and
measure its distance to every foreign B.Cu item (buffered by the 0.20 mm rule).
The achievable track width for that heading is 2*distance - 0.20. If the best
heading over all 360 degrees is below the 0.20 mm design minimum, no legal route
can leave the pad at all, and the non-convergence is a property of the board
geometry rather than of the router.

This is a measurement, not a router: it exists to explain a non-convergence with
numbers instead of the word "blocked".
"""
import math
import sys

import pcbnew as k
from shapely.geometry import LineString

sys.path.insert(0, '/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/solar-fix')
import route2 as R  # noqa: E402


def mm(v):
    return v / 1e6


def probe(b, ref, num, net):
    fp = b.FindFootprintByReference(ref)
    pads = [p for p in fp.Pads() if p.GetNumber() == num
            and p.IsOnLayer(b.GetLayerID('B.Cu'))]
    p = pads[0]
    bb = p.GetBoundingBox()
    cx, cy = (mm(bb.GetLeft()) + mm(bb.GetRight())) / 2, \
             (mm(bb.GetTop()) + mm(bb.GetBottom())) / 2
    half = max(mm(bb.GetWidth()), mm(bb.GetHeight())) / 2
    bad = R.forbidden(b, net, 'B.Cu')
    rows = []
    for deg in range(0, 360, 1):
        th = math.radians(deg)
        start = (cx + half * math.cos(th), cy + half * math.sin(th))
        end = (cx + 8.0 * math.cos(th), cy + 8.0 * math.sin(th))
        d = LineString([start, end]).distance(bad)
        rows.append((2 * d - R.CLEAR, deg, d))
    rows.sort(reverse=True)
    best = rows[0]
    n_ok = sum(1 for r in rows if r[0] >= 0.20)
    print(f'{ref}.{num} [{net}] B.Cu centre ({cx:.3f},{cy:.3f}) '
          f'land {mm(bb.GetWidth()):.2f} x {mm(bb.GetHeight()):.2f} mm')
    print(f'  widest legal track leaving this land: {best[0]:.3f} mm '
          f'at heading {best[1]} deg  (rule-buffered clearance {best[2]:.3f} mm)')
    print(f'  headings able to carry a 0.20 mm track: {n_ok} of 360')
    for slack, deg, d in rows[:4]:
        print(f'    heading {deg:3d} deg  max width {slack:+.3f} mm')
    print()
    return best[0], n_ok


b = k.LoadBoard(str(R.SRC / (R.STEM + '.kicad_pcb')))
print('--- control: a land whose pair DID route ---')
probe(b, 'D_BP1', '2', '/W1_SOLAR_N')
probe(b, 'J_W1', '4', '/W1_SOLAR_N')
print('--- lands whose pairs did NOT route ---')
probe(b, 'J_W4', '1', '/W3_SOLAR_N')
probe(b, 'D_BP4', '1', '/W3_SOLAR_N')
probe(b, 'D_BP3', '2', '/W3_SOLAR_N')
print('--- land whose pair routed only when it was the ONLY new track ---')
probe(b, 'D_BP2', '1', '/W1_SOLAR_N')
