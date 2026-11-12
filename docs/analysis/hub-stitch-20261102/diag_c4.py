#!/usr/bin/env python3
"""Diagnose why c4_exact_join reports False while merged==expected.

Prints the component-level diff between the actual after-partition and the
partition C4 predicted, for one rejected arm.
"""
import argparse
import json
import pathlib
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', required=True, type=pathlib.Path)
    ap.add_argument('--after', required=True, type=pathlib.Path)
    ap.add_argument('--scan', required=True, type=pathlib.Path)
    ap.add_argument('--island', required=True)
    args = ap.parse_args()

    _, base = records_at(args.baseline)
    pinned = H.pin_mains(base)
    after_ = records_at(args.after)[1]
    scan = json.loads(args.scan.read_text())
    isl = {i['island_id']: i for i in scan['islands']}[args.island]

    base_part = H.partition(base)
    after_part = H.partition(after_)
    key = isl['target_key']
    def comp_of(records, key):
        return frozenset(k2 for k2, r in records.items()
                         if r['root'] == records[key]['root'])
    t_before = comp_of(base, key)
    net = base[key]['item']['net']
    m = pinned[net]['members']

    removed = {frozenset(t_before), frozenset(m)}
    merged = frozenset(t_before | m)
    expected = (base_part - removed) | {merged}

    print(f'island={args.island} net={net}')
    print(f'base components : {len(base_part)}')
    print(f'after components: {len(after_part)}')
    print(f'expected        : {len(expected)}')
    print(f'exact match     : {after_part == expected}')
    print()
    print('components in after but NOT in expected:')
    for c in sorted((after_part - expected), key=lambda s: -len(s))[:6]:
        print(f'  size={len(c)}  sample={sorted(c)[:3]}')
    print('components in expected but NOT in after:')
    for c in sorted((expected - after_part), key=lambda s: -len(s))[:6]:
        print(f'  size={len(c)}  sample={sorted(c)[:3]}')


if __name__ == '__main__':
    main()
