"""Pinned full-component geometric proof; native counts are only a crosscheck.

No native polygon-component API is assumed. UUIDs identify hard copper; unique
positive-area overlap within zone UUID/net/layer identifies filled polygons.
Split/merge/disappearing outlines fail closed, never silently use outline index.
"""
from collections import defaultdict
import argparse
import json
from pathlib import Path
import pcbnew as k
import run_island_inventory as inv


def snapshot(board, exclude_uuid=None, tolerance=inv.TOL):
    items, nodes, by_item, comps, _, roots, _ = inv.build_copper_graph(
        board, exclude_uuid=exclude_uuid, contact_tolerance=tolerance)
    records = {}
    for item in items:
        iid = item['id']
        if iid not in roots:
            raise ValueError('Copper item without geometry')
        key = item['meta']['uuid']
        if item['kind'] == 'island':
            key += ':' + item['layers'][0] + ':' + str(item['meta']['island'])
        if key in records:
            raise ValueError('Duplicate identity')
        records[key] = dict(item=item, root=roots[iid],
                            geom=nodes[by_item[iid][0]][2])
    return records


def counts(records):
    nets = defaultdict(set)
    for r in records.values():
        nets[r['item']['net']].add(r['root'])
    return {net: len(cs) for net, cs in sorted(nets.items())}


def partition(records, mapping=None):
    groups = defaultdict(set)
    for key, r in records.items():
        if mapping is None or key in mapping:
            groups[r['root']].add(key if mapping is None else mapping[key])
    return {frozenset(v) for v in groups.values()}


def correspondence(before, after, via_uuid):
    """Bijective geometric identity; outline ordering and root numbers irrelevant."""
    mapping, changes = {}, []
    for key, r in before.items():
        item = r['item']
        if item['kind'] != 'island':
            candidates = [key] if key in after else []
        else:
            candidates = [ak for ak, ar in after.items()
                          if ar['item']['kind'] == 'island'
                          and ar['item']['meta']['uuid'] == item['meta']['uuid']
                          and ar['item']['net'] == item['net']
                          and ar['item']['layers'] == item['layers']
                          and r['geom'].intersection(ar['geom']).area > 0]
        if len(candidates) != 1 or candidates[0] in mapping:
            raise ValueError('Non-bijective polygon/object mapping: ' + key)
        ak = candidates[0]
        ar = after[ak]
        if item['kind'] != 'island':
            if (item['net'], item['layers']) != (ar['item']['net'], ar['item']['layers']) or not r['geom'].equals(ar['geom']):
                raise ValueError('Hard copper changed: ' + key)
        else:
            retained = r['geom'].intersection(ar['geom']).area / r['geom'].area
            if retained < .99 or not ar['geom'].covers(r['geom'].representative_point()):
                raise ValueError('Island witness/99% retention failed: ' + key)
            changes.append(dict(before=key, after=ak, retained_fraction=retained,
                                symmetric_difference_mm2=r['geom'].symmetric_difference(ar['geom']).area))
        mapping[ak] = key
    if set(after) - set(mapping) != {via_uuid}:
        raise ValueError('Unexpected added/deleted copper: ' + ', '.join(sorted((set(after) - set(mapping)) - {via_uuid})))
    return mapping, changes


