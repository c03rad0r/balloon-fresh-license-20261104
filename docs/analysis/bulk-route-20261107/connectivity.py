#!/usr/bin/env python3
"""Per-net copper COMPONENT graph of the candidate board, using NATIVE shapes.

The DRC's unconnected records pair two items from DIFFERENT components -- they do not
report "the gap". So the routing targets cannot be read off the DRC; they come from this
graph: which same-net copper islands exist, and which of them are assembly-conditional
(two faces of one edge-launched land) rather than missing copper.

Connectivity predicate is deliberately the same one native DRC uses:
  same layer            -> shape collision at 0 clearance
  different layer       -> only a through-via or a PTH pad bridges them
Zones are included as separate polygon nodes (filled polys), never as one blob.
"""
import json
import os
import sys
from collections import defaultdict

import pcbnew
from shapely.geometry import Polygon
from shapely.ops import unary_union

UM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))


def uid(q):
    return q.m_Uuid.AsString()


def poly_of(ps):
    def coords(c):
        return [(v.x / UM, v.y / UM) for v in c.CPoints()]
    return unary_union([Polygon(coords(ps.COutline(i)),
                                [coords(ps.CHole(i, j)) for j in range(ps.HoleCount(i))])
                        for i in range(ps.OutlineCount())])


def build(board_path, nets):
    b = pcbnew.LoadBoard(board_path)
    if b is None:
        raise SystemExit(f"REFUSED: cannot load {board_path}")

    nodes = {}          # key -> dict
    shapes = {}
    objs = {}
    items = ([q for f in b.GetFootprints() for q in f.Pads()]
             + list(b.GetTracks())
             + [q for f in b.GetFootprints() for q in f.GraphicalItems()
                if q.GetLayerSet().CuStack()])
    for q in items:
        if q.GetNetname() and q.GetNetname() not in nets:
            continue
        k = uid(q)
        objs[k] = q
        for l in q.GetLayerSet().CuStack():
            if not b.IsLayerEnabled(l):
                continue
            key = f"{k}:{l}"
            ps = pcbnew.SHAPE_POLY_SET()
            q.TransformShapeToPolygon(ps, l, 0, 100, pcbnew.ERROR_INSIDE)
            if isinstance(q, pcbnew.PAD):
                name = f"{q.GetParentFootprint().GetReference()}.{q.GetNumber()}"
                ntype = "PAD"
            elif isinstance(q, pcbnew.PCB_VIA):
                name = "VIA"
                ntype = "VIA"
            elif isinstance(q, pcbnew.PCB_TRACK):
                name = "TRACK"
                ntype = "TRACK"
            else:
                name = "GFX"
                ntype = "GFX"
            nodes[key] = {"uuid": k, "layer": l, "layer_name": b.GetLayerName(l),
                          "net": q.GetNetname(), "type": ntype, "name": name,
                          "area": round(geom_area(ps), 4)}
            shapes[key] = q.GetEffectiveShape(l)
            objs.setdefault("_geo", {})[key] = geom_area(ps)

    for z in b.Zones():
        if z.GetNetname() not in nets:
            continue
        for l in z.GetLayerSet().CuStack():
            ps = z.GetFilledPolysList(l)
            for i in range(ps.OutlineCount()):
                key = f"{uid(z)}:{l}:poly{i}"
                sub = ps.UnitSet(i)
                shapes[key] = sub
                nodes[key] = {"uuid": uid(z), "layer": l, "layer_name": b.GetLayerName(l),
                              "net": z.GetNetname(), "type": "polygon",
                              "name": f"ZONE[{z.GetZoneName() or '?'}]",
                              "area": round(geom_area(sub), 4)}

    keys = sorted(nodes)
    adj = {k: set() for k in keys}
    edges = []
    for i, a in enumerate(keys):
        na = nodes[a]
        for c in keys[i + 1:]:
            nc = nodes[c]
            if na["net"] != nc["net"]:
                continue
            if na["layer_name"] != nc["layer_name"]:
                if na["uuid"] != nc["uuid"]:
                    continue          # different items cannot bridge layers
                q = objs[na["uuid"]]
                hit = isinstance(q, pcbnew.PCB_VIA) or (
                    isinstance(q, pcbnew.PAD)
                    and q.GetAttribute() == pcbnew.PAD_ATTRIB_PTH)
            else:
                hit = bool(shapes[a].Collide(shapes[c], 0))
            if hit:
                adj[a].add(c)
                adj[c].add(a)
                edges.append([a, c])
    return b, nodes, adj, edges


def geom_area(ps):
    try:
        return poly_of(ps).area
    except Exception:
        return 0.0


def components(adj):
    comp = {}
    groups = []
    for k in adj:
        if k in comp:
            continue
        stack = [k]
        comp[k] = len(groups)
        seen = [k]
        while stack:
            for j in adj[stack.pop()]:
                if j not in comp:
                    comp[j] = len(groups)
                    seen.append(j)
                    stack.append(j)
        groups.append(sorted(seen))
    return groups


def describe(nodes, group):
    pads = defaultdict(list)
    tracks = 0
    vias = 0
    polys = 0
    bbox = [1e9, 1e9, -1e9, -1e9]
    for k in group:
        n = nodes[k]
        if n["type"] == "PAD":
            pads[n["name"] + ("[F]" if n["layer_name"] == "F.Cu" else
                              "[B]" if n["layer_name"] == "B.Cu" else
                              f"[{n['layer_name']}]")].append(k)
        elif n["type"] == "TRACK":
            tracks += 1
        elif n["type"] == "VIA":
            vias += 1
        else:
            polys += 1
    return {"pads": sorted(pads), "tracks": tracks, "vias": vias, "polys": polys,
            "n_nodes": len(group)}


def main():
    board_path = sys.argv[1]
    netfile = sys.argv[2] if len(sys.argv) > 2 else None
    b = pcbnew.LoadBoard(board_path)
    allnets = set()
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname():
                allnets.add(p.GetNetname())
    if netfile:
        nets = set(json.load(open(netfile)))
    else:
        nets = allnets
    b, nodes, adj, edges = build(board_path, nets)
    groups = components(adj)
    bynet = defaultdict(list)
    for gi, g in enumerate(groups):
        net = nodes[g[0]]["net"]
        bynet[net].append(gi)

    out = {}
    for net in sorted(bynet):
        cs = bynet[net]
        print(f"\n== {net}: {len(cs)} component(s)")
        rec = []
        for gi in cs:
            d = describe(nodes, groups[gi])
            d["id"] = gi
            rec.append(d)
            print(f"  C{gi}: pads={d['pads']} tracks={d['tracks']} vias={d['vias']} "
                  f"polys={d['polys']} nodes={d['n_nodes']}")
        out[net] = rec
    json.dump(out, open(os.path.join(HERE, "components.json"), "w"), indent=1)
    print(f"\n{len(groups)} groups over {len(bynet)} nets; {len(edges)} edges")


if __name__ == "__main__":
    main()
