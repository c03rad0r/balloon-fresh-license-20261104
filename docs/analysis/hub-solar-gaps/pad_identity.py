#!/usr/bin/env python3
"""Resolve the J_W pad-number contradiction: does one number map to ONE land?

Records disagree about the layer of J_W1.4 (/W1_SOLAR_N): one names F.Cu, another
B.Cu. Two possibilities:

  A  the pad number maps to a SINGLE physical land whose copper exists on both
     faces (edge-card land) -> the layer disagreement is cosmetic
  B  the pad number maps to TWO physically distinct lands -> a real netlist defect

This checks pad UUID identity, exact XY, size, and shape per pad number, and
compares against the footprint's own pad definitions.
"""
import json
from collections import defaultdict

import pcbnew as k

BASE = ('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
        'hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb')
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')


def main():
    b = k.LoadBoard(BASE)
    out = {}
    for ref in ('J_W1', 'J_W2', 'J_W3', 'J_W4'):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            continue
        print(f'\n=== {ref}  footprint at '
              f'({fp.GetPosition().x/1e6:.3f}, {fp.GetPosition().y/1e6:.3f}) ===')
        by_num = defaultdict(list)
        for p in fp.Pads():
            by_num[p.GetNumber()].append(p)
        rec = {}
        for num in sorted(by_num):
            ps = by_num[num]
            print(f'  pad {num}: {len(ps)} pad object(s)')
            entry = []
            for p in ps:
                ls = [b.GetLayerName(x) for x in p.GetLayerSet().Seq() if b.GetLayerName(x) in CU]
                entry.append(dict(
                    uuid=p.m_Uuid.AsString(),
                    layers=ls,
                    pos=[round(p.GetPosition().x / 1e6, 4), round(p.GetPosition().y / 1e6, 4)],
                    size=[round(p.GetSize().x / 1e6, 4), round(p.GetSize().y / 1e6, 4)],
                    shape=int(p.GetShape()),
                    net=p.GetNetname(),
                    attr=int(p.GetAttribute())))
                print(f'      uuid={p.m_Uuid.AsString()[:8]} layers={ls} '
                      f'pos={entry[-1]["pos"]} size={entry[-1]["size"]} '
                      f'shape={entry[-1]["shape"]} net={p.GetNetname()!r}')
            # verdict for this pad number
            pos = {tuple(e['pos']) for e in entry}
            uuids = {e['uuid'] for e in entry}
            if len(ps) == 1:
                v = 'ONE pad object covering both faces' if len(entry[0]['layers']) > 1 \
                    else 'ONE pad object, single layer'
            elif len(pos) == 1:
                v = 'MULTIPLE objects at IDENTICAL XY (stacked land)'
            else:
                v = f'MULTIPLE objects at DIFFERENT XY {sorted(pos)} <- distinct lands'
            print(f'      -> {v}')
            rec[num] = dict(objects=len(ps), positions=sorted(pos),
                            uuids=sorted(uuids), verdict=v, pads=entry)
        out[ref] = rec

    json.dump(out, open('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
                        'unconn-class/jw_pad_identity.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
