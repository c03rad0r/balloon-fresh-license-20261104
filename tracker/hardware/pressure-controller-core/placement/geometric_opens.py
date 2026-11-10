#!/usr/bin/env python3
"""Geometric open count for an unrouted board, independent of DRC's path model.

Opens are counted per net as (number of connected copper islands) - 1, where two
same-net pads are in the same island only if their real pad shapes collide (stacked,
interleaved or shield pads share an island without any track). The printed identity is
the accounting check: opens == pads - merges - nets_with_pads.

Why this is not "endpoints - nets": a footprint may carry several pads with the SAME
number (USB shell `S1` x4, ESP32 thermal `41` x13, WSON `9` x4, switch legs), so the board
holds more pads than the netlist has endpoints, and adjacent same-net pads touch each
other. Both effects are reported, never assumed.
"""
import collections, sys
import pcbnew as p

b = p.LoadBoard(sys.argv[1])
pads = collections.defaultdict(list)
stacked = collections.Counter()
for f in b.GetFootprints():
    for pad in f.Pads():
        num = pad.GetNumber()
        if not num:
            continue
        pads[pad.GetNetname()].append(pad)
        # Duplicate pad numbers are a WITHIN-FOOTPRINT property (USB shell S1 x4,
        # ESP32 thermal 41 x13); keying globally would count every part's pad "1".
        stacked[(f.GetReference(), num, pad.GetNetname())] += 1
duplicates = sum(c - 1 for c in stacked.values() if c > 1)

opens = merges = 0
for net, ps in pads.items():
    parent = list(range(len(ps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            a, c = ps[i], ps[j]
            if a.GetEffectiveShape(a.GetLayer()).Collide(c.GetEffectiveShape(c.GetLayer()), 0):
                parent[find(i)] = find(j)
    islands = len({find(i) for i in range(len(ps))})
    opens += islands - 1
    merges += len(ps) - islands

npads, nnets = sum(len(v) for v in pads.values()), len(pads)
if len(sys.argv) > 2:
    import json
    per_net = {net: sum(1 for _ in ps) for net, ps in pads.items()}
    detail = {}
    for net, ps in pads.items():
        parent = list(range(len(ps)))

        def f2(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                a, c = ps[i], ps[j]
                if a.GetEffectiveShape(a.GetLayer()).Collide(c.GetEffectiveShape(c.GetLayer()), 0):
                    parent[f2(i)] = f2(j)
        detail[net] = len({f2(i) for i in range(len(ps))}) - 1
    from pathlib import Path as _P
    _P(sys.argv[2]).write_text(json.dumps(detail, indent=2, sort_keys=True) + '\n')
assert opens == npads - merges - nnets, (opens, npads, merges, nnets)
print('geometric_opens', opens, 'pads', npads, 'merges', merges, 'nets', nnets,
      'stacked_duplicate_pads', duplicates,
      'multi_pad_nets', sum(1 for v in pads.values() if len(v) > 1))
