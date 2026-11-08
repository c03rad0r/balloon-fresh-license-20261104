"""Edge-to-edge copper gap from each U1 pad to every nearby track, via Collide bisection.

The previous version measured CENTRE distance and then subtracted an approximate rectangle
half-extent. Both are wrong for long segments: a 7.6 mm track's midpoint can be far from its closest
approach to the pad. Measured consequence: it printed "CLEAR ENOUGH" for segments that in fact touch
the pad's clearance envelope.

Correct method, and the only one that has proven reliable on this board:
  build the real SHAPE_SEGMENT for the track (its own width included),
  bisect the smallest separation at which SHAPE::Collide(pad_shape, track_shape, sep) turns False,
  report that separation as the edge-to-edge copper gap.
No SHAPE::Distance (measured 0.335 mm reported where the true gap was 0.100 mm).

A 0.200 mm track needs a 0.200 mm gap to foreign copper. Anything below that blocks.
"""
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')

import pcbnew as p

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')

PADS = [('/EN', 'U1', '3'), ('/SPI2_SCK', 'U1', '4')]
SCAN = 2_000_000          # 2 mm search box, in nm
CLEAR = 200_000
TRACK = 200_000          # the NEW track's own width -- it must fit in the space too


def gap(pad_shape, other_shape):
    """Edge-to-edge copper gap in nm, or None if wider than SCAN.

    SHAPE::Collide(a, b, s) is TRUE when the shapes are closer than s. So:
      Collide(..., 0) true   -> they physically overlap (gap 0)
      Collide(..., s) true   -> gap < s
    Bisect the smallest s at which it stops being a collision; that s IS the gap.
    The previous version tested Collide(...,0) and returned None when it was FALSE, which threw
    away every object that was merely NEAR the pad -- it reported 0 neighbours on a pad the escape
    probe had just shown to be enclosed at 0.4 mm.
    """
    if p.SHAPE.Collide(other_shape, pad_shape, 0):
        return 0                       # touching / overlapping
    lo, hi = 0, SCAN                   # lo: no collision, hi: unknown
    if not p.SHAPE.Collide(other_shape, pad_shape, hi):
        return None                    # gap >= SCAN
    for _ in range(24):
        mid = (lo + hi) // 2
        if p.SHAPE.Collide(other_shape, pad_shape, mid):
            hi = mid
        else:
            lo = mid
    return hi


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
            continue
        ps = pad.GetEffectiveShape(p.F_Cu)
        c = pad.GetPosition()
        print('%s  pad %s.%s  (%.3f, %.3f)  %.3f x %.3f'
              % (net, ref, pin, c.x / UM, c.y / UM,
                 pad.GetSize().x / UM, pad.GetSize().y / UM))
        # A NEW 0.200 mm track placed between the pad and an existing track needs
        #   0.200 mm clearance + 0.200 mm of its own width = 0.400 mm of space between the two
        # existing coppers. Reporting "clear by (gap - 0.200)" was an ARITHMETIC ERROR: it ignored
        # the new track's own width and declared a 0.350 mm corridor clear when it is 0.050 mm short.
        # The router's NO PATH was right and my metric was wrong.
        print('   a new 0.200 mm track needs %.3f mm between existing coppers '
              '(0.200 clearance + 0.200 width)' % ((CLEAR + TRACK / 1) / UM))

        rows = []
        for t in b.GetTracks():
            if t.Type() != p.PCB_TRACE_T:
                continue
            tn = str(t.GetNetname())
            if tn == net:
                continue
            # ONLY same-layer copper blocks an F.Cu escape. A B.Cu track is not an obstacle for a
            # track on F.Cu, and including it produced false 0.000 mm "BLOCKS" rows for /F33_IRQ.
            if t.GetLayer() != p.F_Cu:
                continue
            g = gap(ps, t.GetEffectiveShape(0))
            if g is None:
                continue
            a, e = t.GetStart(), t.GetEnd()
            rows.append((g, tn, b.GetLayerName(t.GetLayer()),
                         a.x / UM, a.y / UM, e.x / UM, e.y / UM))
        rows.sort()
        print('   %d segment(s) within %.1f mm of the pad copper:' % (len(rows), SCAN / UM))
        for g, tn, lay, ax, ay, bx, by in rows[:12]:
            side = 'RIGHT +x' if (ax + bx) / 2 > c.x / UM else 'LEFT  -x'
            need = CLEAR + 200_000
            verdict = ('BLOCKS, short by %.3f' % ((need - g) / UM)) if g < need \
                else ('clear by %+.3f' % ((g - need) / UM))
            print('      %6.3f mm  %-6s %-14s (%.3f,%.3f)->(%.3f,%.3f)  %-10s %s'
                  % (g / UM, lay, tn, ax, ay, bx, by, side, verdict))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
