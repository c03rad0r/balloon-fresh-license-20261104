"""Escape probe for any pad: how far can a 0.200 mm track get in each direction at S1?

For each of 12 directions from the pad centre, step outward at 0.100 mm and report the first
foreign object that blocks a 0.200 mm track at the frozen S1 clearance. This answers "is this pad
trapped?" with numbers instead of a router verdict, and names WHICH neighbour encloses it.

Why this exists: /F33_VSENSE pad U1.21 returned NO PATH after 138 steps to targets 41 mm away. That
looked like a long-corridor failure but was a pad-escape failure -- the search never left the pad.
The same 138-step signature on other nets needs the same question asked directly.

SHAPE::Collide only, never SHAPE::Distance (unreliable on this board's pads).
"""
import math
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')

import pcbnew as p

UM = 1_000_000.0
ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
CLEAR = 200_000
GUARD = CLEAR + 70_711
STEP = 100_000        # 0.100 mm
MAXREACH = 5.0        # mm

TARGETS = [t for t in os.environ.get(
    'ESCAPE_TARGETS', '/SPI2_SCK:U1:4,/EN:U1:3').split(',') if t]


def probe(b, net, ref, pin, layer):
    pad = None
    for f in b.GetFootprints():
        if f.GetReference() != ref:
            continue
        for pd in f.Pads():
            if str(pd.GetNumber()) == str(pin):
                pad = pd
    if pad is None:
        print('  pad %s.%s not found' % (ref, pin))
        return
    if not pad.IsOnLayer(layer):
        print('  pad %s.%s is not on %s' % (ref, pin, b.GetLayerName(layer)))
        return
    c = pad.GetPosition()
    px, py = c.x / UM, c.y / UM
    print('%s  pad %s.%s (%.3f, %.3f) size %.3f x %.3f'
          % (net, ref, pin, px, py, pad.GetSize().x / UM, pad.GetSize().y / UM))

    results = []
    for ang in range(0, 360, 30):
        dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        reach = 0.0
        who = ''
        for k in range(1, int(MAXREACH / (STEP / UM)) + 1):
            x = px + dx * (STEP / UM) * k
            y = py + dy * (STEP / UM) * k
            pt = p.SHAPE_CIRCLE(p.VECTOR2I(int(round(x * UM)), int(round(y * UM))), STEP // 2)
            hit = ''
            for t in b.GetTracks():
                if str(t.GetNetname()) == net:
                    continue
                if t.Type() != p.PCB_VIA_T and t.GetLayer() != layer:
                    continue
                if p.SHAPE.Collide(t.GetEffectiveShape(0), pt, GUARD):
                    hit = 'track %s' % t.GetNetname()
                    break
            if not hit:
                for f in b.GetFootprints():
                    for pd in f.Pads():
                        if str(pd.GetNetname()) == net:
                            continue
                        if not pd.IsOnLayer(layer):
                            continue
                        if p.SHAPE.Collide(pd.GetEffectiveShape(layer), pt, GUARD):
                            hit = 'pad %s.%s' % (f.GetReference(), pd.GetNumber())
                            break
                    if hit:
                        break
            if hit:
                who = hit
                break
            reach = (STEP / UM) * k
        results.append((ang, reach, who))

    for ang, reach, who in results:
        print('   %3d deg: clear %4.2f mm  %s' % (ang, reach, who or '(clear to 5 mm)'))
    best = max(r[1] for r in results)
    free = [r for r in results if not r[2]]
    print('   WIDEST clear run: %.2f mm   free directions: %d of 12'
          % (best, len(free)))
    if best < 0.35 and not free:
        print('   VERDICT: TRAPPED at S1')
    elif free:
        print('   VERDICT: has at least one open direction')
    else:
        print('   VERDICT: tight but not fully enclosed')
    print()


def main():
    b = p.LoadBoard(LIVE)
    for spec in TARGETS:
        parts = spec.split(':')
        if len(parts) != 3:
            print('bad target %r, expected net:REF:PIN' % spec)
            continue
        net, ref, pin = parts
        probe(b, net, ref, pin, p.F_Cu)
    return 0


if __name__ == '__main__':
    sys.exit(main())
