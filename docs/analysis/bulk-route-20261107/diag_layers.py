#!/usr/bin/env python3
"""Which copper layer ids does this board actually use? Printed, never assumed.

A KeyError on layer id 4 during raster marking means some copper item claims a layer the
raster does not model. That is information: either the board carries inner-layer copper
(raster must model it, or such items must be excluded and the exclusion stated) or the id
mapping assumed by LIDX is wrong.
"""
import collections
import sys

import pcbnew

UM = 1e6


def main(path):
    b = pcbnew.LoadBoard(path)
    print("enabled copper:", b.GetCopperLayerCount())
    for lid in b.GetEnabledLayers().CuStack():
        print(f"  id={lid:3d} name={pcbnew.LayerName(lid)}")

    c = collections.Counter()
    for t in b.GetTracks():
        c[t.GetLayer()] += 1
    print("\ntrack layer histogram (id: count):", dict(sorted(c.items())))
    for lid in sorted(c):
        print(f"  id={lid} name={pcbnew.LayerName(lid)} count={c[lid]}")

    pads = collections.Counter()
    for f in b.GetFootprints():
        for p in f.Pads():
            for lid in p.GetLayerSet().Seq():
                if lid <= 31:
                    pads[lid] += 1
    print("\npad layer histogram (id: count):", dict(sorted(pads.items())))
    for lid in sorted(pads):
        print(f"  id={lid} name={pcbnew.LayerName(lid)} count={pads[lid]}")


if __name__ == "__main__":
    main(sys.argv[1])
