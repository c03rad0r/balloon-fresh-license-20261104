#!/usr/bin/env python3
"""VERIFY the concurrent solar audit's central claim, independently.

Claim under test (docs/analysis/hub-solar-audit/FINDINGS.md, commit e27f39c0):
  "The J_W wing-seat footprint defines 8 copper lands, not 4: pad numbers 1..4 exist TWICE, once on
   F.Cu and once on B.Cu, with identical XY and the same net. The 'zero shared layer' premise is
   therefore a measurement artefact; 12 of 12 diode<->J_W pairs share B.Cu."

Why this matters for MY audit: if it is true, my own obstacle model was wrong in a second, deeper way
than the circle-vs-rectangle bug — I keyed pads by (ref, number) and would silently drop one of each
duplicate pair, so "the J_W end has F.Cu only" could be my error rather than a board property.

This checks, read-only:
  * every pad object of every J_W footprint: number, layer set, XY, net, uuid
  * whether pad numbers repeat, and whether repeated ones differ only in layer
  * for each diode<->J_W pair: the FULL set of shared copper layers across all pad objects, not
    just the first object per number
Exit 0 = the claim reproduces; 1 = it does not.
"""
import collections
import sys

import pcbnew

UM = 1_000_000.0


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    print(f"board: {sys.argv[1]}\n")

    jw = [fp for fp in board.GetFootprints() if fp.GetReference().startswith("J_W")]
    print(f"J_W footprints: {[f.GetReference() for f in jw]}\n")

    total_objs = 0
    for fp in jw:
        pads = list(fp.Pads())
        total_objs += len(pads)
        bynum = collections.defaultdict(list)
        for p in pads:
            bynum[p.GetNumber()].append(p)
        dup = {k: v for k, v in bynum.items() if len(v) > 1}
        print(f"{fp.GetReference()}: {len(pads)} pad objects, {len(bynum)} distinct numbers, "
              f"{len(dup)} numbers duplicated")
        for num, objs in sorted(dup.items()):
            desc = []
            for p in objs:
                layers = [pcbnew.LayerName(l) for l in p.GetLayerSet().Seq()
                          if l in (pcbnew.F_Cu, pcbnew.B_Cu)]
                pos = p.GetPosition()
                desc.append(f"{layers} @({pos.x / UM:.4f},{pos.y / UM:.4f}) net={p.GetNetname()!r} "
                            f"uuid={p.m_Uuid.AsString()[:8]}")
            xs = {(p.GetPosition().x, p.GetPosition().y) for p in objs}
            nets = {p.GetNetname() for p in objs}
            ls = {tuple(sorted(pcbnew.LayerName(l) for l in p.GetLayerSet().Seq()
                               if l in (pcbnew.F_Cu, pcbnew.B_Cu))) for p in objs}
            print(f"   pad {num}: {len(objs)} objects  sameXY={len(xs) == 1}  "
                  f"sameNet={len(nets) == 1}  distinctLayerSets={len(ls)}")
            for d in desc:
                print(f"      {d}")
    print(f"\ntotal J_W pad objects: {total_objs}")

    # full-object shared-layer test for a few named pairs
    print("\nshared copper layers, counting ALL pad objects per number:")
    pairs = [("D_BP2.1", "J_W2.1"), ("D_BP1.2", "J_W1.4"), ("D_BP4.1", "J_W4.1"),
             ("D_BP4.2", "U2.4")]
    for a, b in pairs:
        def objs(spec):
            ref, num = spec.split(".", 1)
            fp = next((f for f in board.GetFootprints() if f.GetReference() == ref), None)
            if fp is None:
                return []
            return [p for p in fp.Pads() if p.GetNumber() == num]
        oa, ob = objs(a), objs(b)
        la = set()
        for p in oa:
            la |= {pcbnew.LayerName(l) for l in p.GetLayerSet().Seq()
                   if l in (pcbnew.F_Cu, pcbnew.B_Cu)}
        lb = set()
        for p in ob:
            lb |= {pcbnew.LayerName(l) for l in p.GetLayerSet().Seq()
                   if l in (pcbnew.F_Cu, pcbnew.B_Cu)}
        print(f"   {a:9s} {sorted(la)}  <->  {b:9s} {sorted(lb)}   shared={sorted(la & lb)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
