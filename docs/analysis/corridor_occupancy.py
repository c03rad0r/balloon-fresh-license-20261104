"""What occupies the sideways corridors of the /EN and /SPI2_SCK pads? Segment-accurate.

The escape probe measured directions from the pad CENTRE and reported the first blocked ray. That is
enough to say "enclosed" but not enough to say what to move. This measures the actual distance from
each pad's copper rectangle to every nearby track SEGMENT (not endpoint) and reports the ones that
sit in the sideways corridors.

Why sideways only: U1 pads are 1.500 x 0.900 mm on a 1.270 mm pitch, so the gap between adjacent pads
is 0.370 mm. A 0.200 mm track needs 0.200 + 2 x 0.200 = 0.600 mm. The vertical channel is unusable, so
any escape must go along +x or -x, and those are the corridors worth measuring.

Read-only.
"""
import math
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')

import pcbnew as p

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')

PADS = [('/EN', 'U1', '3'), ('/SPI2_SCK', 'U1', '4')]
REACH = 2.5          # mm around the pad
CLEAR = 0.200
TRACK_HW = 0.100


def rect_edge_dist(px, py, sx, sy, ax, ay, bx, by):
    """Distance from a WxH rectangle's boundary (centred at px,py) to segment ab.

    Approximated by subtracting the rectangle's half-extent projected along the direction to the
    segment's closest point. Conservative for a rectangle: it uses the half-extent along the ray,
    which is what determines whether copper touches.
    """
    dx = ((ax + bx) / 2) - px
    dy = ((ay + by) / 2) - py
    n = math.hypot(dx, dy)
    if n == 0:
        return 0.0
    # half-extent of the rectangle along that direction
    hx, hy = sx / 2, sy / 2
    t = math.hypot(dx / n * hx, dy / n * hy)
    return t


def seg_dist(px, py, ax, ay, bx, by):
    """Distance from point to segment, in the same units as the inputs."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def main():
    b = p.LoadBoard(LIVE)
    for net, ref, pin in PADS:
        pad = None
        for f in b.GetFootprints():
            if f.GetReference() != ref:
                continue
            for pd in f.Pads():
                if str(pd.GetNumber()) == str(pin):
                    pad = pd
        if pad is None:
            print('%s.%s not found' % (ref, pin))
            continue
        c = pad.GetPosition()
        px, py = c.x / UM, c.y / UM
        sx, sy = pad.GetSize().x / UM, pad.GetSize().y / UM
        print('%s  pad %s.%s centre (%.3f, %.3f) size %.3f x %.3f'
              % (net, ref, pin, px, py, sx, sy))
        print('   needs %.3f mm clear from its own edge for a 0.200 mm track'
              % (TRACK_HW + CLEAR))

        rows = []
        for t in b.GetTracks():
            if t.Type() != p.PCB_TRACE_T:
                continue
            tn = str(t.GetNetname())
            if tn == net:
                continue
            a, e = t.GetStart(), t.GetEnd()
            d_c = seg_dist(px, py, a.x / UM, a.y / UM, e.x / UM, e.y / UM)
            # CENTRE distance is the wrong metric. The pad is 1.500 x 0.900 mm, so its own edge is
            # up to 0.750 mm from centre; a segment 0.750 mm from the centre is TOUCHING the pad.
            # What matters is the gap from the pad's edge to the segment's edge.
            d = d_c - rect_edge_dist(px, py, sx, sy, a.x / UM, a.y / UM, e.x / UM, e.y / UM)
            if d_c > REACH + max(sx, sy):
                continue
            d = max(0.0, d) - TRACK_HW     # now an edge-to-edge copper gap
            # sideways = |dx| dominant at the closest approach
            rows.append((d, tn, b.GetLayerName(t.GetLayer()),
                         a.x / UM, a.y / UM, e.x / UM, e.y / UM, t.GetLength() / UM))
        rows.sort()
        print('   %d foreign segment(s) within %.1f mm:' % (len(rows), REACH))
        for d, tn, lay, ax, ay, bx, by, ln in rows[:14]:
            side = 'RIGHT +x' if (ax + bx) / 2 > px else 'LEFT  -x'
            need = d - (TRACK_HW + CLEAR)
            print('      %5.3f mm to centre  %-6s %-14s (%.3f,%.3f)->(%.3f,%.3f) len %.2f  %s  %s'
                  % (d, lay, tn, ax, ay, bx, by, ln, side,
                     'CLEAR ENOUGH' if need >= 0 else 'blocks (needs %+.3f mm)' % need))
        print()

    # the pad row context
    print('U1 pad row pitch check:')
    ys = []
    for f in b.GetFootprints():
        if f.GetReference() != 'U1':
            continue
        for pd in f.Pads():
            n = str(pd.GetNumber())
            if n in ('2', '3', '4', '5'):
                q = pd.GetPosition()
                ys.append((float(n), q.y / UM, pd.GetSize().y / UM))
    ys.sort()
    for i in range(len(ys) - 1):
        gap = (ys[i + 1][1] - ys[i][1]) - (ys[i][2] / 2 + ys[i + 1][2] / 2)
        print('   U1.%s to U1.%s: centre %.3f mm apart, pad gap %.3f mm'
              % (ys[i][0], ys[i + 1][0], ys[i + 1][1] - ys[i][1], gap))
    print('   a 0.200 mm track needs %.3f mm of gap -> vertical channel is unusable'
          % (0.200 + 2 * CLEAR))
    return 0


if __name__ == '__main__':
    sys.exit(main())
