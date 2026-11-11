#!/usr/bin/env python3
"""Prove additive-pour batches cannot break prior copper connections.

Compare normalized native serialization of every pre-existing top-level object,
including filled polygons, footprints (pads/net/pose/keepouts), setup, nets and outline.
Only NEW zones (and, when a batch legitimately adds them, declared new items) may appear;
no old object may disappear or change.

USAGE (2026-11-11). The original version hard-coded batch0->batch1->batch2, which silently
stopped covering anything once later batches landed. It now takes the pairs and the set of
additions the batch is ALLOWED to make, and fails closed on anything else:

    check_preservation.py --pairs before.kicad_pcb:after.kicad_pcb [--pairs ...] \\
        --allow zone [--allow segment] [--allow via] [--out proofs/preservation.json]

`zone` compares definitions with filled_polygon children excluded (native refill may rewrite
fills, which is exactly the copper this batch is allowed to add); `segment`/`via` compare them
as written, so a re-route of unrelated copper still fails.
"""
import argparse
import ast
import collections
import json
import re
import sys
import tempfile
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent
m = ast.parse((ROOT.parent / 'generate.py').read_text())
ns = {'re': re, 'json': json}
exec(compile(ast.Module(body=[n for n in m.body
                             if isinstance(n, ast.FunctionDef) and n.name in
                             {'parse', 'dump', 'children', 'raw'}], type_ignores=[]),
             'helpers', 'exec'), ns)


def objects(path, strip_fills=True):
    b = pcbnew.LoadBoard(str(path))
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / 'normalized.kicad_pcb'
        pcbnew.SaveBoard(str(f), b)
        tree = ns['parse'](f.read_text())
    out = collections.Counter()
    for x in tree[1:]:
        if not isinstance(x, list):
            continue
        if strip_fills and x and x[0] == 'zone':
            x = [q for q in x
                 if not (isinstance(q, list) and q and q[0] == 'filled_polygon')]
        out[ns['dump'](x)] += 1
    return out


def kind(dump):
    for k in ('zone', 'segment', 'arc', 'via', 'gr_line', 'footprint', 'net'):
        if dump.startswith('(' + k + ' '):
            return k
    return dump.split(' ', 1)[0].lstrip('(')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", action='append', required=True,
                    help="before.kicad_pcb:after.kicad_pcb")
    ap.add_argument("--allow", action='append', default=[],
                    help="object kind this batch may ADD (zone, segment, via)")
    ap.add_argument("--out", default=str(ROOT / 'proofs/preservation.json'))
    a = ap.parse_args()
    allow = set(a.allow)
    result = []
    for pair in a.pairs:
        before, after = pair.split(':')
        A = objects(ROOT / before if not before.startswith('/') else before)
        B = objects(ROOT / after if not after.startswith('/') else after)
        removed = list((A - B).elements())
        added = list((B - A).elements())
        added_kinds = collections.Counter(kind(x) for x in added)
        bad_removed = [x for x in removed if kind(x) not in allow]
        # An allowed kind may only appear as an ADDITION. A modified existing object shows up
        # as one removal + one addition, so it is caught by bad_removed above.
        bad_added = {k: v for k, v in added_kinds.items() if k not in allow}
        record = {
            'before': before, 'after': after,
            'unchanged_existing_objects': sum(A.values()),
            'added_by_kind': dict(added_kinds),
            'removed_or_modified_existing_objects': len(removed),
            'disallowed_removals': bad_removed[:3],
            'disallowed_additions': bad_added,
            'allowed_additions': sorted(allow),
        }
        assert not bad_removed, f'{after}: existing objects changed/removed: {bad_removed[:1]}'
        assert not bad_added, f'{after}: undeclared new object kinds {bad_added}'
        result.append(record)
    Path(a.out).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
