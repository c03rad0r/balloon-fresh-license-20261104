"""Are the 4 zone-pair "unconnected" records real copper gaps or connectivity artefacts?

DRC reports these as unconnected, on the live board (18 opens):
  4   Zone 'VSCAP_BCu' [/VSCAP] on B.Cu  || PTH pad 1 [/VSCAP] of C_CAP1
  14  Zone 'GND_FCu'  [GND]  on F.Cu    || Zone 'GND_In1' [GND] on In1.Cu
  15  Zone 'GND_BCu'  [GND]  on B.Cu    || Zone 'GND_In1' [GND] on In1.Cu
  16  Zone 'GND_In1'  [GND]  on In1.Cu  || Zone 'GND_FCu' [GND]  on F.Cu

A zone on one layer cannot connect to a zone on another layer without a via. So a
zone-to-zone record across layers is EXPECTED unless stitching vias join the pours. The
question that matters: for each net, are the per-layer pours actually electrically joined?

Method: for each net with a zone-pair record, take every via and through-hole pad of that net
and report which zone fills (net + layer) it lands in. If a single via joins layer A's fill to
layer B's fill, the pours ARE connected and the record is informational. If some layer's fill
has no shared via with the others, that pour is isolated -- a real defect.
"""
import json
import pcbnew as p

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
NETS = ['GND', '/VSCAP']


def main():
    b = p.LoadBoard(BOARD)
    fills = []          # (net, layer, polyset, area)
    for z in b.Zones():
        net = z.GetNetname()
        if net not in NETS:
            continue
        ln = z.GetLayer()
        fp = z.GetFilledPolysList(ln)
        n = fp.OutlineCount()
        area = z.GetFilledArea() / 1e12
        fills.append((net, ln, fp, area, n))
        print('zone %-8s %-8s %2d island(s) %9.2f mm2' % (net, b.GetLayerName(ln), n, area))

    # stitching objects per net: vias (join all layers) and PTH pads (join their stack)
    stitches = {}
    for t in b.GetTracks():
        if isinstance(t, p.PCB_VIA):
            stitches.setdefault(t.GetNetname(), []).append(('VIA', t.GetPosition(),
                                                            [p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu]))
    for f in b.GetFootprints():
        for q in f.Pads():
            if not q.HasHole():
                continue
            layers = [l for l in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu) if q.IsOnLayer(l)]
            if layers:
                stitches.setdefault(q.GetNetname(), []).append(
                    ('PTH %s.%s' % (f.GetReference(), q.GetNumber()), q.GetPosition(), layers))

    print()
    for net in NETS:
        print('=== %s' % net)
        mine = [f for f in fills if f[0] == net]
        layers = sorted({f[1] for f in mine})
        joined = {l: set() for l in layers}
        n_via = 0
        for (kind, pos, lset) in stitches.get(net, []):
            hits = []
            for (n2, ln, fp, area, ni) in mine:
                if ln in lset and fp.Contains(pos):
                    hits.append(ln)
            if len(hits) >= 2:
                n_via += 1
                for h in hits:
                    joined[h].update(hits)
        print('  stitching objects joining >=2 layers: %d' % n_via)
        for l in layers:
            others = joined[l]
            print('    %-8s fill %s' % (b.GetLayerName(l),
                                        ('joined to %s' % sorted(b.GetLayerName(o) for o in others))
                                        if others else 'NOT joined to any other layer fill'))
        isolated = [l for l in layers if not joined[l]]
        if isolated:
            print('  VERDICT: %d layer fill(s) have NO via/PTH shared with another layer: %s'
                  % (len(isolated), [b.GetLayerName(l) for l in isolated]))
            print('           -> the zone-pair record for these is a REAL disconnection.')
        else:
            print('  VERDICT: every layer fill shares at least one via/PTH with another layer.')
            print('           -> pours are electrically joined; the record is informational.')
        print()


if __name__ == '__main__':
    main()
