#!/usr/bin/env python3
"""Geometric open count for an unrouted board, independent of DRC's path model."""
import collections, sys
import pcbnew as p
b = p.LoadBoard(sys.argv[1])
pads = collections.defaultdict(list)
for f in b.GetFootprints():
    for pad in f.Pads():
        if pad.GetNumber():
            pads[pad.GetNetname()].append(pad)
opens = 0
for net, ps in pads.items():
    parent = list(range(len(ps)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            if ps[i].GetBoundingBox().Intersects(ps[j].GetBoundingBox()):
                parent[find(i)] = find(j)
    opens += len({find(i) for i in range(len(ps))}) - 1
print('geometric_opens', opens, 'nets_with_pads', len(pads),
      'multi_pad_nets', sum(1 for v in pads.values() if len(v) > 1))
