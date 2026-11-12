#!/usr/bin/env python3
"""Refill a board copy and run native KiCad DRC, emitting a multiset summary.

Usage: drc.py <board.kicad_pcb> [--no-refill]

Writes <stem>.drc.json next to the board and prints:
  violations total, error/warning split, per-identity multiset counts,
  unconnected count and per-identity multiset counts.
"""
import json
import subprocess
import sys
import pathlib
import hashlib

import pcbnew as k


def refill(pcb):
    b = k.LoadBoard(str(pcb))
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)


def identity(item):
    """Stable identity for a DRC finding, independent of list order.

    Built from the finding type, severity, description and the descriptions of
    the items involved, SORTED. UUIDs are deliberately excluded: measured on
    this board, KiCad's own unconnected equipment pairing is not stable between
    two identical runs (9 of 86 pairs swap partners across runs on a
    byte-identical board), so a UUID-pair identity is not a reproducible key.
    Item descriptions carry the object identity (ref/pad/net/layer) that a human
    reads, and the multiset over them is deterministic - verified by running the
    same board twice and diffing.
    """
    parts = [item.get('type', '?'), item.get('severity', '?'),
             item.get('description', '')]
    descs = sorted(i.get('description', '?') for i in item.get('items', []))
    parts.extend(descs)
    return ' | '.join(parts)


def main():
    pcb = pathlib.Path(sys.argv[1])
    do_refill = '--no-refill' not in sys.argv
    if do_refill:
        refill(pcb)
    sha = hashlib.sha256(pcb.read_bytes()).hexdigest()
    out = pcb.with_suffix('.drc.json')
    r = subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json',
                        '-o', str(out), '--severity-all', str(pcb)],
                       capture_output=True, text=True)
    d = json.loads(out.read_text())
    res = dict(board=pcb.name, sha256=sha, exit=r.returncode,
               violations=len(d['violations']),
               unconnected=len(d['unconnected_items']),
               violation_ids={}, unconnected_ids={},
               severity={})
    for v in d['violations']:
        res['violation_ids'][identity(v)] = res['violation_ids'].get(identity(v), 0) + 1
        s = v.get('severity', '?')
        res['severity'][s] = res['severity'].get(s, 0) + 1
    for v in d['unconnected_items']:
        res['unconnected_ids'][identity(v)] = res['unconnected_ids'].get(identity(v), 0) + 1
    res['violation_ids'] = dict(sorted(res['violation_ids'].items()))
    res['unconnected_ids'] = dict(sorted(res['unconnected_ids'].items()))
    pcb.with_suffix('.drc-summary.json').write_text(json.dumps(res, indent=1))
    print(json.dumps({kk: res[kk] for kk in
                      ('board', 'sha256', 'exit', 'violations', 'unconnected',
                       'severity')}, indent=1))
    print('--- violation multiset ---')
    for kk, v in res['violation_ids'].items():
        print(f'{v:3d}  {kk}')
    print('--- unconnected multiset ---')
    for kk, v in res['unconnected_ids'].items():
        print(f'{v:3d}  {kk}')


if __name__ == '__main__':
    main()
