"""Route the four CUT_SENSE pad-to-track opens: a B.Cu pad against an F.Cu track.

These four were misfiled as assembly lands in my earlier classification. They are NOT pad-to-
pad (which would be a wing-tab assembly join); each is a pad on one layer against a TRACK on
the other:

  0  Pad 3 [/CUT_SENSE_W1] of J_W1 on B.Cu   || Track on F.Cu, 0.8500 mm
  1  Pad 3 [/CUT_SENSE_W2] of J_W2 on B.Cu   || Track on F.Cu, 2.3500 mm
  2  Pad 3 [/CUT_SENSE_W3] of J_W3 on B.Cu   || Track on F.Cu, 2.3500 mm
  3  Pad 3 [/CUT_SENSE_W4] of J_W4 on B.Cu   || Track on F.Cu, 0.1000 mm

A pad-to-track gap across layers needs a plated transition. Open 3 is 0.1 mm apart, so a via
may well fit even though the cross-layer PAD-PAD cases could not.

Method per open: take the pad centre and the nearest endpoint of the reported same-net track
on the other layer, then route between them with the tested guard-banded router, which may
insert vias. Gated by adopt_batch.py: opens must decrease, no per-type regression, no rise in
hard errors.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json
import math
import os
import subprocess
import collide_router as CR
import batch_run as BR

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
REL = 'docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, REL, 'latest.kicad_pcb')
NAME = 'CUTSENSE'

# net -> (pad footprint, pad number)
TARGETS = {
    '/CUT_SENSE_W1': ('J_W1', '3'),
    '/CUT_SENSE_W2': ('J_W2', '3'),
    '/CUT_SENSE_W3': ('J_W3', '3'),
    '/CUT_SENSE_W4': ('J_W4', '3'),
}


def pad_xy(b, ref, num):
    for f in b.GetFootprints():
        if f.GetReference() != ref:
            continue
        for q in f.Pads():
            if q.GetNumber() == num:
                c = q.GetPosition()
                layers = [l for l in (p.F_Cu, p.B_Cu) if q.IsOnLayer(l)]
                return (c.x, c.y), layers
    return None, None


def nearest_track_endpoint(b, net, layer, px, py):
    best = None
    for t in b.GetTracks():
        if t.GetNetname() != net or isinstance(t, p.PCB_VIA):
            continue
        if t.GetLayer() != layer:
            continue
        for q in (t.GetStart(), t.GetEnd()):
            d = math.hypot(q.x - px, q.y - py)
            if best is None or d < best[0]:
                best = (d, (q.x, q.y))
    return best


def add_path(b, path, net):
    n = b.FindNet(net)
    if n is None:
        b.Add(p.NETINFO_ITEM(b, net))
        n = b.FindNet(net)
    ns = nv = 0
    for k in range(1, len(path)):
        x1, y1, l1 = path[k - 1]
        x2, y2, l2 = path[k]
        if l1 != l2:
            v = p.PCB_VIA(b)
            v.SetNet(n)
            v.SetPosition(p.VECTOR2I(int(round(x1)), int(round(y1))))
            v.SetWidth(int(BR.VIA_R * 2))
            v.SetDrill(int(CR.DRILL_R * 2))
            b.Add(v)
            nv += 1
        elif (int(x1), int(y1)) != (int(x2), int(y2)):
            t = p.PCB_TRACK(b)
            t.SetNet(n)
            t.SetLayer(l1)
            t.SetWidth(int(BR.TRACK_R * 2))
            t.SetStart(p.VECTOR2I(int(round(x1)), int(round(y1))))
            t.SetEnd(p.VECTOR2I(int(round(x2)), int(round(y2))))
            b.Add(t)
            ns += 1
    return ns, nv


def main():
    B = os.path.join(ROOT, REL, 'batches', NAME)
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in ('kicad_pro', 'kicad_dru', 'fp-lib-table'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    b = p.LoadBoard(src)
    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)

    done = []
    for net, (ref, num) in TARGETS.items():
        (s, slayers) = pad_xy(b, ref, num)
        if s is None:
            print('%-16s pad %s.%s not found' % (net, ref, num))
            continue
        # the reported partner is a track on the OTHER layer
        other = [l for l in (p.F_Cu, p.B_Cu) if l not in slayers]
        best = None
        for l in other:
            r = nearest_track_endpoint(b, net, l, s[0], s[1])
            if r and (best is None or r[0] < best[0]):
                best = (r[0], r[1], l)
        if best is None:
            print('%-16s no same-net track on %s' % (net, other))
            continue
        d, g, glayer = best
        print('\n%-16s pad(%s) (%.3f,%.3f) -> track(%s) (%.3f,%.3f)  gap %.3f mm'
              % (net, [b.GetLayerName(l) for l in slayers], s[0] / 1e6, s[1] / 1e6,
                 b.GetLayerName(glayer), g[0] / 1e6, g[1] / 1e6, d / 1e6))

        field = BR.SeqField(b, box, BR.ROUTE_CLEAR)
        margin = 2500000
        rbox = (min(s[0], g[0]) - margin, min(s[1], g[1]) - margin,
                max(s[0], g[0]) + margin, max(s[1], g[1]) + margin)
        path, why = CR.route(field, s, g, net, rbox, slayers, [glayer],
                             deadline_steps=900000, deadline_s=120.0, seed_radius=4)
        if not path:
            print('    NO PATH: %s' % why)
            continue
        ns, nv = add_path(b, path, net)
        ln = sum(math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
                 for k in range(1, len(path))) / 1e6
        print('    ROUTED %.2f mm, %d seg, %d via' % (ln, ns, nv))
        done.append(net)

    if not done:
        print('\nnothing routed -- tree untouched')
        return 1

    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    del b
    refill = '/home/c08r4d0r/.hermes/cache/scratch/refill_one.py'
    subprocess.run(['/usr/bin/python3', '-B', refill, out], capture_output=True, timeout=900)
    for ext in ('kicad_pro', 'kicad_dru', 'fp-lib-table'):
        s = src.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, out.replace('.kicad_pcb', '.' + ext)], check=False)
    print('\nrouted %d/%d: %s' % (len(done), len(TARGETS), done))
    print('candidate at %s -- gate with adopt_batch.py %s' % (out, NAME))
    json.dump({'routed': done}, open(os.path.join(B, 'report.json'), 'w'), indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
