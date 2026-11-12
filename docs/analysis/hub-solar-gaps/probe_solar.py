#!/usr/bin/env python3
"""Close the 9 real solar-chain gaps with short routed tracks.

Each gap is a J_W pad <-> bypass-diode pin pair on the same /W*_SOLAR_N net, with
no copper between them. This probe:

  1. loads the repaired candidate (read-only source untouched),
  2. for each of the 9 pairs, finds the two pads and their exact positions,
  3. rejects the pair unless BOTH pads are on the same copper layer and the
     straight segment between them is clear of foreign copper,
  4. reports the geometry so the fix can be judged before any edit.

No board is modified by this script: it only measures and reports.
"""
import json
import pathlib
import re

import pcbnew as k
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

BASE = ('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
        'hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb')
CLS = ('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
       'unconn-class/classification.json')
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')
CLEAR = 0.20
TRACK = 0.20


def mm(v):
    return v / 1e6


def pad_at(board, ref, num, layer):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        return None
    for p in fp.Pads():
        if p.GetNumber() != num:
            continue
        ls = [board.GetLayerName(l) for l in p.GetLayerSet().Seq()]
        if layer in ls:
            return p
    return None


def main():
    b = k.LoadBoard(BASE)
    b.BuildConnectivity()
    d = json.load(open(CLS))
    pat = re.compile(r'Pad (\d+) \[([^\]]*)\] of (\w+) on ([\w.]+)')

    pairs = []
    for rec in d['details']:
        if 'D_BP' not in ' '.join(rec['descs']):
            continue
        ms = [pat.search(ds) for ds in rec['descs']]
        if not all(ms) or len(ms) != 2:
            continue
        (n1, net1, r1, l1), (n2, net2, r2, l2) = [m.groups() for m in ms]
        if net1 != net2:
            continue
        p1 = pad_at(b, r1, n1, l1)
        p2 = pad_at(b, r2, n2, l2)
        pairs.append(dict(net=net1, a=(r1, n1, l1), b=(r2, n2, l2),
                          p1=p1, p2=p2))

    # foreign copper per layer, excluding this net
    foreign = {l: [] for l in CU}
    for t in b.GetTracks():
        lay = b.GetLayerName(t.GetLayer())
        if lay not in CU:
            continue
        ls = LineString([(mm(t.GetStart().x), mm(t.GetStart().y)),
                         (mm(t.GetEnd().x), mm(t.GetEnd().y))]).buffer(
                             mm(t.GetWidth()) / 2, cap_style='round')
        foreign[lay].append((t.GetNetname(), ls))
    for f in b.GetFootprints():
        for p in f.Pads():
            for l in [b.GetLayerName(x) for x in p.GetLayerSet().Seq()]:
                if l in CU:
                    bb = p.GetBoundingBox()
                    foreign[l].append((p.GetNetname(),
                                       Point(mm(p.GetPosition().x),
                                             mm(p.GetPosition().y)).buffer(
                                                 max(mm(p.GetSize().x),
                                                     mm(p.GetSize().y)) / 2)))

    print(f'{len(pairs)} J_W<->diode pairs on the same net\n')
    ok = []
    for i, pr in enumerate(pairs, 1):
        if pr['p1'] is None or pr['p2'] is None:
            print(f'{i:2d} {pr["net"]:16s} MISSING a pad: {pr["a"]} / {pr["b"]}')
            continue
        x1, y1 = mm(pr['p1'].GetPosition().x), mm(pr['p1'].GetPosition().y)
        x2, y2 = mm(pr['p2'].GetPosition().x), mm(pr['p2'].GetPosition().y)
        lay = pr['a'][2]
        dist = LineString([(x1, y1), (x2, y2)]).length
        seg = LineString([(x1, y1), (x2, y2)]).buffer(
            TRACK / 2 + CLEAR, cap_style='round')
        clashes = [(n, g) for n, g in foreign[lay]
                   if n not in (pr['net'], '') and g.intersects(seg)]
        same_layer = pr['b'][2] == lay
        print(f'{i:2d} {pr["net"]:16s} {pr["a"][0]}.{pr["a"][1]}({lay}) -> '
              f'{pr["b"][0]}.{pr["b"][1]}({pr["b"][2]})  '
              f'd={dist:6.2f}mm  sameLayer={same_layer}  '
              f'blockers={len(clashes)}'
              + (f'  {sorted({n for n, _ in clashes})[:3]}' if clashes else ''))
        if same_layer and not clashes:
            ok.append(dict(net=pr['net'], a=pr['a'], b=pr['b'], layer=lay,
                           length=round(dist, 4),
                           from_mm=[round(x1, 4), round(y1, 4)],
                           to_mm=[round(x2, 4), round(y2, 4)]))

    print(f'\nROUTEABLE (same layer, clear corridor): {len(ok)}')
    for o in ok:
        print('  ', o['net'], o['from_mm'], '->', o['to_mm'], f"{o['length']}mm")
    out = pathlib.Path('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
                       'unconn-class/solar_routes.json')
    out.write_text(json.dumps(dict(routeable=len(ok), routes=ok), indent=1))
    print('wrote', out)


if __name__ == '__main__':
    main()
