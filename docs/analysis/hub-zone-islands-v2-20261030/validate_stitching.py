"""Native single-via experiments; no count-only legality inference.

Run with system Python, --repo, --work (NEW directory), --inventory and --out.
Connectivity remains provisional: graph landing after refill is not a native
endpoint-to-endpoint proof. No failed sampled site proves non-stitchability.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import pcbnew as k
import run_island_inventory as invmod


def identities(report):
    """Multiset, retaining rule description/layer and stable item identities."""
    return Counter(json.dumps((v['type'], v['severity'], v['description'],
                   sorted((i['uuid'], i['description']) for i in v['items'])))
                   for v in report['violations'])


def drc(pcb):
    out = pcb.with_suffix('.drc.json')
    result = subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json',
                             '--severity-all', '-o', str(out), str(pcb)],
                            capture_output=True, text=True, timeout=180)
    if result.returncode != 0 or not out.exists():
        raise RuntimeError(result.stdout + result.stderr)
    return json.loads(out.read_text())


def fresh(src, work):
    work.mkdir(parents=True, exist_ok=False)
    for pattern in (invmod.STEM + '.kicad_*', '*.kicad_dru', '*lib-table'):
        for f in src.glob(pattern):
            shutil.copy2(f, work / f.name)
    return work / (invmod.STEM + '.kicad_pcb')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--inventory', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    inv = json.loads(args.inventory.read_text())
    if (inv['graph_sigma_components_minus_1'], inv['affected_nets'],
            inv['base_unconnected_pcbnew']) != (86, 22, 86):
        raise RuntimeError('Inventory crosscheck failed')
    src = args.repo / 'tracker/hardware'
    source = src / (invmod.STEM + '.kicad_pcb')
    source_hash = invmod.sha256(source)
    if source_hash != inv['refill']['source_sha256']:
        raise RuntimeError('Inventory source mismatch')
    pcb = fresh(src, args.work / 'baseline')
    b = k.LoadBoard(str(pcb))
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)
    baseline = drc(pcb)
    base_ids = identities(baseline)
    result = dict(status='INCOMPLETE_DRAFT_CONNECTIVITY_PROOF_AND_COVERAGE_PENDING',
                  source_sha256=source_hash, baseline_violations=len(baseline['violations']),
                  baseline_unconnected=len(baseline['unconnected_items']), arms=[])
    # Checkpoint every arm; an interruption cannot erase completed experiments.
    for n, island in enumerate(i for i in inv['islands'] if i['status'] == 'ISOLATED'):
        pcb = fresh(src, args.work / f'arm{n:02d}')
        b = k.LoadBoard(str(pcb))
        v = k.PCB_VIA(b)
        x, y = island['stitch']['candidate_site_mm']
        v.SetPosition(k.VECTOR2I(round(x*1e6), round(y*1e6)))
        v.SetWidth(500000)
        v.SetDrill(300000)
        v.SetViaType(k.VIATYPE_THROUGH)
        v.SetLayerPair(k.F_Cu, k.B_Cu)
        v.SetNet(b.FindNet(island['net']))
        b.Add(v)
        k.ZONE_FILLER(b).Fill(b.Zones())
        k.SaveBoard(str(pcb), b)
        report = drc(pcb)
        added = identities(report) - base_ids
        removed = base_ids - identities(report)
        arm = dict(island_id=island['island_id'], site_mm=[x,y],
                   native_no_new_violations=not bool(added),
                   new_violation_identities=dict(added), removed_violation_identities=dict(removed),
                   unconnected_after=len(report['unconnected_items']),
                   connectivity_proven=False,
                   verdict='UNVERIFIED_MAIN_COMPONENT_LANDING',
                   candidate_board_sha256=invmod.sha256(pcb))
        result['arms'].append(arm)
        if invmod.sha256(source) != source_hash:
            raise RuntimeError('Source changed')
        result['source_unchanged'] = True
        args.out.write_text(json.dumps(result, indent=1)+'\n')
        print(n, island['island_id'], 'no_new_violations=', not bool(added), flush=True)


if __name__ == '__main__':
    main()
