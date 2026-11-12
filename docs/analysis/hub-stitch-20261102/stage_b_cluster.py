#!/usr/bin/env python3
"""Stage B driver: try ONE cluster of candidate via sites on a fresh copy.

For each cluster it:
  1. writes a fresh copy of the current repaired-candidate board,
  2. adds one 0.50/0.30 mm through via per site on the cluster's net,
  3. REFILLS, then runs native DRC (refill-before-DRC always),
  4. requires C1-C7 exact partition proof (see prove.py),
  5. also runs the zero-contact sensitivity and the no-via refill control.

A cluster that fails ANY check is reported with the precise reason and the
candidate set is narrowed by the caller. Nothing is ever accepted on a count
drop alone.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import pcbnew as k

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as H  # noqa: E402
import prove as P  # noqa: E402


def records_at(pcb, exclude=(), tolerance=H.TOL):
    b = k.LoadBoard(str(pcb))
    b.BuildConnectivity()
    rec = H.snapshot(b, exclude_uuids=exclude, tolerance=tolerance)
    return b, rec


def run_cluster(src_pcb, work, cluster, baseline_pcb, native_base_ids,
                native_base_unconn, pinned):
    """cluster: list of dicts with target_key, net, x, y."""
    work = pathlib.Path(work)
    pcb = H.fresh_copy(src_pcb, work)

    # ---- before snapshot from the PRISTINE baseline copy (already refilled)
    base_board, base_rec = records_at(baseline_pcb)
    base_sigma = H.sigma(base_rec)
    if base_sigma != native_base_unconn:
        raise RuntimeError(f'baseline graph/native mismatch {base_sigma} != {native_base_unconn}')

    # ---- add vias (grouped by net; a cluster may only join one net at a time)
    nets = {c['net'] for c in cluster}
    if len(nets) != 1:
        raise ValueError('A cluster must be single-net; got ' + repr(nets))
    netname = nets.pop()
    b, uuids = P.add_vias(pcb, cluster, netname)
    if len(uuids) != len(cluster):
        raise RuntimeError('via count mismatch')
    for c, u in zip(cluster, uuids):
        c['via_uuid'] = u
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)

    report, meta = H.drc(pcb, work / 'after.drc.json')
    ids_after = H.identities(report)
    added_ids = ids_after - native_base_ids
    removed_ids = native_base_ids - ids_after
    native_unconn = len(report['unconnected_items'])

    result = dict(cluster=[{kk: vv for kk, vv in c.items() if kk != 'via_uuid'} for c in cluster],
                  added_via_uuids=uuids, after_board_sha256=H.sha256(pcb),
                  drc=meta, native_violations=len(report['violations']),
                  native_unconnected=native_unconn,
                  new_violation_identities=dict(added_ids),
                  removed_violation_identities=dict(removed_ids),
                  native_no_new_violations=not added_ids,
                  tolerance=H.TOL, checks={}, blockers=[], verdict='REJECTED')

    # ---- C1-C6 at nominal tolerance
    b2, after_rec = records_at(pcb)
    via_uuids = set(uuids)
    b3, novia_rec = records_at(pcb, exclude=via_uuids)
    try:
        chk = P.prove(base_rec, after_rec, novia_rec, cluster, pinned, native_unconn,
                      f'{H.TOL} mm contact tolerance')
        result['checks']['nominal'] = chk
    except ValueError as exc:
        result['blockers'].append('nominal: ' + str(exc))
        return result

    # ---- C6 zero-contact sensitivity
    try:
        zb, zbase = records_at(baseline_pcb, tolerance=0)
        zafter = H.snapshot(b2, tolerance=0)
        znovia = H.snapshot(b3, exclude_uuids=via_uuids, tolerance=0)
        zchk = P.prove(zbase, zafter, znovia, cluster, pinned, native_unconn,
                       '0.000 mm contact tolerance')
        result['checks']['zero_tolerance'] = zchk
    except ValueError as exc:
        result['blockers'].append('zero_tolerance: ' + str(exc))
        return result

    # ---- C7 native legality
    ok = (result['native_no_new_violations']
          and chk['c3_pinned_main_joined'] and zchk['c3_pinned_main_joined']
          and chk['c4_exact_join'] and zchk['c4_exact_join']
          and chk['c5_no_via_refill_control'] and zchk['c5_no_via_refill_control']
          and chk['native_matches_graph'] and zchk['native_matches_graph'])
    if not result['native_no_new_violations']:
        result['blockers'].append('native_drc: new violation identities')
    if not (chk['c4_exact_join'] and zchk['c4_exact_join']):
        result['blockers'].append('exact_join: partition differs from the declared merge')
    if not (chk['c5_no_via_refill_control'] and zchk['c5_no_via_refill_control']):
        result['blockers'].append('no_via_control: refill alone changed the partition')
    if not (chk['native_matches_graph'] and zchk['native_matches_graph']):
        result['blockers'].append('native/graph sigma disagree')
    result['verdict'] = 'PROVEN_LEGAL_JOIN' if ok else 'REJECTED'
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, type=pathlib.Path)
    ap.add_argument('--baseline', required=True, type=pathlib.Path)
    ap.add_argument('--cluster', required=True, type=pathlib.Path)
    ap.add_argument('--work', required=True, type=pathlib.Path)
    ap.add_argument('--out', required=True, type=pathlib.Path)
    args = ap.parse_args()

    baseline_board, base_rec = records_at(args.baseline)
    pinned = H.pin_mains(base_rec)
    report, meta = H.drc(args.baseline, args.baseline.with_suffix('.drc.json'))
    base_ids = H.identities(report)
    unconn = len(report['unconnected_items'])
    cluster = json.loads(args.cluster.read_text())
    cluster = cluster['cluster'] if isinstance(cluster, dict) else cluster
    for c in cluster:
        if 'target_key' not in c:
            raise SystemExit('cluster entries need target_key')
    res = run_cluster(args.src, args.work, cluster, args.baseline, base_ids, unconn, pinned)
    args.out.write_text(json.dumps(res, indent=1) + '\n')
    print(res['verdict'], len(res['blockers']), 'blockers',
          'unconn', res['native_unconnected'], 'ids+', len(res['new_violation_identities']))


if __name__ == '__main__':
    main()
