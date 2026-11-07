#!/usr/bin/env python3
"""Per-record GEOMETRY of the 23 missing-copper targets.

For each native unconnected record, resolve BOTH endpoints to the same-net copper ISLAND they
belong to, then measure:
  * the exact minimum gap between those two islands (polygon-to-polygon, all layers)
  * the island sizes and where their nearest points are

That number decides the work: a 0.1-1.5 mm stub gap is a single segment; a multi-mm haul with
congested terrain is a different job. Nothing is inferred -- every distance comes from
KiCad's own effective shapes, and the island partition is built with the same predicate
native DRC uses (same-layer collision, or a through-via/PTH pad bridging layers).

Zones are included as their FILLED polygons per layer.
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
F, B, I1, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu


def shp_poly(q, layer):
    ps = pcbnew.SHAPE_POLY_SET()
    q.TransformShapeToPolygon(ps, layer, 0, 100, pcbnew.ERROR_INSIDE)

    def coords(c):
        return [(v.x / UM, v.y / UM) for v in c.CPoints()]
    if ps.OutlineCount() == 0:
        return None
    return unary_union([Polygon(coords(ps.COutline(i)),
                               [coords(ps.CHole(i, j)) for j in range(ps.HoleCount(i))])
                        for i in range(ps.OutlineCount())])


class Net:
    """Island partition + geometry for ONE net, built from native shapes."""

    def __init__(self, board, netname):
        self.b = board
        self.net = netname
        self.nodes = {}       # key -> dict(poly, layer, uuid, kind, name)
        self.adj = defaultdict(set)
        self._build()

    def _add(self, key, poly, layer, uuid, kind, name, is_pth=False, is_via=False):
        self.nodes[key] = {"poly": poly, "layer": layer, "uuid": uuid,
                           "kind": kind, "name": name,
                           "pth": is_pth, "via": is_via}

    def _build(self):
        b, net = self.b, self.net
        items = ([q for f in b.GetFootprints() for q in f.Pads()]
                 + list(b.GetTracks()))
        by_uuid = {}
        for q in items:
            if q.GetNetname() != net:
                continue
            by_uuid[q.m_Uuid.AsString()] = q
            for lid in q.GetLayerSet().CuStack():
                if lid not in (F, B, I1, I2):
                    continue
                poly = shp_poly(q, lid)
                if poly is None:
                    continue
                if isinstance(q, pcbnew.PAD):
                    kind, name = "PAD", f"{q.GetParentFootprint().GetReference()}.{q.GetNumber()}"
                    pth = q.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
                elif isinstance(q, pcbnew.PCB_VIA):
                    kind, name, pth = "VIA", "VIA", False
                else:
                    kind, name, pth = "TRACK", "TRACK", False
                self._add(f"{q.m_Uuid.AsString()}:{lid}", poly, lid,
                          q.m_Uuid.AsString(), kind, name, pth,
                          isinstance(q, pcbnew.PCB_VIA))
        # zones: filled polygons per layer
        for z in b.Zones():
            if z.GetNetname() != net:
                continue
            for lid in z.GetLayerSet().CuStack():
                if lid not in (F, B, I1, I2):
                    continue
                try:
                    ps = z.GetFilledPolysList(lid)
                except Exception:
                    continue
                if ps.OutlineCount() == 0:
                    continue
                for i in range(ps.OutlineCount()):
                    poly = shp_poly_of_polyset(ps, i)
                    if poly is None:
                        continue
                    self._add(f"{z.m_Uuid.AsString()}:{lid}:p{i}", poly, lid,
                              z.m_Uuid.AsString(), "ZONE",
                              f"ZONE[{z.GetZoneName() or '?'}]")

        keys = sorted(self.nodes)
        for i, a in enumerate(keys):
            na = self.nodes[a]
            for c in keys[i + 1:]:
                nc = self.nodes[c]
                if na["layer"] == nc["layer"]:
                    if na["poly"].distance(nc["poly"]) <= 0.0:
                        self.adj[a].add(c)
                        self.adj[c].add(a)
                elif na["uuid"] == nc["uuid"] and (na["via"] or na["pth"]):
                    self.adj[a].add(c)
                    self.adj[c].add(a)

        self.comp = {}
        self.groups = []
        for k in keys:
            if k in self.comp:
                continue
            stack = [k]
            self.comp[k] = len(self.groups)
            seen = [k]
            while stack:
                for j in self.adj[stack.pop()]:
                    if j not in self.comp:
                        self.comp[j] = len(self.groups)
                        seen.append(j)
                        stack.append(j)
            self.groups.append(sorted(seen))

    def group_of_item(self, uuid_str, layer_name):
        lay = {"F.Cu": F, "B.Cu": B, "In1.Cu": I1, "In2.Cu": I2}[layer_name]
        for k in self.nodes:
            n = self.nodes[k]
            if n["uuid"] == uuid_str and n["layer"] == lay:
                return self.comp[k]
        # fall back: any layer of that uuid
        for k in self.nodes:
            if self.nodes[k]["uuid"] == uuid_str:
                return self.comp[k]
        return None

    def group_geom(self, gi):
        polys = [self.nodes[k]["poly"] for k in self.groups[gi]]
        return unary_union(polys)

    def describe(self, gi):
        pads = sorted({self.nodes[k]["name"] for k in self.groups[gi]
                       if self.nodes[k]["kind"] == "PAD"})
        lay = sorted({pcbnew.LayerName(self.nodes[k]["layer"])
                      for k in self.groups[gi]})
        return {"pads": pads, "layers": lay,
                "tracks": sum(1 for k in self.groups[gi] if self.nodes[k]["kind"] == "TRACK"),
                "vias": sum(1 for k in self.groups[gi] if self.nodes[k]["kind"] == "VIA"),
                "zones": sum(1 for k in self.groups[gi] if self.nodes[k]["kind"] == "ZONE")}


def shp_poly_of_polyset(ps, i):
    def coords(c):
        return [(v.x / UM, v.y / UM) for v in c.CPoints()]
    sub = ps.UnitSet(i)
    if sub is None or sub.OutlineCount() == 0:
        return None
    return Polygon(coords(sub.COutline(0)))


def main(board_path, drc_path, target_nets):
    b = pcbnew.LoadBoard(board_path)
    d = json.load(open(drc_path))
    recs = d["unconnected_items"]

    import re
    def parse(desc):
        m = re.match(r"^(?:PTH )?[Pp]ad (\S+) \[(.*?)\] of (\S+)(?: on (\S+))?$", desc)
        if m:
            return {"kind": "pad", "num": m.group(1), "net": m.group(2),
                    "ref": m.group(3), "layer": m.group(4), "desc": desc}
        m = re.match(r"^Track \[(.*?)\] on (\S+), length ([\d.]+) mm$", desc)
        if m:
            return {"kind": "track", "net": m.group(1), "layer": m.group(2), "desc": desc}
        m = re.match(r"^Via \[(.*?)\] on (\S+) - (\S+)$", desc)
        if m:
            return {"kind": "via", "net": m.group(1), "desc": desc}
        m = re.match(r"^Zone '(\S+)' \[(.*?)\] on (\S+), priority (\d+)$", desc)
        if m:
            return {"kind": "zone", "name": m.group(1), "net": m.group(2),
                    "layer": m.group(3), "desc": desc}
        return {"kind": "?", "desc": desc}

    caches = {}
    out = []
    for i, r in enumerate(recs, 1):
        ends = [parse(it["description"]) for it in r["items"]]
        netnames = {e.get("net") for e in ends if e.get("net")}
        if len(netnames) != 1:
            print(f"R{i:02d}: MULTI-NET {netnames} -- skipped")
            continue
        net = netnames.pop()
        if net not in target_nets:
            continue
        if net not in caches:
            caches[net] = Net(b, net)
        N = caches[net]
        # resolve each end to its island via the DRC item UUID
        gis = []
        for e, it in zip(ends, r["items"]):
            u = it["uuid"]
            gi = N.group_of_item(u, e.get("layer") or "F.Cu")
            gis.append(gi)
        line = {"record": i, "net": net, "ends": [e["desc"] for e in ends],
                "islands": gis}
        if None in gis:
            line["verdict"] = "UNRESOLVED ISLAND"
            print(f"R{i:02d} {net:14s} UNRESOLVED island for an endpoint")
            out.append(line)
            continue
        ga, gb = gis
        if ga == gb:
            line["verdict"] = "SAME ISLAND (record is stale or intra-island)"
            print(f"R{i:02d} {net:14s} both ends already in island {ga} -- record stale")
            out.append(line)
            continue
        A = N.group_geom(ga)
        Bg = N.group_geom(gb)
        gap = A.distance(Bg)
        pa, pb = nearest_points_pair(A, Bg)
        da, db = N.describe(ga), N.describe(gb)
        line.update({"gap_mm": round(gap, 4),
                     "nearest_a": [round(v, 3) for v in pa],
                     "nearest_b": [round(v, 3) for v in pb],
                     "island_a": da, "island_b": db})
        out.append(line)
        print(f"R{i:02d} {net:14s} gap={gap:6.3f} mm  "
              f"({pa[0]:.2f},{pa[1]:.2f})->({pb[0]:.2f},{pb[1]:.2f})")
        print(f"      A island {ga}: pads={da['pads'][:6]} layers={da['layers']} "
              f"trk={da['tracks']} via={da['vias']} zone={da['zones']}")
        print(f"      B island {gb}: pads={db['pads'][:6]} layers={db['layers']} "
              f"trk={db['tracks']} via={db['vias']} zone={db['zones']}")
        print(f"      ends: {line['ends'][0]}  ||  {line['ends'][1]}")
    json.dump(out, open(os.path.join(HERE, "targets.json"), "w"), indent=1)


def nearest_points_pair(A, Bg):
    from shapely.ops import nearest_points
    p, q = nearest_points(A, Bg)
    return (p.x, p.y), (q.x, q.y)


if __name__ == "__main__":
    nets = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    main(sys.argv[1], sys.argv[2], nets)
