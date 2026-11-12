#!/usr/bin/env python3
"""Copper-graph harness for the hub stitch campaign.

The graph builder is reused unchanged from the proven island-inventory work
(35 islands / sigma 86 / 22 nets / native 86 crosscheck). What is NEW here:

  * a board path is a parameter (the repaired candidate), not a repo constant;
  * candidate sites are scored by EXACT ANNULUS OVERLAP against the target
    island's component and the pinned main component, instead of a
    centre-to-copper distance prediction;
  * the partition proof is generalised to a CLUSTER of simultaneous joins and
    pins the main component by its ORIGINAL member set.

Nothing here infers native polygon membership; native DRC is used only for
legality (violation-identity multiset) and as an aggregate connectivity
crosscheck, never to identify an endpoint.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

import pcbnew as k
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import inventory as inv  # noqa: E402  (proven primitives + graph builder)

STEM = inv.STEM
CU_LAYERS = inv.CU_LAYERS
R_CLEAR = inv.R_CLEAR
R_VIA_DIA = inv.R_VIA_DIA
R_VIA_R = inv.R_VIA_R
R_EDGE = inv.R_EDGE
R_DRILL = inv.R_DRILL
R_HOLE_CLEAR = inv.R_HOLE_CLEAR
VIA_DRILL_HALF = inv.VIA_DRILL_HALF
TOL = inv.TOL


# ------------------------------------------------------------------ utilities
def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def fresh_copy(board_path, work, extra_files=()):
    """Copy board + sibling project/dru/lib-table into a NEW directory."""
    board_path = pathlib.Path(board_path)
    work = pathlib.Path(work)
    work.mkdir(parents=True, exist_ok=False)
    stem = board_path.stem
    for f in board_path.parent.glob(stem + '.kicad_*'):
        shutil.copy2(f, work / f.name)
    for f in board_path.parent.glob('*.kicad_dru'):
        shutil.copy2(f, work / f.name)
    for f in board_path.parent.glob('*lib-table'):
        shutil.copy2(f, work / f.name)
    for f in extra_files:
        shutil.copy2(f, work / pathlib.Path(f).name)
    return work / board_path.name


def refill_save(pcb):
    b = k.LoadBoard(str(pcb))
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)
    return b


def drc(pcb, out=None):
    pcb = pathlib.Path(pcb)
    out = pathlib.Path(out) if out else pcb.with_suffix('.drc.json')
    cmd = ['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
           '-o', str(out), str(pcb)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not out.exists():
        raise RuntimeError('DRC produced no report: ' + res.stdout + res.stderr)
    # exit 5 == violations found; that is a RESULT, not a failure
    if res.returncode not in (0, 5):
        raise RuntimeError(f'DRC exit {res.returncode}: ' + res.stdout + res.stderr)
    return json.loads(out.read_text()), dict(cmd=cmd, exit=res.returncode,
                                            stdout=res.stdout, stderr=res.stderr)


def identities(report):
    """Multiset of violation identities; never list indexes."""
    return Counter(json.dumps((v['type'], v['severity'], v['description'],
                               sorted((i.get('uuid', ''), i.get('description', ''))
                                      for i in v['items'])))
                   for v in report['violations'])


# -------------------------------------------------------------------- graph
def snapshot(board, exclude_uuids=(), tolerance=TOL):
    """Records keyed by stable identity: hard copper by UUID, island by
    zone-uuid:layer:index (index is only a KEY here; correspondence re-maps by
    positive-area overlap, so a renumbered outline cannot fake identity)."""
    excl = set(exclude_uuids)
    items, nodes, by_item, comps, _, roots, _ = inv.build_copper_graph(
        board, contact_tolerance=tolerance, exclude_uuids=excl)
    records = {}
    for item in items:
        iid = item['id']
        if iid not in roots:
            raise ValueError('Copper item without geometry')
        if item['meta']['uuid'] in excl:
            continue
        key = item['meta']['uuid']
        if item['kind'] == 'island':
            key += ':' + item['layers'][0] + ':' + str(item['meta']['island'])
        if key in records:
            raise ValueError('Duplicate identity: ' + key)
        records[key] = dict(item=item, root=roots[iid],
                            geom=nodes[by_item[iid][0]][2])
    # roots must be recomputed on the RETAINED set: excluding a via can split a
    # component, which is exactly what the no-via control needs to show.
    return records


def components(records):
    groups = defaultdict(set)
    for key, r in records.items():
        groups[r['root']].add(key)
    return groups


def partition(records, mapping=None):
    groups = defaultdict(set)
    for key, r in records.items():
        if mapping is None or key in mapping:
            groups[r['root']].add(key if mapping is None else mapping[key])
    return {frozenset(v) for v in groups.values()}


def net_counts(records):
    nets = defaultdict(set)
    for r in records.values():
        nets[r['item']['net']].add(r['root'])
    return {net: len(cs) for net, cs in sorted(nets.items())}


def sigma(records):
    return sum(n - 1 for n in net_counts(records).values())


def correspondence(before, after, added_uuids, area_keep=.99):
    """Bijective geometric identity between two snapshots.

    Hard copper: same UUID, and geometry/net/layers identical.
    Filled polygons: exactly one partner with the same zone UUID/net/layer and
    positive-area overlap, retaining >= area_keep of the original area and its
    original interior witness. Split/merge/disappear fail closed.
    """
    mapping, changes = {}, []
    for key, r in before.items():
        item = r['item']
        if item['kind'] != 'island':
            cands = [key] if key in after else []
        else:
            cands = [ak for ak, ar in after.items()
                     if ar['item']['kind'] == 'island'
                     and ar['item']['meta']['uuid'] == item['meta']['uuid']
                     and ar['item']['net'] == item['net']
                     and ar['item']['layers'] == item['layers']
                     and r['geom'].intersection(ar['geom']).area > 0]
        if len(cands) != 1:
            raise ValueError('Non-bijective mapping for ' + key
                             + f' ({len(cands)} partners)')
        ak = cands[0]
        if ak in mapping:
            raise ValueError('Two originals map to one partner: ' + ak)
        ar = after[ak]
        if item['kind'] != 'island':
            if (item['net'], item['layers']) != (ar['item']['net'], ar['item']['layers']):
                raise ValueError('Hard copper net/layer changed: ' + key)
            if not r['geom'].equals(ar['geom']):
                raise ValueError('Hard copper geometry changed: ' + key)
        else:
            kept = r['geom'].intersection(ar['geom']).area / r['geom'].area
            if kept < area_keep or not ar['geom'].covers(r['geom'].representative_point()):
                raise ValueError('Island witness/retention failed: ' + key)
            changes.append(dict(before=key, after=ak, retained_fraction=round(kept, 6),
                                symmetric_difference_mm2=round(
                                    r['geom'].symmetric_difference(ar['geom']).area, 6)))
        mapping[ak] = key
    extra = set(after) - set(mapping)
    if extra != set(added_uuids):
        raise ValueError('Unexpected added/deleted copper: '
                         + ', '.join(sorted(extra)) + ' expected ' + ', '.join(sorted(added_uuids)))
    return mapping, changes


# --------------------------------------------------------------- main pins
def pads_in(records_by_root, root):
    return [i for i in records_by_root.get(root, [])]


def pin_mains(records):
    """Pin each net's MAIN component by its ORIGINAL member set.

    Convention (unchanged from the inventory): the component carrying the most
    pads; ties broken by total island area, then by deterministic component id.
    The pin is a SET OF MEMBERS, never a root number, so it survives any
    renumbering caused by the edit under test.
    """
    by_root = defaultdict(list)
    for key, r in records.items():
        by_root[r['root']].append(key)
    per_net = defaultdict(set)
    for key, r in records.items():
        per_net[r['item']['net']].add(r['root'])
    pinned = {}
    for net, roots in per_net.items():
        def score(root):
            members = by_root[root]
            pads = [m for m in members if records[m]['item']['kind'] == 'pad']
            area = sum(records[m]['geom'].area for m in members
                       if records[m]['item']['kind'] == 'island')
            return (len(pads), area)
        best = max(sorted(roots), key=score)
        members = frozenset(by_root[best])
        pads = sorted(f"{records[m]['item']['meta']['ref']}.{records[m]['item']['meta']['num']}"
                      for m in members if records[m]['item']['kind'] == 'pad')
        pinned[net] = dict(members=members, pads=pads, n_members=len(members),
                           n_pads=len(pads))
    return pinned


def component_of(records, target_key):
    return frozenset(k for k, r in records.items() if r['root'] == records[target_key]['root'])
