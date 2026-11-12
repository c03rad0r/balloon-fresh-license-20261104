#!/usr/bin/env python3
"""Build a bounded cluster: one net, at most N islands, sites chosen by exact
annulus overlap. Clusters are the unit of iteration: native DRC after each one.

Safety property that makes batching sound: the proof REQUIRES the after-partition
to equal the before-partition with exactly the declared components merged. Two
vias in one cluster can therefore only both be accepted if they join exactly
their own declared target to the SAME pinned main and nothing else — a
cross-join between two member islands would show up as an unexpected merge and
be rejected. `--isolated-targets` additionally verifies with the graph that the
cluster's target components are pairwise disjoint before the run.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as H  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', required=True, type=pathlib.Path)
    ap.add_argument('--baseline', required=True, type=pathlib.Path)
    ap.add_argument('--net', default='GND')
    ap.add_argument('--max-islands', type=int, default=4)
    ap.add_argument('--min-main-overlap', type=float, default=0.02)
    ap.add_argument('--exclude', default='', help='comma separated island_ids')
    ap.add_argument('--out', required=True, type=pathlib.Path)
    args = ap.parse_args()

    scan = json.loads(args.scan.read_text())
    excl = {e for e in args.exclude.split(',') if e}

    import pcbnew as k
    b = k.LoadBoard(str(args.baseline))
    b.BuildConnectivity()
    rec = H.snapshot(b)
    pinned = H.pin_mains(rec)

    picks = []
    for i in scan['islands']:
        if i['is_main_body'] or i['net'] != args.net:
            continue
        if i['island_id'] in excl:
            continue
        if not i.get('candidate_sites'):
            continue
        best = None
        for s in i['candidate_sites']:
            if s['annulus_overlap_main_mm2'] < args.min_main_overlap:
                continue
            if best is None or s['annulus_overlap_main_mm2'] > best['annulus_overlap_main_mm2']:
                best = s
        if best is None:
            continue
        picks.append(dict(island_id=i['island_id'], target_key=i['target_key'],
                          net=i['net'], x=best['x'], y=best['y'],
                          annulus_overlap_component_mm2=best['annulus_overlap_component_mm2'],
                          annulus_overlap_main_mm2=best['annulus_overlap_main_mm2'],
                          area_mm2=i['area_mm2']))
    picks.sort(key=lambda p: -p['annulus_overlap_main_mm2'])
    cluster = picks[:args.max_islands]

    # disjointness of the target components (a cluster must not pre-join two members)
    roots = [rec[c['target_key']]['root'] for c in cluster]
    if len(set(roots)) != len(roots):
        raise SystemExit('cluster targets are already in the same component - refuse to batch')

    args.out.write_text(json.dumps(dict(params=dict(net=args.net,
                                                    max_islands=args.max_islands,
                                                    min_main_overlap=args.min_main_overlap),
                                        remaining_candidates=len(picks),
                                        cluster=cluster), indent=1) + '\n')
    print(f'cluster of {len(cluster)} from {len(picks)} remaining '
          f'({args.net}); sites: {[c["island_id"] for c in cluster]}')


if __name__ == '__main__':
    main()
