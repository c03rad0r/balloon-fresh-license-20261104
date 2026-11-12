#!/usr/bin/env python3
"""Iterate bounded clusters of via sites until no candidate can be accepted.

Per iteration:
  1. scan the CURRENT board (refilled copy) -> isolated islands + exact
     annulus-overlap sites;
  2. plan a bounded cluster (one net, <= max-islands, target components
     pairwise disjoint);
  3. prove the cluster (stage_b: C1..C7 + zero-contact + no-via control);
  4. PROVEN -> adopt the board, record, continue;
     REJECTED -> bisect: prove each member alone, adopt the passing ones,
     record every rejection with the runner's precise reason.

Every accepted step re-verifies that the ORIGINAL pinned main member set of the
global baseline is still one component containing the target, so "joined main"
always means the component that was main in the untouched repaired candidate.

Usage:
  iterate.py --source BOARD --workdir DIR --out results.json \
             [--max-islands 4] [--max-iterations 12] [--net GND]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

import pcbnew as k

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import prove as P  # noqa: E402


def records_at(pcb, exclude=(), tolerance=H.TOL):
    b = k.LoadBoard(str(pcb))
    b.BuildConnectivity()
    return b, H.snapshot(b, exclude_uuids=exclude, tolerance=tolerance)


def scan(pcb, workdir, tag):
    """Run stage A on the current board; returns the parsed scan."""
    w = workdir / f'scan-{tag}'
    out = workdir / f'scan-{tag}.json'
    cmd = ['/usr/bin/python3', str(HERE / 'stage_a_scan.py'), '--board', str(pcb),
           '--work', str(w), '--out', str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stdout + res.stderr)
    return json.loads(out.read_text())


def origin_main_check(records_before, records_after, mapping, orig_main, target_key):
    """The ORIGINAL pinned main member set must be one component containing target."""
    rev = {v: kk for kk, v in mapping.items()}
    if not set(orig_main) <= set(records_before):
        raise ValueError('original main member missing from before-state')
    roots = {records_after[rev[m]]['root'] for m in orig_main}
    if len(roots) != 1:
        raise ValueError('original pinned main is split after the edit')
    if records_after[rev[target_key]]['root'] not in roots:
        raise ValueError('target not in the ORIGINAL pinned main component')
    return True


def prove_cluster(cur_pcb, base_pcb_for_this_step, cluster, workdir, tag,
                  base_ids, base_unconn, pinned, orig_main):
    w = workdir / f'run-{tag}'
    pcb = H.fresh_copy(cur_pcb, w)
    netname = cluster[0]['net']
    b, uuids = P.add_vias(pcb, cluster, netname)
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)
    report, meta = H.drc(pcb, w / 'after.drc.json')
    ids_after = H.identities(report)
    added = ids_after - base_ids
    removed = base_ids - ids_after
    nat_unconn = len(report['unconnected_items'])
    for c, u in zip(cluster, uuids):
        c['via_uuid'] = u

    res = dict(tag=tag, cluster=[{kk: vv for kk, vv in c.items()} for c in cluster],
               added_via_uuids=uuids, after_board=str(pcb), after_sha=H.sha256(pcb),
               drc=meta, native_violations=len(report['violations']),
               native_unconnected=nat_unconn,
               new_violation_identities=dict(added),
               removed_violation_identities=dict(removed),
               native_no_new_violations=not added, blockers=[], checks={},
               verdict='REJECTED')

    _, after = records_at(pcb)
    _, novia = records_at(pcb, exclude=uuids)
    _, before = records_at(cur_pcb)
    try:
        chk = P.prove(before, after, novia, cluster, pinned, nat_unconn, '0.004 mm')
        res['checks']['nominal'] = chk
        mapping, _ = H.correspondence(before, after, uuids)
        for c in cluster:
            origin_main_check(before, after, mapping, orig_main[c['net']], c['target_key'])
        res['checks']['orig_main_preserved'] = True
    except ValueError as exc:
        res['blockers'].append('nominal: ' + str(exc))
        return res, None

    try:
        _, zb = records_at(base_pcb_for_this_step, tolerance=0)
        _, zb_cur = records_at(cur_pcb, tolerance=0)
        b2 = k.LoadBoard(str(pcb)); b2.BuildConnectivity()
        za = H.snapshot(b2, tolerance=0)
        zn = H.snapshot(b2, exclude_uuids=uuids, tolerance=0)
        zchk = P.prove(zb_cur, za, zn, cluster, pinned, nat_unconn, '0.000 mm')
        res['checks']['zero_tolerance'] = zchk
    except ValueError as exc:
        res['blockers'].append('zero_tolerance: ' + str(exc))
        return res, None

    if res['native_no_new_violations'] is False:
        res['blockers'].append('native_drc: %d new violation identities'
                               % sum(added.values()))
    if not (chk['c3_pinned_main_joined'] and zchk['c3_pinned_main_joined']):
        res['blockers'].append('c3: pinned main not provably joined')
    if not (chk['c4_exact_join'] and zchk['c4_exact_join']):
        res['blockers'].append('c4: partition is not exactly the declared merge '
                               '(merged %d, expected %d)'
                               % (chk['c4_components_merged'],
                                  chk['c4_expected_components_merged']))
    if not (chk['c5_no_via_refill_control'] and zchk['c5_no_via_refill_control']):
        res['blockers'].append('c5: refill alone changed the partition')
    if not (chk['native_matches_graph'] and zchk['native_matches_graph']):
        res['blockers'].append('native/graph sigma disagree (%d vs %d)'
                               % (nat_unconn, chk['graph_sigma_after']))
    ok = not res['blockers']
    res['verdict'] = 'PROVEN_LEGAL_JOIN' if ok else 'REJECTED'
    return res, (pcb if ok else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, type=pathlib.Path)
    ap.add_argument('--workdir', required=True, type=pathlib.Path)
    ap.add_argument('--out', required=True, type=pathlib.Path)
    ap.add_argument('--max-islands', type=int, default=4)
    ap.add_argument('--max-iterations', type=int, default=12)
    ap.add_argument('--net', default='GND')
    ap.add_argument('--min-main-overlap', type=float, default=0.02)
    args = ap.parse_args()
    wd = args.workdir
    wd.mkdir(parents=True, exist_ok=True)

    # Global baseline: untouched repaired candidate, refilled on a copy.
    gbase_dir = wd / 'global-baseline'
    if gbase_dir.exists():
        shutil.rmtree(gbase_dir)
    gbase = H.fresh_copy(args.source, gbase_dir)
    H.refill_save(gbase)
    gbase_sha = H.sha256(gbase)
    _, grec = records_at(gbase)
    orig_pinned = H.pin_mains(grec)
    orig_main = {net: info['members'] for net, info in orig_pinned.items()}
    base_report, _ = H.drc(gbase, wd / 'global-baseline.drc.json')
    base_ids = H.identities(base_report)
    base_unconn = len(base_report['unconnected_items'])

    results = dict(source_sha256=H.sha256(args.source), global_baseline_sha=gbase_sha,
                   baseline_violations=len(base_report['violations']),
                   baseline_unconnected=base_unconn,
                   baseline_sigma=H.sigma(grec),
                   baseline_violation_types=sorted({v['type'] for v in base_report['violations']}),
                   original_pinned_main={n: dict(n_members=i['n_members'], n_pads=i['n_pads'])
                                         for n, i in orig_pinned.items() if i['n_members'] > 0},
                   steps=[], rejections=[], final=None)
    cur = gbase
    accepted = []
    for it in range(args.max_iterations):
        sc = scan(cur, wd, f'{it:02d}')
        results['steps'].append(dict(iteration=it, board=cur.name,
                                     board_sha=H.sha256(cur),
                                     isolated=sc['isolated_total'],
                                     sigma=sc['graph_sigma'],
                                     native=sc['native_unconnected'],
                                     islands_with_sites=sc['isolated_with_sites']))
        # bounded cluster, one net, disjoint target components
        _, crec = records_at(cur)
        pinned = H.pin_mains(crec)
        import pcbnew as _k
        bb = _k.LoadBoard(str(cur)); bb.BuildConnectivity()
        rec = H.snapshot(bb)
        picks = []
        for i in sc['islands']:
            if i['is_main_body'] or i['net'] != args.net:
                continue
            if not i.get('candidate_sites'):
                continue
            best = max((s for s in i['candidate_sites']
                        if s['annulus_overlap_main_mm2'] >= args.min_main_overlap),
                       key=lambda s: s['annulus_overlap_main_mm2'], default=None)
            if best is None:
                continue
            picks.append(dict(island_id=i['island_id'], target_key=i['target_key'],
                              net=i['net'], x=best['x'], y=best['y'],
                              annulus_overlap_component_mm2=best['annulus_overlap_component_mm2'],
                              annulus_overlap_main_mm2=best['annulus_overlap_main_mm2'],
                              area_mm2=i['area_mm2']))
        if not picks:
            results['steps'].append(dict(iteration=it, stop='no candidate sites left'))
            break
        picks.sort(key=lambda p: -p['annulus_overlap_main_mm2'])
        cluster, roots = [], set()
        for p in picks:
            r = rec[p['target_key']]['root']
            if r in roots:
                continue
            roots.add(r)
            cluster.append(p)
            if len(cluster) >= args.max_islands:
                break

        res, newpcb = prove_cluster(cur, gbase, cluster, wd, f'{it:02d}-c',
                                    base_ids, base_unconn, pinned, orig_main)
        if newpcb is not None:
            results['steps'].append(dict(iteration=it, cluster_accepted=res['tag'],
                                         islands=[c['island_id'] for c in cluster],
                                         unconnected=res['native_unconnected'],
                                         new_identities=0))
            accepted.append(dict(tag=res['tag'], islands=[c['island_id'] for c in cluster],
                                 sites=[dict(island_id=c['island_id'], x=c['x'], y=c['y'],
                                             via_uuid=c['via_uuid']) for c in cluster],
                                 unconnected=res['native_unconnected'],
                                 board_sha=res['after_sha']))
            cur = newpcb
            results['final'] = dict(board=str(cur), sha=H.sha256(cur),
                                    unconnected=res['native_unconnected'],
                                    violations=res['native_violations'])
            results['accepted'] = accepted
            args.out.write_text(json.dumps(results, indent=1) + '\n')
            continue

        # cluster rejected -> bisect to singletons
        results['rejections'].append(dict(tag=res['tag'], level='cluster',
                                          islands=[c['island_id'] for c in cluster],
                                          blockers=res['blockers'],
                                          new_identities=dict(res['new_violation_identities'])))
        adopted = False
        for n, c in enumerate(cluster):
            single = [c]
            sres, spcb = prove_cluster(cur, gbase, single, wd, f'{it:02d}-s{n}',
                                       base_ids, base_unconn, pinned, orig_main)
            if spcb is not None:
                accepted.append(dict(tag=sres['tag'], islands=[c['island_id']],
                                     sites=[dict(island_id=c['island_id'], x=c['x'],
                                                 y=c['y'], via_uuid=c['via_uuid'])],
                                     unconnected=sres['native_unconnected'],
                                     board_sha=sres['after_sha']))
                cur = spcb
                adopted = True
                results['final'] = dict(board=str(cur), sha=H.sha256(cur),
                                        unconnected=sres['native_unconnected'],
                                        violations=sres['native_violations'])
                results['accepted'] = accepted
                args.out.write_text(json.dumps(results, indent=1) + '\n')
            else:
                results['rejections'].append(dict(tag=sres['tag'], level='island',
                                                  islands=[c['island_id']],
                                                  site_mm=[c['x'], c['y']],
                                                  annulus_overlap_main_mm2=c['annulus_overlap_main_mm2'],
                                                  blockers=sres['blockers'],
                                                  new_identities=dict(sres['new_violation_identities'])))
                args.out.write_text(json.dumps(results, indent=1) + '\n')
        if not adopted:
            results['steps'].append(dict(iteration=it,
                                         stop='every candidate in this iteration was rejected'))
            break
    args.out.write_text(json.dumps(results, indent=1) + '\n')
    fin = results.get('final') or {}
    print('accepted', len(accepted), 'rejected', len(results['rejections']),
          'final unconnected', fin.get('unconnected'), 'sha', fin.get('sha'))


if __name__ == '__main__':
    main()