def prove(before, after, without_via, target, main, via_uuid, native_count):
    mapping, changes = correspondence(before, after, via_uuid)
    base_partition = partition(before)
    unchanged = partition(without_via, mapping) == base_partition
    target_members = next(g for g in base_partition if target in g)
    main_members = next(g for g in base_partition if main in g)
    reverse = {v: key for key, v in mapping.items()}
    target_after = reverse[target]
    joined_root = after[target_after]['root']
    main_reached = all(after[reverse[key]]['root'] == joined_root for key in main_members)
    via_reached = after[via_uuid]['root'] == joined_root
    # Exactly two pinned components may join: no splitting, foreign merges or relabeling.
    expected = (base_partition - {target_members, main_members}) | {target_members | main_members}
    exact_join = partition(after, mapping) == expected and target_members != main_members
    per_net = counts(after)
    sigma = sum(n-1 for n in per_net.values())
    return dict(geometric_endpoint_to_pinned_main=main_reached and via_reached,
                no_refill_partition_reassignment=unchanged, exact_two_component_join=exact_join,
                graph_per_net_components_after=per_net, graph_sigma_after=sigma,
                native_unconnected_crosscheck=native_count == sigma,
                geometric_proven=all((main_reached, via_reached, unchanged, exact_join, native_count == sigma)),
                target_before=target, target_after=target_after, pinned_main_anchor=main,
                pinned_main_member_count=len(main_members), target_component_member_count=len(target_members),
                polygon_mapping=changes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    here = Path(__file__).parent
    inventory = json.loads((here/'islands.json').read_text())
    native = json.loads((here/'native_validation.json').read_text())
    source = here.parents[2]/'tracker/hardware'/ (inv.STEM+'.kicad_pcb')
    if inv.sha256(source) != inventory['refill']['source_sha256']:
        raise RuntimeError('Pinned source mismatch')
    pcb = args.evidence/'baseline'/(inv.STEM+'.kicad_pcb')
    if inv.sha256(pcb) != inventory['refill']['copy_sha256_after_fill']:
        raise RuntimeError('Pinned baseline hash mismatch')
    board = k.LoadBoard(str(pcb))
    board.BuildConnectivity()
    before = snapshot(board)
    cs = counts(before)
    if (sum(n-1 for n in cs.values()), sum(n>1 for n in cs.values()), board.GetConnectivity().GetUnconnectedCount(False)) != (86,22,86):
        raise RuntimeError('86/22 baseline gate failed')
    if cs != inventory['graph_per_net_components']:
        raise RuntimeError('Per-net baseline mismatch')
    result = dict(source_sha256=inv.sha256(source), baseline_per_net_components=cs,
                  native_per_island_proven=False,
                  native_limitation='Installed pcbnew SWIG bindings do not expose usable per-filled-polygon component membership; native crosscheck is aggregate only, not endpoint proof.', arms=[])
    isolated = [i for i in inventory['islands'] if i['status']=='ISOLATED']
    for n, island in enumerate(isolated):
        arm_native = native['arms'][n]
        if arm_native['island_id'] != island['island_id']:
            raise RuntimeError('Arm ordering mismatch')
        pcb = args.evidence/f'arm{n:02d}'/(inv.STEM+'.kicad_pcb')
        if inv.sha256(pcb) != arm_native['candidate_board_sha256']:
            raise RuntimeError('Candidate evidence hash mismatch')
        b = k.LoadBoard(str(pcb))
        b.BuildConnectivity()
        if b.GetConnectivity().GetUnconnectedCount(False) != arm_native['unconnected_after']:
            raise RuntimeError('Saved native DRC and connectivity disagree')
        after = snapshot(b)
        new = [key for key, r in after.items() if r['item']['kind']=='via' and key not in before]
        if len(new) != 1:
            raise RuntimeError('Not a single-via experiment')
        via_uuid = new[0]
        target = island['zone_uuid']+':'+island['layer']+':'+str(island['island_index'])
        anchors = [key for key,r in before.items() if r['root']==island['main_component']]
        if before[target]['root'] != island['component'] or not anchors:
            raise RuntimeError('Inventory component mismatch')
        main_anchor = sorted(anchors)[0]
        arm = dict(island_id=island['island_id'], candidate_board_sha256=inv.sha256(pcb), via_uuid=via_uuid)
        try:
            arm.update(prove(before, after, snapshot(b, via_uuid), target, main_anchor, via_uuid,
                             b.GetConnectivity().GetUnconnectedCount(False)))
            # Zero-distance sensitivity rejects proofs depending on 4um proximity alone.
            strict_before, strict_after = snapshot(board, tolerance=0), snapshot(b, tolerance=0)
            strict = prove(strict_before, strict_after, snapshot(b, via_uuid, tolerance=0),
                           target, main_anchor, via_uuid, arm_native['unconnected_after'])
            arm['zero_tolerance_geometric_proven'] = strict['geometric_proven']
            arm['geometric_proven'] &= strict['geometric_proven']
        except ValueError as exc:
            arm.update(geometric_proven=False, blocker=str(exc))
        arm['native_no_new_violations'] = arm_native['native_no_new_violations']
        arm['connectivity_proven'] = False  # reserved for native per-island proof
        arm['verdict'] = ('GEOMETRIC_MAIN_JOIN_NATIVE_LEGAL_SAMPLE' if arm['geometric_proven'] and arm['native_no_new_violations'] else 'SAMPLED_CANDIDATE_NOT_PROVEN')
        result['arms'].append(arm)
        result['source_unchanged'] = inv.sha256(source)==result['source_sha256']
        if not result['source_unchanged']:
            raise RuntimeError('Source changed')
        args.out.write_text(json.dumps(result, indent=1)+'\n')
        print(n, island['island_id'], arm['verdict'], arm.get('blocker',''), flush=True)


if __name__ == '__main__':
    main()
