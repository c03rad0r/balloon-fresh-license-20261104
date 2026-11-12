#!/usr/bin/env python3
"""Compare COPPER between two board files: is a cosmetic/zone edit actually copper-neutral?

Reports per board: sha256, footprint/pad/track/via/zone counts, unconnected count from KiCad's own
connectivity engine, and a canonical geometry multiset for pads, track segments, arcs, vias and
zones (net, layer, endpoints, width, size). Zone FILLED AREA is reported separately because a zone
refill legitimately changes it while the copper objects stay identical.

The distinction matters: "copper identical" is a claim about objects, and a refill changes bytes,
filled polygons and areas without changing a single track, pad or via. Reporting one as the other
is how a cosmetic repair gets mistaken for a routing change (or a routing change hides behind one).

Usage: compare_copper.py <boardA> <boardB>
Exit 0 = copper objects identical, 1 = different, 2 = usage/load failure.
"""
import hashlib
import sys

import pcbnew

UM = 1_000_000.0


def uv(v):
    return round(v / UM, 4)


def signature(path):
    b = pcbnew.LoadBoard(path)
    if b is None:
        return None
    sig = {"segments": [], "arcs": [], "vias": [], "pads": [], "zones": []}
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            sig["vias"].append((uv(t.GetPosition().x), uv(t.GetPosition().y),
                                uv(t.GetWidth(pcbnew.F_Cu)), uv(t.GetDrillValue()),
                                t.GetLayer(), t.GetNetname()))
        elif t.Type() == pcbnew.PCB_ARC_T:
            sig["arcs"].append((uv(t.GetStart().x), uv(t.GetStart().y),
                                uv(t.GetEnd().x), uv(t.GetEnd().y),
                                uv(t.GetMid().x), uv(t.GetMid().y),
                                uv(t.GetWidth()), t.GetLayer(), t.GetNetname()))
        else:
            sig["segments"].append((uv(t.GetStart().x), uv(t.GetStart().y),
                                    uv(t.GetEnd().x), uv(t.GetEnd().y),
                                    uv(t.GetWidth()), t.GetLayer(), t.GetNetname()))
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            pos = p.GetPosition()
            sig["pads"].append((ref, p.GetNumber(), uv(pos.x), uv(pos.y),
                                uv(p.GetSize().x), uv(p.GetSize().y), p.GetNetname()))
    areas = []
    for z in b.Zones():
        outline = z.Outline()
        verts = []
        for i in range(outline.OutlineCount()):
            c = outline.Outline(i)
            for j in range(c.PointCount()):
                pt = c.CPoint(j)
                verts.append((uv(pt.x), uv(pt.y)))
        sig["zones"].append((z.GetNetname(), outline.OutlineCount(), tuple(sorted(verts))))
        areas.append((z.GetNetname(), round(z.GetFilledArea() / 1e12, 4)))
    for k in sig:
        sig[k].sort(key=repr)
    b.BuildConnectivity()
    sig["unconnected"] = b.GetConnectivity().GetUnconnectedCount(False)
    sig["zone_fill_areas"] = sorted(areas)
    sig["sha256"] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    sig["path"] = path
    return sig


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a, b = signature(sys.argv[1]), signature(sys.argv[2])
    if a is None or b is None:
        print("FAIL: could not load one of the boards")
        return 2
    for name, s in (("A", a), ("B", b)):
        print(f"{name}: pads={len(s['pads'])} segments={len(s['segments'])} "
              f"arcs={len(s['arcs'])} vias={len(s['vias'])} zones={len(s['zones'])} "
              f"unconnected={s['unconnected']}")
        print(f"   sha256 {s['sha256']}  {s['path']}")
    same = True
    for k in ("segments", "arcs", "vias", "pads", "zones"):
        if a[k] == b[k]:
            print(f"  COPPER IDENTICAL: {k} ({len(a[k])})")
        else:
            same = False
            only_a = [x for x in a[k] if x not in b[k]]
            only_b = [x for x in b[k] if x not in a[k]]
            print(f"  COPPER DIFFERS: {k}: onlyA={len(only_a)} onlyB={len(only_b)}")
            for x in only_a[:5]:
                print("     onlyA:", x)
            for x in only_b[:5]:
                print("     onlyB:", x)
    if a["zone_fill_areas"] != b["zone_fill_areas"]:
        print("  ZONE FILL AREAS differ (legitimate after a refill; objects above are the "
              "authority on copper):")
        for x, y in zip(a["zone_fill_areas"], b["zone_fill_areas"]):
            if x != y:
                print(f"     {x[0]}: {x[1]} -> {y[1]} mm2")
    else:
        print("  ZONE FILL AREAS identical")
    print("VERDICT:", "COPPER-IDENTICAL" if same else "COPPER-CHANGED")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
