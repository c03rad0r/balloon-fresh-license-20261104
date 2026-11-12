#!/usr/bin/env python3
"""Confirm the J_W F.Cu/B.Cu pad pairs are edge-card lands at IDENTICAL XY.

If a pad number exists as two pads (one F.Cu, one B.Cu) at the SAME position and
same net, the inserted wing tab bridges them mechanically and board copper must
not join them. If their XY differ, they are two distinct lands.
"""
import pcbnew as k
from collections import defaultdict

B = ('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
     'unconn-class/hub_board_v10_lora1280_7of9.kicad_pcb')
b = k.LoadBoard(B)

for ref in ('J_W1', 'J_W2', 'J_W3', 'J_W4'):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        print(f'{ref}: MISSING')
        continue
    by_num = defaultdict(list)
    for p in fp.Pads():
        layers = [b.GetLayerName(l) for l in p.GetLayerSet().Seq()]
        if 'F.Cu' in layers or 'B.Cu' in layers:
            by_num[p.GetNumber()].append(
                (tuple(layers), round(p.GetPosition().x / 1e6, 4),
                 round(p.GetPosition().y / 1e6, 4), p.GetNetname()))
    print(f'== {ref} ==')
    for num, insts in sorted(by_num.items()):
        if len(insts) < 2:
            continue
        pos = {(x, y) for _, x, y, _ in insts}
        nets = {n for _, _, _, n in insts}
        verdict = 'SAME XY -> mechanically bridged' if len(pos) == 1 else f'DIFFERENT XY {sorted(pos)}'
        print(f'  pad {num}: {len(insts)} copper faces, net(s)={sorted(nets)} -> {verdict}')
