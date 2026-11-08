"""Can /W3_SOLAR_N close WITHOUT the J_W4 socket-edge violation?

STATE. Board 322ade1e, 11 opens. /W3_SOLAR_N is the one open with a KNOWN route: freerouting closed it,
but its In2.Cu leg runs 0.066 mm and 0.407 mm from the J_W4 wing-socket cavity against the 0.50 mm rule
(AGENTS.md 13a, ADR-142: no track within 0.5 mm of, or across, a wing-socket cavity edge).

So this is not "find a path" -- the path is known. It is "move 0.5 mm off a cavity" for a route whose
pads are two-face wing pads.

STEP 1: measure the J_W4 cavity geometry exactly -- where the cavity edges actually are, so a valid
        offset is computed rather than guessed.

STEP 2: measure what /W3_SOLAR_N looks like on the live board: fragments, layers, endpoints, and how
        far each pad is from the cavity.

STEP 3: decide the cheapest legal option:
        (a) shift the freerouting In2 leg clear of the cavity
        (b) route the net on B.Cu instead, avoiding In2 near J_W4 entirely
        (c) declare it not closable at S1 and keep the open

This script does 1 and 2 and prints the numbers. It changes nothing.
"""

import pcbnew as p

UM = 1_000_000.0
BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
NET = '/W3_SOLAR_N'

b = p.LoadBoard(LIVE)

print('=== J_W footprint pads (the wing socket) ===')
for ref in ('J_W4', 'J_W3', 'J_W2', 'J_W1'):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        continue
    print('\n  %s  pos (%.3f, %.3f)  orient %.0f' % (
        ref, fp.GetPosition().x / UM, fp.GetPosition().y / UM, fp.GetOrientationDegrees()))
    for pd in fp.Pads():
        pos = pd.GetPosition()
        print('    pad %-3s net %-14s (%8.3f,%8.3f)  %.3fx%.3f  drill %.3f  layers %s'
              % (pd.GetNumber(), str(pd.GetNetname()),
                 pos.x / UM, pos.y / UM, pd.GetSizeX() / UM, pd.GetSizeY() / UM,
                 pd.GetDrillSize().x / UM,
                 ','.join(pd.GetLayerSet().FmtHex()[:6] for _ in [0])))

print('\n=== Edge.Cuts graphics near J_W4 (the cavity) ===')
bb4 = None
fp4 = b.FindFootprintByReference('J_W4')
if fp4 is not None:
    bb4 = fp4.GetBoundingBox()
    print('  J_W4 bbox: (%.3f,%.3f)-(%.3f,%.3f)'
          % (bb4.GetLeft() / UM, bb4.GetTop() / UM, bb4.GetRight() / UM, bb4.GetBottom() / UM))

print('\n  footprint graphics on Edge.Cuts:')
for fp in b.GetFootprints():
    for gi in fp.GraphicalItems():
        if gi.GetLayer() != p.Edge_Cuts:
            continue
        try:
            s, e = gi.GetStart(), gi.GetEnd()
        except Exception:
            continue
        print('    %-8s %s (%.3f,%.3f)->(%.3f,%.3f)'
              % (fp.GetReference(), gi.GetClass(),
                 s.x / UM, s.y / UM, e.x / UM, e.y / UM))

print('\n=== %s copper on the live board ===' % NET)
segs = []
for t in b.GetTracks():
    if str(t.GetNetname()) != NET:
        continue
    s, e = t.GetStart(), t.GetEnd()
    segs.append((b.GetLayerName(t.GetLayer()), s.x / UM, s.y / UM, e.x / UM, e.y / UM,
                 t.GetWidth() / UM, t.Type() == p.PCB_VIA_T))
print('  %d objects' % len(segs))
for r in segs:
    print('    %-8s %s (%8.3f,%8.3f)->(%8.3f,%8.3f) w%.3f'
          % (r[0], 'VIA' if r[6] else 'trk', r[1], r[2], r[3], r[4], r[5]))

print('\n=== %s pads on the board ===' % NET)
for fp in b.GetFootprints():
    for pd in fp.Pads():
        if str(pd.GetNetname()) != NET:
            continue
        pos = pd.GetPosition()
        lay = []
        for l in (p.F_Cu, p.B_Cu):
            if pd.IsOnLayer(l):
                lay.append(b.GetLayerName(l))
        print('    %s.%s  (%8.3f,%8.3f)  %s  drill %.3f'
              % (fp.GetReference(), pd.GetNumber(), pos.x / UM, pos.y / UM,
                 '+'.join(lay), pd.GetDrillSize().x / UM))
