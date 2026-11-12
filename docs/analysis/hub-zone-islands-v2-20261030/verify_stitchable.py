#!/usr/bin/env python3
"""Prove or refute the stitchability claims by MEASUREMENT, not geometry alone.

Takes every island the inventory marked legal=True, drops one 0.50 mm via at the
reported candidate site on the island's net, refills, and runs kicad-cli DRC.

Expectation if the claim is right:
    unconnected  86 -> 86 - N
    no NEW clearance/annular violations beyond the 40 pre-existing

A batch that fails is bisected so the failure is attributable to a specific island.
Runs entirely on a copy; the source board is never written.
"""
from __future__ import annotations

raise SystemExit('RETIRED count-only experiment: use validate_stitching.py; historical results are not proof')

import argparse
import collections
import json
import pathlib
import shutil
import subprocess
import sys

import pcbnew as k

STEM = 'hub_board_v10_lora1280_7of9'


def fresh_copy(src_dir: pathlib.Path, work: pathlib.Path) -> pathlib.Path:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for f in src_dir.glob(STEM + '.kicad_*'):
        shutil.copy(f, work / f.name)
    for f in src_dir.glob('*.kicad_dru'):
        shutil.copy(f, work / f.name)
    return work / (STEM + '.kicad_pcb')


def add_vias(pcb: pathlib.Path, sites):
    """sites = [(x_mm, y_mm, netname)]"""
    b = k.LoadBoard(str(pcb))
    netcode = {}
    for net in b.GetNetInfo().NetsByName():
        pass
    for x, y, netname in sites:
        ni = b.FindNet(netname)
        if ni is None:
            raise SystemExit(f'net not found: {netname}')
        v = k.PCB_VIA(b)
        v.SetPosition(k.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
        v.SetWidth(int(round(0.5 * 1e6)))
        v.SetDrill(int(round(0.3 * 1e6)))
        v.SetLayerPair(k.F_Cu, k.B_Cu)
        v.SetViaType(k.VIATYPE_THROUGH)
        v.SetNetCode(ni.GetNetCode())
        b.Add(v)
    filler = k.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    k.SaveBoard(str(pcb), b)


def run_drc(pcb: pathlib.Path, out_json: pathlib.Path, want_raw=False):
    r = subprocess.run(
        ['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', str(out_json),
         '--severity-all', str(pcb)],
        capture_output=True, text=True)
    d = json.loads(out_json.read_text())
    summary = dict(
        unconnected=len(d.get('unconnected_items', [])),
        violations=len(d.get('violations', [])),
        violation_types=sorted({v.get('type') for v in d.get('violations', [])}),
        stdout=r.stdout.strip().splitlines()[-4:],
    )
    return (summary, d) if want_raw else summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(pathlib.Path(__file__).resolve().parents[3]))
    ap.add_argument('--islands', default='islands.json')
    ap.add_argument('--work', default=None)
    ap.add_argument('--out', default='stitch_verification.json')
    args = ap.parse_args()

    repo = pathlib.Path(args.repo)
    src_dir = repo / 'tracker' / 'hardware'
    work = pathlib.Path(args.work) if args.work else repo / '.stitch_work'
    data = json.loads(pathlib.Path(args.islands).read_text())

    claimed = [i for i in data['islands']
               if i['status'] == 'ISOLATED' and i['stitch'] and i['stitch']['legal']]
    print(f'islands claimed stitchable: {len(claimed)}')

    # -- baseline
    pcb = fresh_copy(src_dir, work)
    base, base_raw = run_drc(pcb, work / 'drc_base.json', want_raw=True)
    print('baseline', base)

    sites = [(i['stitch']['candidate_site_mm'][0], i['stitch']['candidate_site_mm'][1],
              i['net']) for i in claimed]

    # -- batch
    pcb = fresh_copy(src_dir, work)
    add_vias(pcb, sites)
    batch = run_drc(pcb, work / 'drc_batch.json')
    print('batch   ', batch)
    expect = base['unconnected'] - len(sites)
    ok = (batch['unconnected'] == expect and
          batch['violations'] <= base['violations'])
    print(f'expected unconnected {expect}, got {batch["unconnected"]} -> {"PASS" if ok else "FAIL"}')

    result = dict(baseline=base, batch=batch, expected_unconnected=expect,
                  batch_pass=bool(ok), claimed=[i['island_id'] for i in claimed],
                  sites=[[s[0], s[1], s[2]] for s in sites], per_island=None)

    if not ok:
        # -- bisect: one via at a time
        print('bisecting...')
        per = []
        def vkey(v):
            return (v.get('type'), v.get('description'),
                    tuple(sorted((i.get('description', '')) for i in v.get('items') or [])))

        base_v = collections.Counter(vkey(v) for v in base_raw['violations'])
        for isl, s in zip(claimed, sites):
            pcb = fresh_copy(src_dir, work / 'one')
            add_vias(pcb, [s])
            r, raw = run_drc(pcb, work / 'drc_one.json', want_raw=True)
            gained = base['unconnected'] - r['unconnected']
            got_v = collections.Counter(vkey(v) for v in raw['violations'])
            added = got_v - base_v
            removed = base_v - got_v
            per.append(dict(island_id=isl['island_id'], net=s[2],
                            site=[s[0], s[1]],
                            unconnected_before=base['unconnected'],
                            unconnected_after=r['unconnected'],
                            resolved=gained,
                            new_violations=sum(added.values()),
                            new_violations_detail=[list(k) for k in added],
                            removed_violations=sum(removed.values()),
                            verdict='PROVEN' if (gained == 1 and not added)
                                    else 'REFUTED'))
            print(f"  {isl['island_id']:34s} resolved={gained} "
                  f"new={sum(added.values())} removed={sum(removed.values())} "
                  f"-> {per[-1]['verdict']}")
            if added:
                for kk in added:
                    print('      +', kk[0], kk[2])
        result['per_island'] = per

    pathlib.Path(args.out).write_text(json.dumps(result, indent=1))
    print('wrote', args.out)


if __name__ == '__main__':
    main()
