#!/usr/bin/env python3
"""Classify the unconnected items on the repaired candidate by ENDPOINT.

Question: how many of the remaining disconnections sit on pads that ADR-136
declares outside the flight interface (J_W pads 2 and 3), versus pads that must
carry a signal in flight?

Read-only. Refills a copy, runs native DRC, and attributes each unconnected
record to its item descriptions. No per-island inference.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
from collections import Counter

STEM = 'hub_board_v10_lora1280_7of9'
SRC = pathlib.Path('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
                   'hub-repair-20261102/output/after')
WORK = pathlib.Path('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/unconn-class')


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    for f in SRC.glob(STEM + '.kicad_*'):
        shutil.copy(f, WORK / f.name)
    pcb = WORK / (STEM + '.kicad_pcb')

    import pcbnew as k
    b = k.LoadBoard(str(pcb))
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)

    out = WORK / 'drc.json'
    r = subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', str(out),
                        '--severity-all', str(pcb)], capture_output=True, text=True)
    d = json.loads(out.read_text())
    unc = d['unconnected_items']

    print(f'unconnected records: {len(unc)}')
    print(f'violations: {len(d["violations"])}')
    print()

    # classify each record by the pads it names
    cat = Counter()
    per_net = Counter()
    details = []
    for rec in unc:
        descs = [i['description'] for i in rec.get('items', [])]
        names = []
        for ds in descs:
            m = re.match(r'Pad (?:\d+ )?\[([^\]]*)\] of (\w+)', ds)
            if m:
                names.append((m.group(2), None))
                continue
            m = re.match(r'Pad (\d+) \[([^\]]*)\] of (\w+)', ds)
            if m:
                names.append((m.group(3), m.group(1)))
                continue
            m = re.search(r'of (\w+)', ds)
            names.append((m.group(1) if m else '?', None))

        refs = {n[0] for n in names}
        is_jw = any(x.startswith('J_W') for x in refs)
        netm = re.search(r'\[([^\]]*)\]', descs[0]) if descs else None
        net = netm.group(1) if netm else '?'
        per_net[net] += 1
        if is_jw:
            cat['J_W (ADR-136 retained-unused pads)'] += 1
        else:
            cat['other'] += 1
        details.append(dict(net=net, refs=sorted(refs), descs=descs,
                            cls='J_W' if is_jw else 'other'))

    for k2, v in cat.most_common():
        print(f'  {k2}: {v}')
    print()
    print('per net:')
    for net, c in per_net.most_common():
        print(f'  {net:16s} {c:3d}')
    print()
    print('J_W records in full:')
    for x in details:
        if x['cls'] == 'J_W':
            print('  ', ' || '.join(x['descs'])[:150])

    (WORK / 'classification.json').write_text(json.dumps(
        dict(unconnected=len(unc), categories=dict(cat), per_net=dict(per_net),
             details=details), indent=1))
    print('\nwrote', WORK / 'classification.json')


if __name__ == '__main__':
    main()
