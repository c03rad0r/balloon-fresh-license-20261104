"""Close /F33_VSENSE with VIAS at coincident XY points, not a route.

Measured: the net has 4 fragments. Two pairs sit at IDENTICAL coordinates on DIFFERENT layers:
  frag1 (14.950, 6.650) B.Cu  ==  frag3 (14.950, 6.650) F.Cu
  frag1 (21.850, 8.350) B.Cu  ==  frag2 (21.850, 8.350) F.Cu
and there is NO foreign copper within 0.6 mm of either point (measured, not assumed).

So the missing link is a layer change at a point where both layers already carry this net. A via
is the correct, minimal repair. A route would be wrong even if it closed the net.

Guards:
  - both layers must already carry NET at the exact point (verified by Collide)
  - the full 0.600 mm via land must clear FOREIGN copper at the S1 rule + guard (measured)
  - via is S1: 0.600 mm land / 0.300 mm drill
  - saves a NEW candidate; the live board is not touched here
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
B = os.path.join(ROOT, 'docs/analysis/bulk-route-20261107/batches/F33VIA')
SRC = os.path.join(ROOT, 'docs/analysis/bulk-route-20261107/latest.kicad_pcb')
OUT = os.path.join(B, 'routed.kicad_pcb')

NET = '/F33_VSENSE'
SITES = [(14.950, 6.650), (21.850, 8.350)]
LAND = 600_000          # 0.600 mm land
DRILL = 300_000         # 0.300 mm drill
CLEAR = 200_000
GUARD = CLEAR + 70_711


def net_at(b, x, y, layer, tol=2000):
    pt = p.SHAPE_CIRCLE(p.VECTOR2I(int(round(x * UM)), int(round(y * UM))), tol)
    for t in b.GetTracks():
        if t.Type() != p.PCB_VIA_T and t.GetLayer() != layer:
            if t.Type() != p.PCB_VIA_T:
                continue
        try:
            if p.SHAPE.Collide(t.GetEffectiveShape(0), pt, 0):
                return str(t.GetNetname())
        except Exception:
            pass
    for f in b.GetFootprints():
        for pad in f.Pads():
            if not pad.IsOnLayer(layer):
                continue
            if p.SHAPE.Collide(pad.GetEffectiveShape(layer), pt, 0):
                return str(pad.GetNetname())
    return ''


def landing_clear(b, x, y):
    """Foreign copper that would violate the via land."""
    land = p.SHAPE_CIRCLE(p.VECTOR2I(int(round(x * UM)), int(round(y * UM))), LAND // 2)
    hits = []
    for t in b.GetTracks():
        if str(t.GetNetname()) == NET:
            continue
        if p.SHAPE.Collide(t.GetEffectiveShape(0), land, GUARD):
            hits.append('track %s/%s' % (t.GetNetname(), b.GetLayerName(t.GetLayer())))
    for f in b.GetFootprints():
        for pad in f.Pads():
            if str(pad.GetNetname()) == NET:
                continue
            for layer in (p.F_Cu, p.B_Cu):
                if not pad.IsOnLayer(layer):
                    continue
                if p.SHAPE.Collide(pad.GetEffectiveShape(layer), land, GUARD):
                    hits.append('pad %s.%s' % (f.GetReference(), pad.GetNumber()))
                    break
    return hits


def main():
    os.makedirs(B, exist_ok=True)
    shutil.copy(SRC, os.path.join(B, 'board.kicad_pcb'))
    for ext in ('.kicad_dru', '.kicad_pro'):
        s = SRC.replace('.kicad_pcb', ext)
        if os.path.exists(s):
            shutil.copy(s, os.path.join(B, 'board' + ext))
    ft = os.path.join(ROOT, 'docs/analysis/bulk-route-20261107/fp-lib-table')
    if os.path.exists(ft):
        shutil.copy(ft, os.path.join(B, 'fp-lib-table'))

    b = p.LoadBoard(SRC)
    ok_sites = []
    for (x, y) in SITES:
        nf = net_at(b, x, y, p.F_Cu)
        nb = net_at(b, x, y, p.B_Cu)
        print('site (%.3f, %.3f):  F.Cu=%r  B.Cu=%r' % (x, y, nf, nb))
        if nf != NET or nb != NET:
            print('  REFUSED: both layers must already carry %s at this point' % NET)
            return 2
        hits = landing_clear(b, x, y)
        if hits:
            print('  REFUSED: via land would violate clearance against %s' % hits[:3])
            return 2
        print('  OK: both layers carry the net, land is clear')
        ok_sites.append((x, y))

    n = b.FindNet(NET)
    if n is None:
        b.Add(p.NETINFO_ITEM(b, NET))
        n = b.FindNet(NET)
    for (x, y) in ok_sites:
        v = p.PCB_VIA(b)
        v.SetNet(n)
        v.SetPosition(p.VECTOR2I(int(round(x * UM)), int(round(y * UM))))
        v.SetWidth(LAND)
        v.SetDrill(DRILL)
        b.Add(v)
        print('added via at (%.3f, %.3f) %.3f/%.3f' % (x, y, LAND / UM, DRILL / UM))

    p.SaveBoard(OUT, b)
    b2 = p.LoadBoard(OUT)
    p.ZONE_FILLER(b2).Fill(b2.Zones())
    p.SaveBoard(OUT, b2)
    for ext in ('.kicad_dru', '.kicad_pro'):
        s = os.path.join(B, 'board' + ext)
        if os.path.exists(s):
            shutil.copy(s, OUT.replace('.kicad_pcb', ext))
    print('saved', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
