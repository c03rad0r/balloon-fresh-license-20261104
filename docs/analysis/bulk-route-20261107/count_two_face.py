#!/usr/bin/env python3
"""count_two_face.py -- enumerate EVERY pad number backed by 2+ pad objects on
disjoint copper layers, across the whole board.

This is the exclusion list the release gate would need to carry. Measuring it now so
the recommendation names a real count instead of a guess.
"""
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
MM = 1e6
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)


def layers_of(pad):
    ls = pad.GetLayerSet()
    return {b.GetLayerName(l) for l in COPPER if ls.Contains(l)}


def box(pad):
    bb = pad.GetBoundingBox()
    return (round(bb.GetX() / MM, 3), round(bb.GetY() / MM, 3),
            round((bb.GetX() + bb.GetWidth()) / MM, 3),
            round((bb.GetY() + bb.GetHeight()) / MM, 3))


found = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    by_num = {}
    for pad in fp.Pads():
        by_num.setdefault(pad.GetNumber(), []).append(pad)
    for num, pads in by_num.items():
        if len(pads) < 2:
            continue
        lays = [layers_of(p) for p in pads]
        all_lay = set().union(*lays)
        # two-face: 2+ objects, layers disjoint, boxes identical, none is PTH
        pth = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in pads)
        if pth:
            continue
        if len(all_lay) < 2:
            continue
        boxes = {box(p) for p in pads}
        found.append({
            "ref": ref, "num": num, "n": len(pads),
            "layers": sorted(all_lay),
            "same_box": len(boxes) == 1,
            "net": pads[0].GetNetname(),
        })

print(f"board: {BOARD.split('/')[-1]}")
print(f"pad numbers backed by 2+ SMD objects on disjoint copper layers: {len(found)}\n")
print(f"{'ref':8s} {'pad':4s} {'n':>2s}  {'layers':22s} {'same bbox':10s} net")
for f in sorted(found, key=lambda x: (x["ref"], x["num"])):
    print(f"{f['ref']:8s} {f['num']:4s} {f['n']:2d}  {','.join(f['layers']):22s} "
          f"{str(f['same_box']):10s} {f['net']}")

bad = [f for f in found if not f["same_box"]]
print(f"\nsame bbox in every case: {not bad}")
if bad:
    print("  NOT same bbox (would need individual inspection): "
          + ", ".join(f"{f['ref']}.{f['num']}" for f in bad))
print(f"\nsuggested exclusion list entries: {len(found)}")
print("  " + " ".join(f"{f['ref']}.{f['num']}" for f in sorted(found, key=lambda x: (x["ref"], x["num"]))))
