"""Are the 4 zone-pair "unconnected" records REAL gaps or DRC artefacts?

DRC reports e.g. `Zone 'GND_FCu' [GND] on F.Cu` vs `Zone 'GND_In1' [GND] on In1.Cu` as
unconnected. A zone pair on different layers cannot connect by itself -- it needs a via
joining the two pours. But KiCad also reports a zone's ORIGIN as the item position, which
makes these records hard to locate and easy to dismiss.

So: measure whether the GND pours on F/B/In1 are electrically joined through vias, and
whether VSCAP_BCu has two disconnected islands. If they are joined, the records are
artefacts. If not, they are real and one of them may be the honest cause of a split pour.

Method: for each zone net and layer pair, collect the zone's filled polygons and the vias
on that net; ask whether every filled island contains or touches a via/copper that reaches
the other layer's pour.
"""
import pcbnew as p
import json, sys
from pathlib import Path

BOARD = Path('/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb')


def main():
    b = pcbnew if False else p
    bd = b.LoadBoard(str(BOARD))
    vias_by_net = {}
    for t in bd.GetTracks():
        if isinstance(t, b.PCB_VIA):
            vias_by_net.setdefault(t.GetNetname(), []).append(t)

    print('vias per net (top nets):')
    for net, vs in sorted(vias_by_net.items(), key=lambda kv: -len(kv[1]))[:8]:
        print('  %-14s %d' % (net, len(vs)))

    print('\nzones:')
    for z in bd.Zones():
        net = z.GetNetname()
        layer = bd.GetLayerName(z.GetLayer())
        fp = z.GetFilledPolysList(z.GetLayer()) if hasattr(z, 'GetFilledPolysList') else None
        islands = 0
        if fp is not None:
            try:
                islands = fp.OutlineCount()
            except Exception:
                islands = -1
        area = z.GetFilledArea() / 1e12 if hasattr(z, 'GetFilledArea') else -1
        # how many vias of this net lie inside the zone's own filled polygons?
        inside = 0
        if fp is not None:
            try:
                for v in vias_by_net.get(net, []):
                    if fp.Contains(v.GetPosition()):
                        inside += 1
            except Exception:
                inside = -1
        print('  %-10s %-8s islands=%-3s area=%8.2f mm2  vias_inside=%s (net has %d)'
              % (net, layer, islands, area, inside, len(vias_by_net.get(net, []))))

    print('\ndangling vias (the 2 DRC warnings):')
    # a via is dangling if no track of its net touches either end
    for net, vs in vias_by_net.items():
        tracks = [t for t in bd.GetTracks()
                  if not isinstance(t, b.PCB_VIA) and t.GetNetname() == net]
        for v in vs:
            c = v.GetPosition()
            touch = 0
            for t in tracks:
                for l in (b.F_Cu, b.B_Cu):
                    if t.IsOnLayer(l):
                        sh = t.GetEffectiveShape(l)
                        if sh.Collide(p.SHAPE_SEGMENT(c, c, 1000), 1000):
                            touch += 1
                            break
            if touch == 0:
                print('  DANGLING /%-14s at (%.3f, %.3f) drill=%.2f'
                      % (net, c.x / 1e6, c.y / 1e6, v.GetDrillValue() / 1e6))


if __name__ == '__main__':
    main()
