#!/usr/bin/env python3
"""Resolve the C10.1 disagreement with KiCad's OWN connectivity, via GetConnectedPadsAndVias.

The control experiment already answered the headline: removing C10 leaves the open count at
38, so native DRC does NOT treat C10.1 as an unconnected island. That is surprising -- the
pad has no same-net copper within 0.25 mm on F.Cu -- so the mechanism must be identified
rather than assumed. Candidates: (a) the In2.Cu +3V3 plane connects it through a
through-hole something, (b) DRC's ratsnest merges a 3-island net into fewer records, or
(c) C10.1 really is floating and DRC reports it inside one of the +3V3 records.

This prints C10.1's actual connected pad/via set and, for the +3V3 record, BOTH endpoints,
so (b) and (c) are distinguishable.
"""
import sys

import pcbnew

UM = 1e6


def shape_neighbours(b, pad):
    """Exact same-net F.Cu neighbours of a pad, using KiCad effective shapes."""
    from shapely.geometry import Polygon
    out = {}
    shp = pad.GetEffectiveShape(pcbnew.F_Cu)
    for f in b.GetFootprints():
        for q in f.Pads():
            if q is pad or q.GetNetname() != pad.GetNetname():
                continue
            if not q.GetLayerSet().Contains(pcbnew.F_Cu):
                continue
            if shp.Collide(q.GetEffectiveShape(pcbnew.F_Cu), 0):
                out[str(q)] = (q, "pad")
    for t in b.GetTracks():
        if t.GetNetname() != pad.GetNetname():
            continue
        layers = ([pcbnew.F_Cu, pcbnew.B_Cu] if isinstance(t, pcbnew.PCB_VIA)
                  else [t.GetLayer()])
        if pcbnew.F_Cu not in layers:
            continue
        w = (t.GetWidth(pcbnew.F_Cu) if isinstance(t, pcbnew.PCB_VIA) else t.GetWidth())
        if shp.Collide(t.GetEffectiveShape(pcbnew.F_Cu), int(w / 2)):
            out[str(t)] = (t, "via" if isinstance(t, pcbnew.PCB_VIA) else "trk")
    return out, {}


def describe(q):
    if isinstance(q, pcbnew.PAD):
        return (f"PAD {q.GetParentFootprint().GetReference()}.{q.GetNumber()} "
                f"[{q.GetNetname()}] attr={q.GetAttribute()}")
    if isinstance(q, pcbnew.PCB_VIA):
        p = q.GetPosition()
        return f"VIA ({p.x/UM:.3f},{p.y/UM:.3f}) dia={q.GetWidth(pcbnew.F_Cu)/UM:.2f}"
    return type(q).__name__


def main(board_path):
    b = pcbnew.LoadBoard(board_path)
    conn = b.GetConnectivity()
    pads, vias = [], []
    for ref, num in (("C10", "1"), ("C10", "2"), ("R_F1", "1")):
        fp = b.FindFootprintByReference(ref)
        p = [x for x in fp.Pads() if x.GetNumber() == num][0]
        pads, vias = [], []
        try:
            conn.GetConnectedPadsAndVias(p, pads, vias)
        except TypeError:
            # swig needs real std::vector wrappers; fall back to the shape-level query
            pads, vias = shape_neighbours(b, p)
        print(f"\n{ref}.{num} [{p.GetNetname()}]")
        print(f"   connected items ({len(pads)}): {sorted(describe(x) for x in pads)}")

    # ratsnest: which pads of +3V3 does KiCad consider already joined?
    print("\n+3V3 pads grouped by connected-pad set (KiCad's own view):")
    groups = {}
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != "+3V3":
                continue
            pp, vv = [], []
            try:
                conn.GetConnectedPadsAndVias(p, pp, vv)
            except TypeError:
                pp, vv = shape_neighbours(b, p)
            key = frozenset(describe(x) for x in pp)
            groups.setdefault(key, []).append(f"{f.GetReference()}.{p.GetNumber()}")
    for i, (k, members) in enumerate(groups.items()):
        print(f"   island {i}: {sorted(members)}")
        print(f"      via its connected pad set ({len(k)}): {sorted(k)}")


if __name__ == "__main__":
    main(sys.argv[1])
