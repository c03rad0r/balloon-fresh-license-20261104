#!/usr/bin/env python3
"""Independent physical copper graph; individual filled islands, never zone UUID union.
Native KiCad polygonization with 100 nm maximum error; polygon intersections in Shapely.
Pads bridge their own copper layers; no interlayer zone bridging by net name.

VIAS ARE MODELLED (2026-11-11). This module used to `assert not isinstance(t, PCB_VIA)` and
fail closed, which was right while every board in this campaign was via-free: a via graph that
guesses is worse than one that refuses. The I2C batch places plated through-vias, so the graph
now models the one thing a via physically IS -- a barrel joining the SAME net's copper on every
copper layer it spans -- through an explicit BRIDGE key, kept separate from the PAD-MEMBERSHIP
key so a via can never fabricate a pad group or a between-pad pair.

Bridges join nodes that share a key AND a net. They never join across nets, and they never join
by net NAME across space (that is the zone-UUID union this module exists to avoid).
test_physical_partitions.py removes a via barrel and requires its net to split, so the model
cannot be vacuously permissive.
"""
import pcbnew
from shapely.geometry import Polygon


def polygons(s):
    def ring(r):
        return [(r.CPoint(i).x, r.CPoint(i).y) for i in range(r.PointCount())]
    return [Polygon(ring(s.COutline(i)), [ring(s.CHole(i,j)) for j in range(s.HoleCount(i))])
            for i in range(s.OutlineCount())]


def partitions(path):
    """Return net -> list of pad groups (each a sorted list of pad identities)."""
    b = pcbnew.LoadBoard(str(path))
    assert b.GetCopperLayerCount() == 2, 'only two-copper-layer boards supported'
    # node = (netname, layer, polygon, pad_key, bridge_key)
    nodes = []

    def add(item, layer, pad=None, bridge=None):
        s = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(s, layer, 0, 100, pcbnew.ERROR_INSIDE)
        for poly in polygons(s):
            nodes.append((item.GetNetname(), layer, poly, pad, bridge))

    for f in b.GetFootprints():
        for p in f.Pads():
            if not p.GetNetname():
                continue
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(layer):
                    add(p, layer, pad=p.m_Uuid.AsString(), bridge='pad:' + p.m_Uuid.AsString())
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            # A plated through-via is a barrel across every copper layer it spans. Its own
            # net only -- GETNETNAME is the via's assigned net, never inferred from geometry.
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if t.IsOnLayer(layer):
                    add(t, layer, bridge='via:' + t.m_Uuid.AsString())
        else:
            add(t, t.GetLayer())
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if z.IsOnLayer(layer):
                for poly in polygons(z.GetFilledPolysList(layer)):
                    nodes.append((z.GetNetname(), layer, poly, None, None))

    parent = list(range(len(nodes)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(nodes):
        for j in range(i):
            c = nodes[j]
            if a[0] != c[0]:
                continue
            same_bridge = a[4] is not None and a[4] == c[4]
            same_layer_contact = a[1] == c[1] and a[2].intersects(c[2])
            if same_bridge or same_layer_contact:
                parent[root(i)] = root(j)

    groups = {}
    for i, n in enumerate(nodes):
        if n[3]:
            groups.setdefault(n[0], {}).setdefault(root(i), set()).add(n[3])
    return {net: sorted([sorted(v) for v in g.values()]) for net, g in sorted(groups.items())}


def splits(before, after):
    return [{'net':net,'pads':g} for net,groups in before.items() for g in groups
            if not any(set(g)<=set(h) for h in after.get(net,[]))]


def pairs(groups):
    return sum(len(g)*(len(g)-1)//2 for v in groups.values() for g in v)
