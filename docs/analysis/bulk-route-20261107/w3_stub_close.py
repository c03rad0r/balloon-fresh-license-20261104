"""Close the 0.2828 mm connector gap the W3BRIDGE router left at its start point.

W3BRIDGE closed the real 41 mm track-to-track gap on /W3_SOLAR_N, but it terminated at
(38.550, 6.950) while the fragment it was joining ends at (38.350, 6.750). Those are exactly
0.2828 mm apart (sqrt(0.2^2 + 0.2^2)), and DRC reports that as a new unconnected record.

This adds ONE same-net 0.200 mm track across that gap and nothing else. No existing copper is
moved or deleted.

Guards, because a bare "add a track" has burned this campaign before:
  - refuses if the two endpoints are further apart than 1 mm (then this is not a stub gap)
  - refuses if the endpoints are not both /W3_SOLAR_N
  - refuses if a track between them would collide with FOREIGN copper at the S1 guard band
    using SHAPE::Collide only (SHAPE::Distance is not trustworthy on this board)
  - saves as a NEW candidate; the batch dir's routed.kicad_pcb is not modified
"""
import json
import math
import os
import shutil
import subprocess
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')

import pcbnew as p

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
B = os.path.join(ROOT, 'docs/analysis/bulk-route-20261107/batches/W3BRIDGE')
SRC = os.path.join(B, 'routed.kicad_pcb')
OUT = os.path.join(B, 'routed-stub.kicad_pcb')

NET = '/W3_SOLAR_N'
AX, AY = 38.350, 6.750        # existing fragment end
BX, BY = 38.550, 6.950        # where the bridge starts
WIDTH = 200_000               # 0.200 mm S1 track
CLEAR = 200_000
GUARD = CLEAR + 70_711        # point-sampled diagonal guard


def collide_seg_foreign(b, ax, ay, bx, by, netname):
    """True if a 0.200 mm track between the points hits FOREIGN copper at the guard band."""
    seg = p.SHAPE_SEGMENT(p.VECTOR2I(int(ax * UM), int(ay * UM)),
                          p.VECTOR2I(int(bx * UM), int(by * UM)),
                          WIDTH // 2)
    for t in b.GetTracks():
        if str(t.GetNetname()) == netname:
            continue
        if p.SHAPE.Collide(t.GetEffectiveShape(0), seg, GUARD):
            return True, 'track %s on %s' % (t.GetNetname(), b.GetLayerName(t.GetLayer()))
    for f in b.GetFootprints():
        for pad in f.Pads():
            if str(pad.GetNetname()) == netname:
                continue
            for layer in (p.F_Cu, p.B_Cu):
                if not pad.IsOnLayer(layer):
                    continue
                if p.SHAPE.Collide(pad.GetEffectiveShape(layer), seg, GUARD):
                    return True, 'pad %s.%s' % (f.GetReference(), pad.GetNumber())
    return False, ''


def main():
    d = math.hypot(BX - AX, BY - AY)
    print('gap to close: %.4f mm' % d)
    if d > 1.0:
        print('REFUSED: endpoints are %.3f mm apart, this is not a stub gap' % d)
        return 2

    b = p.LoadBoard(SRC)
    # confirm both endpoints really are /W3_SOLAR_N copper
    def net_at(x, y, tol=2000):
        pt = p.VECTOR2I(int(x * UM), int(y * UM))
        for t in b.GetTracks():
            shp = t.GetEffectiveShape(0)
            if p.SHAPE.Collide(shp, p.SHAPE_CIRCLE(pt, tol), 0):
                return str(t.GetNetname())
        for f in b.GetFootprints():
            for pad in f.Pads():
                shp = pad.GetEffectiveShape(0) if pad.IsOnLayer(p.F_Cu) else None
                if shp is None:
                    continue
                if p.SHAPE.Collide(shp, p.SHAPE_CIRCLE(pt, tol), 0):
                    return str(pad.GetNetname())
        return ''

    na = net_at(AX, AY)
    nb = net_at(BX, BY)
    print('net at A: %r   net at B: %r' % (na, nb))
    if not na or not nb:
        print('REFUSED: could not identify copper at one endpoint')
        return 2
    if na != NET or nb != NET:
        print('REFUSED: endpoints are not both %s' % NET)
        return 2

    hit, who = collide_seg_foreign(b, AX, AY, BX, BY, NET)
    print('foreign collision on the connector: %s %s' % (hit, who))
    if hit:
        print('REFUSED: connector would violate S1 clearance against %s' % who)
        return 2

    n = p.NETINFO_ITEM(b, NET)
    b.Add(n)
    t = p.PCB_TRACK(b)
    t.SetStart(p.VECTOR2I(int(AX * UM), int(AY * UM)))
    t.SetEnd(p.VECTOR2I(int(BX * UM), int(BY * UM)))
    t.SetWidth(WIDTH)
    t.SetLayer(p.F_Cu)
    t.SetNet(n)
    b.Add(t)
    print('added connector %.4f mm on F.Cu' % d)

    p.SaveBoard(OUT, b)
    print('saved', OUT)

    for ext in ('.kicad_dru', '.kicad_pro'):
        s = os.path.join(B, 'board' + ext)
        if os.path.exists(s):
            shutil.copy(s, OUT.replace('.kicad_pcb', ext))
    print('sidecars copied')
    return 0


if __name__ == '__main__':
    sys.exit(main())
