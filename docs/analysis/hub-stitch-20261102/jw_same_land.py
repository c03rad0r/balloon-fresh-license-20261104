#!/usr/bin/env python3
"""Are J_W 'F.Cu half <-> B.Cu half' unconnected records the by-design edge-card case?

The repo's fab-gating doctrine says: edge-card socket lands (J_W pad on F.Cu + the same
pad on B.Cu, same net, same XY) are bridged MECHANICALLY by the inserted tab; board
copper must not join them, and KiCad flags them as unconnected forever.

This tests that mechanically: for every J_W unconnected record whose two endpoints are
the SAME reference and SAME pad number on two layers, measure the XY offset between the
two pad stacks. Zero offset => same physical land, mechanically bridged.
Non-zero => two distinct lands, and the record is a real copper gap.
"""
import json
import re
from collections import Counter

import pcbnew as k

BOARD = ('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
         'unconn-class/hub_board_v10_lora1280_7of9.kicad_pcb')
CLS = ('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
       'unconn-class/classification.json')


def main():
    b = k.LoadBoard(BOARD)
    pads = {}
    for f in b.GetFootprints():
        for p in f.Pads():
            pads[(f.GetReference(), p.GetNumber())] = p

    d = json.load(open(CLS))
    jw = [x for x in d['details'] if x['cls'] == 'J_W']

    print('template "Pad N [NET] of REF on LAYER"')
    pat = re.compile(r'Pad (\d+) \[([^\]]*)\] of (\w+) on ([\w.]+)')

    same_land = []
    distinct = []
    unparsed = []

    for rec in jw:
        parsed = [pat.search(ds) for ds in rec['descs']]
        if not all(parsed) or len(parsed) != 2:
            unparsed.append(rec)
            continue
        (n1, net1, r1, l1), (n2, net2, r2, l2) = [m.groups() for m in parsed]
        if r1 == r2 and n1 == n2 and l1 != l2:
            p = pads.get((r1, n1))
            if p is None:
                unparsed.append(rec)
                continue
            # same pad object reported twice (one entry per layer) => same land
            same_land.append(dict(ref=r1, pad=n1, net=net1, layers=[l1, l2],
                                  pos_mm=[round(p.GetPosition().x / 1e6, 4),
                                          round(p.GetPosition().y / 1e6, 4)]))
        else:
            distinct.append(rec)

    print(f'\nJ_W records: {len(jw)}')
    print(f'  SAME land on two layers (mechanically bridged by tab): {len(same_land)}')
    print(f'  DISTINCT lands (real copper gap):                      {len(distinct)}')
    print(f'  could not parse:                                       {len(unparsed)}')

    print('\nsame-land records:')
    for x in same_land:
        print(f"  {x['ref']}.{x['pad']} [{x['net']}] layers={x['layers']} pos={x['pos_mm']}")

    print('\ndistinct-land records (REAL gaps):')
    for rec in distinct:
        print('  ', ' || '.join(rec['descs'])[:150])

    # Are the J_W footprints edge-card footprints with pads on both faces at one XY?
    print('\nJ_W pad-layer sanity (each pad number should appear on F.Cu AND B.Cu):')
    for ref in ('J_W1', 'J_W2', 'J_W3', 'J_W4'):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f'  {ref}: MISSING')
            continue
        nu = Counter()
        for p in fp.Pads():
            cu = [b.GetLayerName(l) for l in p.GetLayerSet().Seq()
                  if b.GetLayerName(l) in ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')]
            nu[(p.GetNumber(), tuple(cu))] += 1
        print(f'  {ref}: ' + ', '.join(f'{n}:{"/".join(c)}' for (n, c), _ in sorted(nu.items())))

    out = dict(same_land=len(same_land), distinct=len(distinct),
               same_land_records=same_land)
    open('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
         'unconn-class/jw_split.json', 'w').write(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
