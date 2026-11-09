"""What is the gap between an unconnected pad and its own net's copper?

DRC says which pad fails ("Pad 21 [/F33_VSENSE] of U1 on F.Cu") but not how far the copper
stopped short. This measures it: for the named pad, find the nearest copper of the SAME net and
report the true edge-to-edge gap, not centre distance.

Edge-to-edge matters. Centre-to-centre on a 1.5 x 0.9 pad against a 0.2 track overstates the gap
by roughly half a pad diagonal, which is exactly the error that once made a 0.05 mm clearance
violation look like a 0.5 mm hole.

Usage: pad_gap.py <board> <REF> <PADNUM> <NETNAME>
"""
import math
import sys

import pcbnew

MM = 1e6


def pad_half_extent(pad, direction):
    """Distance from the pad centre to its edge along a unit direction, for a rect pad."""
    bb = pad.GetBoundingBox()
    hx = bb.GetWidth() / 2.0
    hy = bb.GetHeight() / 2.0
    # support function of an axis-aligned box along (dx, dy)
    return abs(direction[0]) * hx + abs(direction[1]) * hy


def seg_point_distance(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1), (x1, y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - cx, py - cy), (cx, cy)


def main():
    board, ref, padnum, netname = sys.argv[1:5]
    b = pcbnew.LoadBoard(board)

    pad = None
    for fp in b.GetFootprints():
        if fp.GetReference() != ref:
            continue
        for p in fp.Pads():
            if p.GetNumber() == padnum:
                pad = p
    if pad is None:
        print(f'no pad {ref}.{padnum}')
        return 1
    if pad.GetNetname() != netname:
        print(f'{ref}.{padnum} is on {pad.GetNetname()!r}, not {netname!r}')
        return 1

    pos = pad.GetPosition()
    px, py = pos.x / MM, pos.y / MM
    print(f'{ref}.{padnum} net={netname} centre=({px:.3f},{py:.3f}) '
          f'size={pad.GetSize().x / MM:.2f}x{pad.GetSize().y / MM:.2f} '
          f'layer={b.GetLayerName(pad.GetLayer())}')

    best = None
    for t in b.GetTracks():
        if t.GetNetname() != netname:
            continue
        if t.GetClass() == 'PCB_VIA':
            vp = t.GetPosition()
            vx, vy = vp.x / MM, vp.y / MM
            try:
                vw = t.GetWidth(pcbnew.UNDEFINED_LAYER)
            except Exception:
                vw = t.GetWidth()
            d = math.hypot(px - vx, py - vy) - vw / 2.0 / MM
            cand = (d, 'via', f'({vx:.2f},{vy:.2f})', b.GetLayerName(t.GetLayer()))
        else:
            s, e = t.GetStart(), t.GetEnd()
            d, (cx, cy) = seg_point_distance(px, py, s.x / MM, s.y / MM, e.x / MM, e.y / MM)
            # remove the pad's own half-extent along the approach direction
            if d > 0:
                ux, uy = (cx - px) / d, (cy - py) / d
                d -= pad_half_extent(pad, (ux, uy))
            d -= t.GetWidth() / 2.0 / MM
            cand = (d, 'track', f'({s.x / MM:.2f},{s.y / MM:.2f})->({e.x / MM:.2f},{e.y / MM:.2f})',
                    b.GetLayerName(t.GetLayer()))
        if best is None or cand[0] < best[0]:
            best = cand

    if best is None:
        print('  no other copper on this net at all')
        return 1
    d, kind, where, layer = best
    print(f'  nearest same-net copper: {kind} {where} on {layer}')
    print(f'  EDGE-TO-EDGE GAP: {d:.3f} mm')
    if d <= 0:
        print('  -> copper overlaps the pad; the unconnected record is NOT a gap '
              '(look for a zone/thermal or net-class issue instead)')
    else:
        print(f'  -> a {d:.3f} mm break. S1 track is 0.200 mm wide, clearance 0.200 mm, '
              f'so a bridge needs {d:.3f} mm of run.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
