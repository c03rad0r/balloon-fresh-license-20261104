#!/usr/bin/env python3
"""Stage A: classify islands on the REPAIRED candidate and score candidate sites.

Everything here is measurement on the repaired board; no prior approval is reused.
A site is only a candidate if the via ANNULUS (0.50 mm diameter) actually
OVERLAPS copper of both the target island's component and the pinned main
component — a centre-distance test says nothing about overlap and was the
weakness of the previous landing prediction.
"""
from __future__ import annotations

import json
import pathlib
import sys
import types

import pcbnew as k
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as H  # noqa: E402
import inventory as inv  # noqa: E402

VIA_ANNULUS = Point(0, 0).buffer(H.R_VIA_R, quad_segs=32)


def annulus_at(x, y):
    from shapely import affinity
    return affinity.translate(VIA_ANNULUS, xoff=x, yoff=y)


def target_key(isl):
    return f"{isl['zone_uuid']}:{isl['layer']}:{isl['island_index']}"


def main():
    ap = __import__('argparse').ArgumentParser()
    ap.add_argument('--board', required=True, type=pathlib.Path)
    ap.add_argument('--work', required=True, type=pathlib.Path)
    ap.add_argument('--out', required=True, type=pathlib.Path)
    ap.add_argument('--grid', type=float, default=0.05)
    args = ap.parse_args()

    # Refill a COPY (refill-before-DRC always); the input board is never written.
    work = args.work
    pcb = H.fresh_copy(args.board, work)
    b = H.refill_save(pcb)
    filled_sha = H.sha256(pcb)
    b = k.LoadBoard(str(pcb))
    b.BuildConnectivity()
    native_unconn = b.GetConnectivity().GetUnconnectedCount(False)

    islands = inv.enumerate_islands(b)
    records = H.snapshot(b)
    pinned = H.pin_mains(records)
    counts = H.net_counts(records)
    sig = H.sigma(records)
    out = dict(board=args.board.name, source_sha256=H.sha256(args.board),
               refilled_sha256=filled_sha, refill_byte_noop=(filled_sha == H.sha256(args.board)),
               native_unconnected=native_unconn, graph_sigma=sig,
               graph_per_net_components={n: c for n, c in counts.items() if c > 1},
               affected_nets=sum(1 for c in counts.values() if c > 1),
               island_total=len(islands),
               pinned_main={n: dict(n_members=p['n_members'], n_pads=p['n_pads'])
                            for n, p in pinned.items() if counts.get(n, 0) > 1},
               islands=[], rejected=[])

    foreign_by_layer = {}
    for lay in H.CU_LAYERS:
        foreign_by_layer[lay] = [(key, r) for key, r in records.items()
                                 if r['item']['layers'] == [lay]]

    isolated = []
    for isl in islands:
        tk = target_key(isl)
        if tk not in records:
            raise RuntimeError('Island in enumeration missing from graph: ' + tk)
        comp = H.component_of(records, tk)
        pm = pinned[isl['net']]['members']
        is_main = comp == pm
        rec = dict(island_id=isl['island_id'], target_key=tk, net=isl['net'],
                   layer=isl['layer'], area_mm2=isl['area_mm2'],
                   bbox_mm=isl['bbox_mm'], centroid_mm=isl['centroid_mm'],
                   component_size=len(comp), is_main_body=is_main)
        if is_main:
            out['islands'].append(rec)
            continue
        # members of this component that are NOT the target island itself
        others = sorted(comp - {tk})
        rec['component_others'] = others[:8]
        rec['component_other_count'] = len(others)
        rec['pads_in_component'] = sorted(
            f"{records[m]['item']['meta']['ref']}.{records[m]['item']['meta']['num']}"
            for m in comp if records[m]['item']['kind'] == 'pad')
        out['islands'].append(rec)
        isolated.append((isl, rec, comp))

    # ---- exact annulus-overlap site region per isolated island
    # p is a legal annulus-overlap site for geometry G iff disk(p, R) ∩ G ≠ ∅,
    # which is exactly p ∈ G.buffer(R). So the candidate REGION is an
    # intersection of three buffers — no grid scan, no distance prediction.
    main_geom = {}
    for net, info in pinned.items():
        main_geom[net] = unary_union([records[m]['geom'] for m in info['members']])
    comp_geom = {}
    for isl, rec, comp in isolated:
        comp_geom[rec['target_key']] = unary_union([records[m]['geom'] for m in comp])

    for isl, rec, comp in isolated:
        tk = rec['target_key']
        g = records[tk]['geom']
        cg = comp_geom[tk]
        # same-net copper on ANOTHER layer that belongs to pinned main
        other_layer_main = []
        for lay in H.CU_LAYERS:
            if lay == isl['layer']:
                continue
            parts = [records[m]['geom'] for m in pinned[isl['net']]['members']
                     if records[m]['item']['layers'] == [lay]]
            if parts:
                other_layer_main.append((lay, unary_union(parts)))
        rec['other_layer_main_layers'] = [lay for lay, _ in other_layer_main]

        # legal centre must lie inside the target island (its own copper)
        region_target = g
        if other_layer_main:
            land_union = unary_union([geom.buffer(H.R_VIA_R) for _, geom in other_layer_main])
            # barrel must ALSO touch the island's own component copper
            region = region_target.intersection(land_union)
            region = region.intersection(cg.buffer(H.R_VIA_R))
        else:
            region = region_target.intersection(Polygon())

        sites = []
        if not region.is_empty:
            polys = [region] if region.geom_type == 'Polygon' else list(region.geoms)
            for poly in polys:
                if poly.area <= 0:
                    continue
                for frac in ((.5, .5), (.25, .25), (.75, .25), (.25, .75), (.75, .75)):
                    x0, y0, x1, y1 = poly.bounds
                    p = Point(x0 + (x1 - x0) * frac[0], y0 + (y1 - y0) * frac[1])
                    if not poly.contains(p):
                        p = poly.representative_point()
                    p = Point(round(p.x, 6), round(p.y, 6))
                    if not poly.covers(p):
                        continue
                    a = annulus_at(p.x, p.y)
                    on_c = a.intersection(cg).area
                    lands = [(lay, round(a.intersection(geom).area, 6))
                             for lay, geom in other_layer_main
                             if a.intersection(geom).area > 1e-9]
                    if on_c <= 1e-9 or not lands:
                        continue
                    sites.append(dict(x=p.x, y=p.y,
                                      annulus_overlap_component_mm2=round(on_c, 6),
                                      lands_on=lands,
                                      annulus_overlap_main_mm2=round(sum(v for _, v in lands), 6)))
        sites.sort(key=lambda s: (-s['annulus_overlap_main_mm2'],
                                  -s['annulus_overlap_component_mm2'], s['x'], s['y']))
        dedup, seen = [], set()
        for s in sites:
            key = (s['x'], s['y'])
            if key in seen:
                continue
            seen.add(key)
            dedup.append(s)
        rec['candidate_sites'] = dedup[:24]
        rec['candidate_site_count'] = len(dedup)
        if not dedup:
            rec['status'] = 'NO_ANNULUS_OVERLAP_SITE'
        else:
            rec['status'] = 'CANDIDATE_SITES_FOUND'

    out['isolated_total'] = len(isolated)
    out['isolated_with_sites'] = sum(1 for _, r, _ in isolated
                                     if r['status'] == 'CANDIDATE_SITES_FOUND')
    out['source_unchanged'] = H.sha256(args.board) == out['source_sha256']
    if not out['source_unchanged']:
        raise RuntimeError('Source changed during analysis')
    args.out.write_text(json.dumps(out, indent=1) + '\n')
    print(f"islands={len(islands)} isolated={len(isolated)} with_sites={out['isolated_with_sites']} "
          f"sigma={sig} native={native_unconn} refill_noop={out['refill_byte_noop']}")


if __name__ == '__main__':
    main()
