#!/usr/bin/env python3
"""Zone-island inventory for the hub board at ISLAND granularity.

Attribution method: ZONE-POLYGON ENUMERATION + an independent copper graph.
It does NOT read, pair, or index DRC records. The prior attempt paired results to
DRC record indices and is invalid because DRC record identity is not deterministic
on identical bytes (5 runs, 86 records, only 65 distinct item-signatures).

Read-only on the source board. Refill happens on a copy with the .kicad_pro beside it.
Run with /usr/bin/python3 (KiCad 9.0.9 pcbnew), not a venv.

Phases
  1  refill a copy, assert the source sha256 is unchanged and the refill is a byte no-op
  2  enumerate filled-zone islands (net, layer, index, area, bbox, centroid, holes)
  3  independent copper graph -> components, per-net component counts
  4  classify each island CONNECTED (main body) / ISOLATED
  5  for isolated islands: nearest same-net copper + measured gap
  6  stitchability: candidate via site, foreign-copper clearance, other-layer landing
  7  cross-check Sigma(components-1) against DRC

Usage:
  /usr/bin/python3 run_island_inventory.py --out islands.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from collections import defaultdict

import pcbnew as k
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

STEM = 'hub_board_v10_lora1280_7of9'
CU_LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']

# ADR-141 canonical rules (verified present in the .kicad_pro; see report.md)
R_CLEAR = 0.20        # copper-to-copper clearance, netclass Default + frozen .kicad_dru
R_VIA_DIA = 0.50      # min via diameter (rules.min_via_diameter)
R_VIA_R = R_VIA_DIA / 2.0
R_EDGE = 0.50         # copper-to-edge
R_TRACK = 0.20        # min track width
R_DRILL = 0.20        # min through drill (ADR-141)
R_HOLE_CLEAR = 0.25   # hole-to-copper clearance (rules.min_hole_clearance)
VIA_DRILL_HALF = 0.15  # netclass Default via drill 0.30 mm / 2
TOL = 0.004           # mm; absorbs nm->mm rounding on "touching" tests only


# ----------------------------------------------------------------- primitives
def mm(v):
    return v / 1e6


def contour_pts(c):
    return [(mm(c.CPoint(i).x), mm(c.CPoint(i).y)) for i in range(c.PointCount())]


def polyset_to_shapely(s):
    out = []
    for i in range(s.OutlineCount()):
        outer = contour_pts(s.COutline(i))
        if len(outer) < 3:
            raise ValueError('Degenerate native outline: cannot preserve island identity')
        holes = [contour_pts(s.CHole(i, h)) for h in range(s.HoleCount(i))]
        holes = [h for h in holes if len(h) >= 3]
        p = Polygon(outer, holes)
        if not p.is_valid:
            # KiCad contours may retrace zero-area cuts. GEOS make_valid retains
            # those cuts as lines: only accept normalization to ONE polygon with
            # unchanged area, never buffer(0)'s silent splitting/deletion.
            from shapely import make_valid
            fixed = make_valid(p)
            parts = list(fixed.geoms) if hasattr(fixed, 'geoms') else [fixed]
            polygons = [g for g in parts if g.geom_type == 'Polygon']
            if len(polygons) != 1 or abs(polygons[0].area - p.area) > 1e-8:
                raise ValueError('Native polygon requires topology-changing repair')
            p = polygons[0]
        if p.is_empty:
            raise ValueError('Empty native outline: cannot preserve island identity')
        out.append(p)
    return out


# Native polygon tessellation budget: 1 nm, inscribed copper. This is still
# polygon geometry, not native connectivity membership.
SHAPE_ERROR_IU = 1


def hole_poly(item):
    if isinstance(item, k.PAD):
        ps = k.SHAPE_POLY_SET()
        item.TransformHoleToPolygon(ps, 0, SHAPE_ERROR_IU, k.ERROR_OUTSIDE)
        return unary_union(polyset_to_shapely(ps))
    if isinstance(item, k.PCB_VIA):
        # Via drills are circular. Circumscribe so no drill void becomes copper.
        import math
        n = 1024
        r = mm(item.GetDrillValue()) / 2
        return Point(mm(item.GetPosition().x), mm(item.GetPosition().y)).buffer(
            r / math.cos(math.pi / (4*n)), quad_segs=n)
    return Polygon()


def native_copper(item, layer):
    ps = k.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, layer, 0, SHAPE_ERROR_IU, k.ERROR_INSIDE)
    geom = unary_union(polyset_to_shapely(ps))
    return geom.difference(hole_poly(item))


def track_poly(t):
    return native_copper(t, t.GetLayer())


def via_poly(t, layer=k.F_Cu):
    return native_copper(t, layer)


def drawing_poly(d):
    return native_copper(d, d.GetLayer())


def edge_segments(board):
    """Every Edge.Cuts segment on the board, INCLUDING footprint-internal ones.

    The breakaway tabs are drawn as Edge.Cuts shapes INSIDE the J_W* footprints, so
    board.GetDrawings() alone misses the tab walls. A via placed 0.45mm from the outer
    rectangle but 0.20mm from a tab wall is a real copper_edge_clearance violation.
    """
    segs = []
    for d in board.GetDrawings():
        if board.GetLayerName(d.GetLayer()) != 'Edge.Cuts':
            continue
        if d.GetShape() == k.SHAPE_T_SEGMENT:
            segs.append(LineString([(mm(d.GetStart().x), mm(d.GetStart().y)),
                                    (mm(d.GetEnd().x), mm(d.GetEnd().y))]))
        else:
            if d.GetShape() != k.SHAPE_T_RECT:
                raise ValueError('Unsupported Edge.Cuts shape; no bounding-box surrogate')
            a, b = d.GetStart(), d.GetEnd()
            segs.append(box(mm(min(a.x,b.x)), mm(min(a.y,b.y)),
                            mm(max(a.x,b.x)), mm(max(a.y,b.y))).exterior)
    for f in board.GetFootprints():
        for g in f.GraphicalItems():
            if board.GetLayerName(g.GetLayer()) != 'Edge.Cuts':
                continue
            if g.GetShape() == k.SHAPE_T_SEGMENT:
                segs.append(LineString([(mm(g.GetStart().x), mm(g.GetStart().y)),
                                        (mm(g.GetEnd().x), mm(g.GetEnd().y))]))
            else:
                if g.GetShape() != k.SHAPE_T_RECT:
                    raise ValueError('Unsupported footprint Edge.Cuts shape')
                a, b = g.GetStart(), g.GetEnd()
                segs.append(box(mm(min(a.x,b.x)), mm(min(a.y,b.y)),
                                mm(max(a.x,b.x)), mm(max(a.y,b.y))).exterior)
    return segs


def pad_poly(p, layer=k.F_Cu):
    return native_copper(p, layer)


# ----------------------------------------------------------------- phase 1
def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def refill_copy(src_dir: pathlib.Path, work: pathlib.Path):
    """Copy -> fill -> report. Source is never opened for write."""
    # Never remove earlier evidence or allow work to alias source.
    work.mkdir(parents=True, exist_ok=False)
    for f in src_dir.glob(STEM + '.kicad_*'):
        shutil.copy(f, work / f.name)
    for f in src_dir.glob('*.kicad_dru'):
        shutil.copy(f, work / f.name)

    src = src_dir / (STEM + '.kicad_pcb')
    dst = work / (STEM + '.kicad_pcb')
    before_src = sha256(src)
    before_dst = sha256(dst)

    b = k.LoadBoard(str(dst))
    filler = k.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    k.SaveBoard(str(dst), b)

    return dict(
        source_pcb=str(src),
        source_sha256=before_src,
        copy_sha256_before_fill=before_dst,
        copy_sha256_after_fill=sha256(dst),
        refill_byte_noop=(sha256(dst) == before_dst),
        source_unchanged=(sha256(src) == before_src),
        work_dir=str(work),
    )


# ----------------------------------------------------------------- phase 2
def enumerate_islands(board):
    """Filled-zone islands. One entry per SHAPE_POLY_SET outline (KiCad's own island unit)."""
    islands = []
    for zi, z in enumerate(board.Zones()):
        if z.GetIsRuleArea():
            continue
        lay_id = z.GetLayer()
        lay = board.GetLayerName(lay_id)
        if not z.HasFilledPolysForLayer(lay_id):
            continue
        fp = z.GetFilledPolysList(lay_id)
        n = fp.OutlineCount()
        zone_area = fp.Area() / 1e12
        shp_list = polyset_to_shapely(fp)
        for ii in range(n):
            one = fp.Subset(ii, ii + 1)
            area = one.Area() / 1e12
            shp = shp_list[ii] if ii < len(shp_list) else None
            if shp is None:
                continue
            cen = shp.centroid
            rp = shp.representative_point()
            minx, miny, maxx, maxy = shp.bounds
            islands.append(dict(
                island_id=f'{z.GetZoneName()}|{lay}|{ii}',
                zone_name=z.GetZoneName(),
                zone_uuid=z.m_Uuid.AsString(),
                zone_index=zi,
                net=z.GetNetname(),
                netcode=z.GetNetCode(),
                layer=lay,
                island_index=ii,
                region_count_in_zone=n,
                area_mm2=round(area, 6),
                zone_total_area_mm2=round(zone_area, 6),
                bbox_mm=[round(v, 6) for v in (minx, miny, maxx, maxy)],
                centroid_mm=[round(cen.x, 6), round(cen.y, 6)],
                interior_point_mm=[round(rp.x, 6), round(rp.y, 6)],
                holes=one.HoleCount(0),
                vertices=one.COutline(0).PointCount(),
                geom=shp,
            ))
    return islands


# ----------------------------------------------------------------- phase 3
def build_copper_graph(board, exclude_uuid=None, contact_tolerance=TOL, exclude_uuids=None):
    """Every copper body as (item, layer, geometry). Same-layer overlap unions;
    one conductor spanning layers is ONE node so barrels bridge layers.

    `exclude_uuids` is the multi-item form used by the no-via refill control: it
    removes EVERY listed barrel so a cluster's joins cannot be faked by the graph
    already seeing the vias it is meant to be testing.
    """
    exclude = set(exclude_uuids or ())
    if exclude_uuid:
        exclude.add(exclude_uuid)
    items = []
    nodes = []
    by_item = defaultdict(list)

    def add(kind, meta, net, netcode, layers, geom):
        iid = len(items)
        items.append(dict(id=iid, kind=kind, net=net, netcode=netcode,
                          layers=layers, meta=meta))
        for lay in layers:
            g = geom[lay] if isinstance(geom, dict) else geom
            if g is not None and not g.is_empty:
                by_item[iid].append(len(nodes))
                nodes.append((iid, lay, g))
        return iid

    # netcode 0: not a member of any net's components, but still REAL COPPER (and
    # sometimes a real hole). Dropping these is how an earlier version of this script
    # placed a via straight through U3 pads 9/10 and called it legal.
    netless_pads = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() <= 0:
                layers0 = [board.GetLayerName(l) for l in p.GetLayerSet().Seq()]
                layers0 = [l for l in layers0 if l in CU_LAYERS]
                if p.GetAttribute() == k.PAD_ATTRIB_PTH:
                    layers0 = list(CU_LAYERS)
                g0 = unary_union([pad_poly(p, board.GetLayerID(lay)) for lay in layers0])
                if layers0:
                    netless_pads.append((p, g0, mm(p.GetDrillSize().x) / 2.0, layers0))
                continue
            ls = [board.GetLayerName(l) for l in p.GetLayerSet().Seq()]
            ls = [l for l in ls if l in CU_LAYERS]
            if not ls:
                continue
            if p.GetAttribute() == k.PAD_ATTRIB_PTH:
                ls = list(CU_LAYERS)
            add('pad', dict(uuid=p.m_Uuid.AsString(), ref=f.GetReference(), num=p.GetNumber(),
                            attr=int(p.GetAttribute())),
                p.GetNetname(), p.GetNetCode(), ls,
                {lay: pad_poly(p, board.GetLayerID(lay)) for lay in ls})

    for t in board.GetTracks():
        if t.m_Uuid.AsString() in exclude or t.GetNetCode() <= 0:
            continue
        if isinstance(t, k.PCB_VIA):
            ls = [board.GetLayerName(l) for l in t.GetLayerSet().Seq()]
            ls = [l for l in ls if l in CU_LAYERS] or list(CU_LAYERS)
            add('via', dict(uuid=t.m_Uuid.AsString(), drill_mm=round(mm(t.GetDrillValue()), 4)),
                t.GetNetname(), t.GetNetCode(), ls,
                {lay: via_poly(t, board.GetLayerID(lay)) for lay in ls})
        else:
            add('track', dict(uuid=t.m_Uuid.AsString(), width_mm=round(mm(t.GetWidth()), 4),
                              layer=board.GetLayerName(t.GetLayer())),
                t.GetNetname(), t.GetNetCode(),
                [board.GetLayerName(t.GetLayer())], track_poly(t))

    # copper-layer graphic shapes: real copper, must be in the graph
    graphics = list(board.GetDrawings()) + [d for f in board.GetFootprints()
                                           for d in f.GraphicalItems()]
    for di, d in enumerate(graphics):
        ls = [board.GetLayerName(l) for l in d.GetLayerSet().Seq()]
        ls = [l for l in ls if l in CU_LAYERS]
        if not ls or d.GetNetCode() <= 0:
            continue
        if not isinstance(d, k.PCB_SHAPE):
            raise ValueError('Unsupported conductive graphic type')
        add('shape', dict(uuid=d.m_Uuid.AsString(), drawing=di, shape=int(d.GetShape())),
            d.GetNetname(), d.GetNetCode(), ls, drawing_poly(d))

    for zi, z in enumerate(board.Zones()):
        if z.GetIsRuleArea():
            continue
        lay_id = z.GetLayer()
        if not z.HasFilledPolysForLayer(lay_id):
            continue
        lay = board.GetLayerName(lay_id)
        for ii, shp in enumerate(polyset_to_shapely(z.GetFilledPolysList(lay_id))):
            add('island', dict(uuid=z.m_Uuid.AsString(), zone=z.GetZoneName(), zone_index=zi, island=ii),
                z.GetNetname(), z.GetNetCode(), [lay], shp)

    parent = list(range(len(nodes)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # layer barrels bridge only for a genuine plated connection
    for iid, ns in by_item.items():
        it = items[iid]
        plated = it['kind'] == 'via' or (it['kind'] == 'pad' and
                  it['meta']['attr'] == int(k.PAD_ATTRIB_PTH))
        if len(ns) > 1 and not plated:
            raise ValueError('Non-plated multilayer item requires separate layer identities')
        for x in ns[1:]:
            union(ns[0], x)

    by_layer = defaultdict(list)
    for n, (iid, lay, g) in enumerate(nodes):
        by_layer[lay].append(n)

    for lay, idxs in by_layer.items():
        geoms = [nodes[i][2] for i in idxs]
        tree = STRtree(geoms)
        for a_pos, a in enumerate(idxs):
            ga = geoms[a_pos]
            na = items[nodes[a][0]]['netcode']
            for b_pos in tree.query(ga.buffer(contact_tolerance), predicate='intersects'):
                bnode = idxs[b_pos]
                if bnode <= a:
                    continue
                if items[nodes[bnode][0]]['netcode'] != na:
                    continue
                if find(a) == find(bnode):
                    continue
                if geoms[b_pos].distance(ga) <= contact_tolerance:
                    union(a, bnode)

    # stable component id per item: smallest item id in the component
    raw = {iid: find(by_item[iid][0]) for iid in range(len(items)) if by_item[iid]}
    canon = {}
    for iid, r in raw.items():
        canon.setdefault(r, []).append(iid)
    root_canon = {r: min(members) for r, members in canon.items()}

    comp_of_item = {iid: root_canon[r] for iid, r in raw.items()}
    comps = defaultdict(list)
    for iid, c in comp_of_item.items():
        comps[c].append(iid)

    root_of = {n: comp_of_item[nodes[n][0]] for n in range(len(nodes))}

    return items, nodes, by_item, comps, root_of, comp_of_item, netless_pads


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(pathlib.Path(__file__).resolve().parents[3]))
    ap.add_argument('--out', default='islands.json')
    ap.add_argument('--work', default=None)
    args = ap.parse_args()

    repo = pathlib.Path(args.repo)
    src_dir = repo / 'tracker' / 'hardware'
    work = pathlib.Path(args.work) if args.work else repo / '.island_work'
    if not (src_dir / (STEM + '.kicad_pcb')).exists():
        sys.exit(f'board not found under {src_dir}')

    out = {'board': STEM, 'method': 'zone-polygon-enumeration + independent copper graph',
           'rules_mm': dict(clearance=R_CLEAR, via_diameter=R_VIA_DIA,
                            via_radius=R_VIA_R, track=R_TRACK, edge=R_EDGE,
                            drill=R_DRILL)}

    # -- phase 1
    refill = refill_copy(src_dir, work)
    out['refill'] = refill
    if not refill['source_unchanged']:
        sys.exit('SOURCE BOARD CHANGED -- aborting')
    board = k.LoadBoard(refill['work_dir'] + '/' + STEM + '.kicad_pcb')
    board.BuildConnectivity()
    out['base_unconnected_pcbnew'] = board.GetConnectivity().GetUnconnectedCount(False)

    # -- phase 2
    islands = enumerate_islands(board)
    out['island_total'] = len(islands)

    # -- phase 3
    items, nodes, by_item, comps, root_of, comp_of_item, netless_pads = build_copper_graph(board)

    # per-net component counts
    per_net = defaultdict(set)
    for iid, it in enumerate(items):
        if iid in comp_of_item and it['netcode'] > 0:
            per_net[it['net']].add(comp_of_item[iid])
    per_net_counts = {net: len(rs) for net, rs in per_net.items() if len(rs) > 0}
    sigma = sum(c - 1 for c in per_net_counts.values())
    out['graph_sigma_components_minus_1'] = sigma
    out['graph_per_net_components'] = dict(sorted(per_net_counts.items()))
    affected = sum(c > 1 for c in per_net_counts.values())
    out['affected_nets'] = affected
    if (sigma, affected, out['base_unconnected_pcbnew']) != (86, 22, 86):
        raise RuntimeError('Connectivity crosscheck failed; refusing classifications')
    if not refill['refill_byte_noop']:
        raise RuntimeError('Refill changed bytes; pinned inventory invalid')
    # A count match alone cannot exclude compensating false joins/splits.
    zero = build_copper_graph(board, contact_tolerance=0)
    partition = lambda cs: {frozenset(ms) for ms in cs.values()}
    out['zero_contact_full_partition_equal'] = partition(comps) == partition(zero[3])
    if not out['zero_contact_full_partition_equal']:
        raise RuntimeError('Zero-contact full partition differs; refusing classifications')
    out['status'] = 'INCOMPLETE_DRAFT_NATIVE_VALIDATION_REQUIRED'

    # main body per net = component with the most pads
    def pads_in(root):
        return [i for i in comps[root] if items[i]['kind'] == 'pad']

    net_main = {}
    for net, roots in per_net.items():
        best = max(sorted(roots), key=lambda r: (len(pads_in(r)),
                                         sum(items[i]['meta'].get('area_mm2', 0)
                                             for i in comps[r] if items[i]['kind'] == 'island')))
        net_main[net] = best

    # island -> item id lookup by (zone_index, island, layer)
    isl_item = {}
    for iid, it in enumerate(items):
        if it['kind'] != 'island':
            continue
        isl_item[(it['meta']['zone_index'], it['meta']['island'],
                  it['layers'][0])] = iid

    # -- foreign copper index, per layer (anything not on the island's own net)
    foreign_by_layer = defaultdict(list)
    for n, (iid, lay, g) in enumerate(nodes):
        foreign_by_layer[lay].append((iid, g))

    def foreign_tree(lay, exclude_netcode):
        keep = [(iid, g) for iid, g in foreign_by_layer[lay]
                if items[iid]['netcode'] != exclude_netcode]
        return keep

    # -- phases 4/5/6
    for isl in islands:
        iid = isl_item.get((isl['zone_index'], isl['island_index'], isl['layer']))
        isl['item_id'] = iid
        root = comp_of_item.get(iid) if iid is not None else None
        isl['component'] = root
        isl['main_component'] = net_main.get(isl['net'])
        members = comps.get(root, []) if root is not None else []
        kinds = defaultdict(int)
        for m in members:
            kinds[items[m]['kind']] += 1
        isl['component_members'] = dict(sorted(kinds.items()))
        isl['component_pads'] = sorted(
            f"{items[m]['meta']['ref']}.{items[m]['meta']['num']}"
            for m in members if items[m]['kind'] == 'pad')
        isl['is_main_body'] = (root == net_main.get(isl['net']))
        isl['status'] = 'CONNECTED' if isl['is_main_body'] else 'ISOLATED'

        if isl['status'] == 'CONNECTED':
            isl['nearest_same_net_mm'] = None
            isl['nearest_same_net_feature'] = None
            isl['stitch'] = None
            continue

        # -- phase 5: nearest same-net copper NOT in this component
        g_i = isl['geom']
        best = None
        for iid2, it2 in enumerate(items):
            if iid2 == iid or it2['netcode'] != isl['netcode']:
                continue
            if root_of.get(by_item[iid2][0]) == root:
                continue
            for node2 in by_item[iid2]:
                _, lay2, g2 = nodes[node2]
                if lay2 != isl['layer']:
                    # cross-layer distance is not a copper gap; record separately
                    continue
                d = g_i.distance(g2)
                if best is None or d < best[0]:
                    desc = it2['kind']
                    if it2['kind'] == 'pad':
                        desc = f"pad {it2['meta']['ref']}.{it2['meta']['num']}"
                    elif it2['kind'] == 'island':
                        desc = f"island {it2['meta']['zone']}#{it2['meta']['island']}"
                    elif it2['kind'] == 'via':
                        desc = 'via'
                    best = (d, desc, lay2, iid2, g2)
        if best:
            nb = best[4]
            p1, p2 = nearest_points(g_i, nb)
            isl['nearest_same_net_mm'] = round(best[0], 6)
            isl['nearest_same_net_feature'] = dict(
                kind=best[1], layer=best[2], item_id=best[3],
                point_island_mm=[round(p1.x, 4), round(p1.y, 4)],
                point_feature_mm=[round(p2.x, 4), round(p2.y, 4)])
        else:
            isl['nearest_same_net_mm'] = None
            isl['nearest_same_net_feature'] = None

        # -- phase 6: stitchability
        isl['stitch'] = stitch_candidate(board, isl, items, nodes, by_item,
                                         foreign_tree, isl['netcode'], netless_pads,
                                         comp_of_item)

    out['islands'] = [{k2: v for k2, v in i.items() if k2 != 'geom'} for i in islands]
    for i in out['islands']:
        i.pop('geom', None)

    # roll-ups
    by_zone_layer = defaultdict(lambda: dict(islands=0, isolated=0, area=0.0))
    for i in out['islands']:
        key = f"{i['zone_name']}@{i['layer']}"
        by_zone_layer[key]['islands'] += 1
        by_zone_layer[key]['area'] = round(by_zone_layer[key]['area'] + i['area_mm2'], 4)
        if i['status'] == 'ISOLATED':
            by_zone_layer[key]['isolated'] += 1
    out['rollup_by_zone_layer'] = dict(sorted(by_zone_layer.items()))
    out['isolated_total'] = sum(1 for i in out['islands'] if i['status'] == 'ISOLATED')
    out['geometric_candidates_pending_native_validation'] = sum(
        1 for i in out['islands']
        if i['status'] == 'ISOLATED' and i['stitch'] and i['stitch']['legal'])

    pathlib.Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"islands={out['island_total']} isolated={out['isolated_total']} "
          f"candidate_predictions={out['geometric_candidates_pending_native_validation']} sigma={sigma} "
          f"drc={out['base_unconnected_pcbnew']}")
    print('wrote', args.out)


def nearest_points(a, b):
    from shapely.ops import nearest_points as np_
    return np_(a, b)


def nearest_clearance(p, trees, cap):
    """Exact edge-of-via-annulus to foreign-copper distance from point p.

    Returns min over all layers of (distance(p, foreign_copper) - R_VIA_R), capped at
    `cap` (a measured upper bound when nothing is close).
    """
    worst = cap
    for lay, (keep, tree) in trees.items():
        ring = p.buffer(cap + R_VIA_R, quad_segs=12)
        for j in tree.query(ring, predicate='intersects'):
            d = keep[j][1].distance(p) - R_VIA_R
            if d < worst:
                worst = d
    return worst


def stitch_candidate(board, isl, items, nodes, by_item, foreign_tree, netcode,
                     netless_pads, comp_of_item):
    """Can ONE via in this island legally resolve its isolation at the 0.20mm rule?

    Two DIFFERENT questions, both measured, never assumed:

    (1) HARD clearance -- distance to foreign copper that CANNOT retreat: tracks, pads,
        vias and copper graphics. This is the true legal blocker. A via is illegal if
        it comes closer than R_CLEAR to any of these on any layer it passes through.

    (2) FROZEN-FILL clearance -- distance to foreign copper INCLUDING zone pours as
        currently filled. A pour does retreat around a new via annulus on refill, so a
        negative value here does not mean illegal; it means the fix needs a refill,
        which invalidates any claim of byte-identical copper. Reported separately
        precisely so the two are not conflated.

    (3) LANDS ELSEWHERE -- a via is VERTICAL. It cannot merge two disjoint outlines on
        the SAME layer. It resolves connectivity only by landing on same-net copper on
        a DIFFERENT layer, giving the island a path into the net's main body. Measured.

    Verdict legal == hard clearance OK AND lands on another layer.
    """
    g = isl['geom']
    minx, miny, maxx, maxy = g.bounds
    step = 0.10
    inner = g.buffer(-R_VIA_R / 2.0)
    if inner.is_empty:
        inner = g

    cands = []
    x = minx
    while x <= maxx + 1e-9:
        y = miny
        while y <= maxy + 1e-9:
            p = Point(round(x, 4), round(y, 4))
            if inner.contains(p):
                cands.append(p)
            y += step
        x += step
    if not cands:
        cands = [inner.representative_point() if not inner.is_empty else g.representative_point()]

    # build per-layer indexes: all-foreign and hard-foreign (non-zone)
    all_idx, hard_idx = {}, {}
    for lay in CU_LAYERS:
        keep = foreign_tree(lay, netcode)
        if not keep:
            continue
        all_idx[lay] = (keep, STRtree([gg for _, gg in keep]))
        hk = [(iid, gg) for iid, gg in keep if items[iid]['kind'] != 'island']
        if hk:
            hard_idx[lay] = (hk, STRtree([gg for _, gg in hk]))

    hard_geoms = [gg for keep, _ in hard_idx.values() for _, gg in keep]
    all_geoms = [gg for keep, _ in all_idx.values() for _, gg in keep]
    extra = [gg for _, gg, _, _ in netless_pads]
    for t in board.GetTracks():
        if t.GetNetCode() <= 0:
            extra.append(via_poly(t) if isinstance(t, k.PCB_VIA) else track_poly(t))
    for d in board.GetDrawings():
        if d.GetNetCode() <= 0 and board.GetLayerName(d.GetLayer()) in CU_LAYERS:
            extra.append(drawing_poly(d))
    for f in board.GetFootprints():
        for d in f.GraphicalItems():
            if board.GetLayerName(d.GetLayer()) in CU_LAYERS:
                extra.append(drawing_poly(d))
    hard_union = unary_union(hard_geoms + extra)
    all_union = unary_union(all_geoms + extra)
    edges = unary_union(edge_segments(board))
    holes = []
    for f in board.GetFootprints():
        for pad in f.Pads():
            drill = pad.GetDrillSize()
            if max(drill.x, drill.y) > 0:
                pos = pad.GetPosition()
                holes.append(hole_poly(pad))
    for t in board.GetTracks():
        if isinstance(t, k.PCB_VIA):
            pos = t.GetPosition()
            holes.append(hole_poly(t))
    hole_union = unary_union(holes)
    landing_by_layer = {}
    for lay in CU_LAYERS:
        gs = [geom for iid2, layer, geom in nodes
              if layer == lay and lay != isl['layer']
              and items[iid2]['netcode'] == netcode
              and comp_of_item.get(iid2) == isl['main_component']]
        if gs:
            landing_by_layer[lay] = unary_union(gs)
    scored = []
    for p in cands:
        hard = hard_union.distance(p) - R_VIA_R
        frozen = all_union.distance(p) - R_VIA_R
        edge = edges.distance(p) - R_VIA_R if not edges.is_empty else -1
        hole = hole_union.distance(p) - VIA_DRILL_HALF if holes else 100
        landing = [lay for lay, geom in landing_by_layer.items()
                   if geom.distance(p) < R_VIA_R - 1e-6]
        margin = min(hard-R_CLEAR, edge-R_EDGE, hole-R_HOLE_CLEAR)
        scored.append((bool(landing) and margin >= 0, bool(landing), margin,
                       hard, frozen, edge, hole, p, landing))
    scored.sort(key=lambda t: t[:3], reverse=True)
    predicted, lands, margin, hard, frozen, edge, hole, p, landing = scored[0]
    return dict(candidate_site_mm=[round(p.x,4), round(p.y,4)],
                hard_clearance_mm=round(hard,4), frozen_fill_clearance_mm=round(frozen,4),
                edge_clearance_mm=round(edge,4), required_edge_clearance_mm=R_EDGE,
                edge_clearance_ok=edge >= R_EDGE, hole_clearance_mm=round(hole,4),
                minimum_modeled_margin_mm=round(margin,4),
                lands_on_same_net_layers=landing, lands_on_main_component=lands,
                resolves_connectivity=lands, legal=predicted,
                proof_status='UNVERIFIED_GEOMETRIC_PREDICTION',
                negative_scope='No legal candidate found in sampled sites; not proof of impossibility',
                grid_step_mm=step, candidates_tested=len(cands))


if __name__ == '__main__':
    main()
