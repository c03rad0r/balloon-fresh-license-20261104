#!/usr/bin/env python3
"""Independent physical copper graph; individual filled islands, never zone UUID union.
Native KiCad polygonization with 100 nm maximum error; polygon intersections in Shapely.
Pads bridge their own copper layers; no interlayer zone bridging by net name.
"""
import itertools
import pcbnew
from shapely.geometry import Polygon


def polygons(s):
    def ring(r):
        return [(r.CPoint(i).x, r.CPoint(i).y) for i in range(r.PointCount())]
    return [Polygon(ring(s.COutline(i)), [ring(s.CHole(i,j)) for j in range(s.HoleCount(i))])
            for i in range(s.OutlineCount())]


def partitions(path):
    b = pcbnew.LoadBoard(str(path))
    assert b.GetCopperLayerCount() == 2, 'only two-copper-layer boards supported'
    nodes = []
    def add(item, layer, pad=None):
        s = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(s, layer, 0, 100, pcbnew.ERROR_INSIDE)
        for poly in polygons(s):
            nodes.append((item.GetNetname(), layer, poly, pad))
    for f in b.GetFootprints():
        for p in f.Pads():
            if not p.GetNetname(): continue
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(layer): add(p, layer, p.m_Uuid.AsString())
    for t in b.GetTracks():
        assert not isinstance(t, pcbnew.PCB_VIA), 'via graph not implemented: fail closed'
        add(t, t.GetLayer())
    for z in b.Zones():
        if z.GetIsRuleArea(): continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if z.IsOnLayer(layer):
                for poly in polygons(z.GetFilledPolysList(layer)):
                    nodes.append((z.GetNetname(), layer, poly, None))
    parent=list(range(len(nodes)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    for i,a in enumerate(nodes):
        for j in range(i):
            c=nodes[j]
            if a[0]==c[0] and ((a[3] and a[3]==c[3]) or (a[1]==c[1] and a[2].intersects(c[2]))):
                parent[root(i)]=root(j)
    groups={}
    for i,n in enumerate(nodes):
        if n[3]: groups.setdefault(n[0],{}).setdefault(root(i),set()).add(n[3])
    return {net: sorted([sorted(v) for v in g.values()]) for net,g in sorted(groups.items())}


def splits(before, after):
    return [{'net':net,'pads':g} for net,groups in before.items() for g in groups
            if not any(set(g)<=set(h) for h in after.get(net,[]))]


def pairs(groups):
    return sum(len(g)*(len(g)-1)//2 for v in groups.values() for g in v)
