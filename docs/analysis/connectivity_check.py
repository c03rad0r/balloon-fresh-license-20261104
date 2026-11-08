"""Is /SPI1_MISO actually connected after SPI1PAIR2, or did the flood lie?

The reachability gate said LOST (341 cells) while native DRC dropped 29 -> 26 and
proof.py reported connected_after=true. Both cannot be right.

The likely cause is a category error in the gate: flood "can a new 0.20 mm track be
drawn here" is the right question on a BEFORE board, but on an AFTER board the
corridor is partly occupied by our own new track, so "room for another track" can
legitimately fail while the net IS connected. That is a false LOST, not a regression.

This checks CONNECTIVITY directly instead: does the pad touch same-net copper that
reaches the other pad?
"""
import pcbnew as p
import sys, os
from pathlib import Path

B = Path('/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/batches/SPI1PAIR2')
ROUTED = B / 'routed.kicad_pcb'
BEFORE = B / 'board.kicad_pcb'
NET = '/SPI1_MISO'
PAIR = ('U3', '3', 'U_C', '3')


def pad_of(b, ref, num, net):
    for f in b.GetFootprints():
        if f.GetReference() == ref:
            for q in f.Pads():
                if q.GetNumber() == num and q.GetNetname() == net:
                    return q
    return None


def same_net_copper(b, net):
    items = [t for t in b.GetTracks() if t.GetNetname() == net]
    for f in b.GetFootprints():
        for q in f.Pads():
            if q.GetNetname() == net:
                items.append(q)
    return items


def touching(b, pad, net):
    """Same-net copper items whose shape touches the pad within 1 um."""
    out = []
    pl = pad.GetLayer()
    for q in same_net_copper(b, net):
        if q.m_Uuid.AsString() == pad.m_Uuid.AsString():
            continue
        for l in (p.F_Cu, p.B_Cu):
            if not (q.IsOnLayer(l) and pad.IsOnLayer(l)):
                continue
            a = pad.GetEffectiveShape(l)
            for l2 in (p.F_Cu, p.B_Cu):
                if q.IsOnLayer(l2):
                    c = q.GetEffectiveShape(l2)
                    if p.SHAPE.Collide(a, c, 1000):
                        out.append((type(q).__name__, q.GetNetname(),
                                    b.GetLayerName(l)))
                        break
    return out


def main():
    for tag, path in (('BEFORE', BEFORE), ('ROUTED', ROUTED)):
        b = p.LoadBoard(str(path))
        ra, na, rb, nb = PAIR
        pa = pad_of(b, ra, na, NET)
        pb = pad_of(b, rb, nb, NET)
        print('\n%s' % tag)
        if not pa or not pb:
            print('  pad missing'); continue
        print('  %s.%s at (%.3f, %.3f)  layers %s'
              % (ra, na, pa.GetPosition().x / 1e6, pa.GetPosition().y / 1e6,
                 [b.GetLayerName(l) for l in (p.F_Cu, p.B_Cu) if pa.IsOnLayer(l)]))
        print('  %s.%s at (%.3f, %.3f)  layers %s'
              % (rb, nb, pb.GetPosition().x / 1e6, pb.GetPosition().y / 1e6,
                 [b.GetLayerName(l) for l in (p.F_Cu, p.B_Cu) if pb.IsOnLayer(l)]))
        ta = touching(b, pa, NET)
        tb = touching(b, pb, NET)
        print('  same-net copper touching %s.%s : %d %s' % (ra, na, len(ta), ta[:4]))
        print('  same-net copper touching %s.%s : %d %s' % (rb, nb, len(tb), tb[:4]))
        n_tr = len([t for t in b.GetTracks() if t.GetNetname() == NET])
        print('  /SPI1_MISO track count: %d' % n_tr)


if __name__ == '__main__':
    main()
