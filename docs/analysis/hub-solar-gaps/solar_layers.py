#!/usr/bin/env python3
"""CORRECTED solar gap analysis - per PAD OBJECT, not per pad number.

The previous script (solar_layers.py) built a dict keyed by (ref, number). A J_W
pad number maps to TWO pad objects (one F.Cu, one B.Cu, same XY, same net), so the
dict silently kept only one and the layer sets came out wrong. That produced the
false conclusion "0 of 9 pairs share a copper layer".

This version keeps every pad object and computes the true shared-layer set.
"""
import json
import re

import pcbnew as k

BASE = ('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
        'hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb')
CLS = ('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
       'unconn-class/classification.json')
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')
ATTR = {0: 'PTH', 1: 'SMD', 2: 'CONN', 3: 'NPTH'}


def main():
    b = k.LoadBoard(BASE)
    d = json.load(open(CLS))
    pat = re.compile(r'Pad (\d+) \[([^\]]*)\] of (\w+) on ([\w.]+)')

    def pad_objs(ref, num):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            return []
        return [p for p in fp.Pads() if p.GetNumber() == num]

    def layers(p):
        return {l for l in (b.GetLayerName(x) for x in p.GetLayerSet().Seq())
                if l in CU}

    rows = []
    for rec in d['details']:
        if 'D_BP' not in ' '.join(rec['descs']):
            continue
        ms = [pat.search(x) for x in rec['descs']]
        if not all(ms) or len(ms) != 2:
            continue
        (n1, net, r1, l1), (n2, _, r2, l2) = [m.groups() for m in ms]

        ps1, ps2 = pad_objs(r1, n1), pad_objs(r2, n2)
        L1 = set().union(*[layers(p) for p in ps1]) if ps1 else set()
        L2 = set().union(*[layers(p) for p in ps2]) if ps2 else set()
        shared = sorted(L1 & L2)
        rows.append(dict(net=net, a=f'{r1}.{n1}', b=f'{r2}.{n2}',
                         a_all_layers=sorted(L1), b_all_layers=sorted(L2),
                         shared=shared, routeable=bool(shared),
                         a_objects=len(ps1), b_objects=len(ps2),
                         a_attr=[ATTR.get(int(p.GetAttribute()), '?') for p in ps1],
                         b_attr=[ATTR.get(int(p.GetAttribute()), '?') for p in ps2]))
        print(f'{net:14s} {r1}.{n1} {sorted(L1)}  <->  {r2}.{n2} {sorted(L2)}  '
              f'shared={shared}')

    ok = [r for r in rows if r['routeable']]
    print(f'\nrouteable on a shared layer: {len(ok)}/{len(rows)}')
    for r in ok:
        print('  FIXABLE:', r['net'], r['a'], '<->', r['b'], 'on', r['shared'])

    json.dump(rows, open('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
                         'unconn-class/solar_layers_corrected.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
