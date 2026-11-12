#!/usr/bin/env python3
"""Measure the base-station board's real area demand before choosing an outline.

TWO BUGS FIXED HERE, both of which made the earlier numbers useless:

1. `placer.hubgen` does not exist -- it is `placer._hubgen()`. The outline trials therefore crashed
   and nobody saw the answer.

2. `fp.GetBoundingBox()` was used for part extent, but a footprint's bounding box INCLUDES its
   reference text. Measured: a 0402 capacitor reported 6.68 x 4.02 mm, which is the designator
   "C_RP_23" plus its pad, not the part. That inflated the total to 8353 mm2 and produced a
   recommendation of 118 x 118 mm for a board whose parts need a third of that.

Part extent is now the union of PADS + F.Fab/Silkscreen/Courtyard graphics -- the physical part --
with reference text excluded. The designator still needs somewhere to go, so it is reported
separately rather than folded into the part.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

spec = importlib.util.spec_from_file_location("placer", os.path.join(HERE, "place_base_station.py"))
placer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(placer)


def body_rect(fp):
    """The physical part: pads plus fab/silk/courtyard graphics. NOT the reference text."""
    xs, ys, xe, ye = [], [], [], []
    for p in fp.Pads():
        r = p.GetBoundingBox()
        xs.append(r.GetLeft()); ys.append(r.GetTop())
        xe.append(r.GetRight()); ye.append(r.GetBottom())
    for g in fp.GraphicalItems():
        if pcbnew.LayerName(g.GetLayer()) in ("F.Fab", "F.Silkscreen", "F.CrtYd"):
            r = g.GetBoundingBox()
            xs.append(r.GetLeft()); ys.append(r.GetTop())
            xe.append(r.GetRight()); ye.append(r.GetBottom())
    if not xs:
        return None
    return (min(xs) / 1e6, min(ys) / 1e6, max(xe) / 1e6, max(ye) / 1e6)


board, placed, skipped, comps, nets = placer.load(120.0, 120.0)

print(f"{'ref':<14} {'w mm':>7} {'h mm':>7} {'area mm2':>9}  value")
print("-" * 76)
rows = []
for ref, fp in placed:
    r = body_rect(fp)
    if r is None:
        continue
    w, h = r[2] - r[0], r[3] - r[1]
    rows.append((w * h, ref, w, h, fp.GetValue()))

tot = 0.0
for area, ref, w, h, val in sorted(rows, reverse=True):
    tot += area
    print(f"{ref:<14} {w:>7.2f} {h:>7.2f} {area:>9.1f}  {str(val)[:32]}")
print("-" * 76)
print(f"{'TOTAL body area':<14} {tot:>25.1f} mm2   ({len(rows)} parts, {len(skipped)} unplaceable)")
print(f"packing efficiency ~60% -> need ~{tot / 0.6:.0f} mm2 usable")
print(f"  square: {(tot / 0.6) ** 0.5:.0f} x {(tot / 0.6) ** 0.5:.0f} mm")
print()

rects = [body_rect(fp) for _, fp in placed]
rects = [r for r in rects if r]
xs0 = min(r[0] for r in rects); ys0 = min(r[1] for r in rects)
xs1 = max(r[2] for r in rects); ys1 = max(r[3] for r in rects)
print(f"placed parts span {xs1 - xs0:.2f} x {ys1 - ys0:.2f} mm "
      f"(x {xs0:.2f}..{xs1:.2f}, y {ys0:.2f}..{ys1:.2f}) at a 120x120 outline")
print()

print("=== outline trials (does everything seat?) ===")
for outline in ("50x30", "56x30", "60x32", "60x45", "70x50"):
    w, h = (float(v) for v in outline.split("x"))
    b2, p2, s2, c2, n2 = placer.load(w, h)
    overflow = placer._hubgen().pack_rest(b2, p2, [], w, h)
    n_over = len(overflow) if overflow else 0
    tag = "ALL SEATED" if not n_over else str(overflow[:6])
    print(f"  {outline:>8}: {len(p2)} placed, {n_over} overflow   {tag}")
