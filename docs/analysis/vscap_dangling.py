"""Are the two /VSCAP dangling vias real, and do they explain the /VSCAP open?

check_drc.py on the live board reports:
  via_dangling: Via [/VSCAP] on F.Cu - B.Cu  @(36.0000, 40.0000)
  via_dangling: Via [/VSCAP] on F.Cu - B.Cu  @(6.6000, 58.5997)

"Not connected or connected on only one layer" means the via lands on copper on one face and
nothing on the other. If true, those two vias contribute nothing and /VSCAP is broken at
exactly those points -- and a dangling via is also a fabrication oddity (a plated barrel into
nothing).

This measures, per via: how many /VSCAP copper objects touch either end on F.Cu and on B.Cu,
using Collide only. A via with 0 or 1 ends touched is dangling; 2+ is connected.
"""
import pcbnew as p

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
NET = '/VSCAP'


def main():
    b = p.LoadBoard(BOARD)

    # every copper object of this net, per layer
    tracks = {}
    for t in b.GetTracks():
        if t.GetNetname() != NET or isinstance(t, p.PCB_VIA):
            continue
        tracks.setdefault(t.GetLayer(), []).append(t)
    pads = {}
    for f in b.GetFootprints():
        for q in f.Pads():
            if q.GetNetname() != NET:
                continue
            for l in (p.F_Cu, p.B_Cu):
                if q.IsOnLayer(l):
                    pads.setdefault(l, []).append(q)

    vias = [t for t in b.GetTracks() if isinstance(t, p.PCB_VIA) and t.GetNetname() == NET]
    print('net %s: %d track segs, %d vias, pads on F=%d B=%d'
          % (NET, sum(len(v) for v in tracks.values()), len(vias),
             len(pads.get(p.F_Cu, [])), len(pads.get(p.B_Cu, []))))

    report = []
    for v in vias:
        c = v.GetPosition()
        per = {}
        for l in (p.F_Cu, p.B_Cu):
            n = 0
            disc = p.SHAPE_CIRCLE(c, 2000)     # 2 um touch tolerance at the via centre
            for t in tracks.get(l, []):
                if p.SHAPE.Collide(disc, t.GetEffectiveShape(l), 2000):
                    n += 1
            for q in pads.get(l, []):
                if p.SHAPE.Collide(disc, q.GetEffectiveShape(l), 2000):
                    n += 1
            per[b.GetLayerName(l)] = n
        dangling = (per.get('F.Cu', 0) == 0 or per.get('B.Cu', 0) == 0)
        report.append({'x': round(c.x / 1e6, 4), 'y': round(c.y / 1e6, 4),
                       'touches': per, 'dangling': dangling})
        print('  via at (%.4f, %.4f)  F.Cu touches %d, B.Cu touches %d  -> %s'
              % (c.x / 1e6, c.y / 1e6, per.get('F.Cu', 0), per.get('B.Cu', 0),
                 'DANGLING' if dangling else 'connected'))

    nd = sum(1 for r in report if r['dangling'])
    print('\n%d of %d /VSCAP vias are dangling' % (nd, len(report)))
    if nd:
        print('VERDICT: real. Each dangling via is a plated barrel connected on one face only.')
        print('  Consequence: it carries no current and /VSCAP stays split at that point.')
    else:
        print('VERDICT: not reproduced by direct measurement -- DRC may be reporting on a '
              'different connectivity state than this file.')


if __name__ == '__main__':
    main()
