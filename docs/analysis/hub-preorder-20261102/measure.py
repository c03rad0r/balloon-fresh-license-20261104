#!/usr/bin/env python3
"""Read-only inventory; no SaveBoard, refill, routing or library updates."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import pcbnew

PIN = '732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561'
BOARD = 'tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def measure(repo):
    path = repo / BOARD
    before = sha(path)
    if before != PIN:
        raise SystemExit('STOP: source board changed; re-audit before using saved DRC')
    board = pcbnew.LoadBoard(str(path))
    rows = []
    for fp in sorted(board.GetFootprints(), key=lambda x: x.GetReference()):
        models = []
        for m in fp.Models():
            raw = str(m.m_Filename)
            expanded = raw.replace('${KIPRJMOD}', str(path.parent))
            expanded = expanded.replace('${KICAD9_3DMODEL_DIR}', '/usr/share/kicad/3dmodels')
            expanded = os.path.expandvars(expanded)
            resolved = Path(expanded)
            if not resolved.is_absolute():
                resolved = path.parent / resolved
            models.append({'declared': raw, 'exists_on_this_host': resolved.is_file(),
                           'sha256': sha(resolved) if resolved.is_file() else None})
        rows.append({'ref': fp.GetReference(), 'library_id': str(fp.GetFPID().GetLibNickname()) + ':' + str(fp.GetFPID().GetLibItemName()),
                     'dnp': fp.IsDNP(), 'models': models})
    drc_path = repo / 'docs/analysis/hub-endpoint-audit-20261030/drc.json'
    drc = json.loads(drc_path.read_text())
    result = {'scope': 'read-only; saved same-board DRC, not a fresh DRC run',
              'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
              'board': BOARD, 'sha256_before': before, 'sha256_after': sha(path),
              'project_sha256': sha(path.with_suffix('.kicad_pro')),
              'saved_drc_sha256': sha(drc_path),
              'drc_counts': dict(collections.Counter(v['type'] for v in drc['violations'])),
              'unconnected_records': len(drc['unconnected_items']),
              'violations': drc['violations'],
              'model_summary': {'footprints': len(rows),
                  'with_declarations': sum(bool(r['models']) for r in rows),
                  'with_existing_model': sum(any(m['exists_on_this_host'] for m in r['models']) for r in rows),
                  'no_declaration_refs': [r['ref'] for r in rows if not r['models']],
                  'unresolved_refs': [r['ref'] for r in rows if r['models'] and not any(m['exists_on_this_host'] for m in r['models'])]},
              'footprints': rows,
              'limits': ['Model existence is not body correctness or transform validation.',
                         'No model needed may be valid for pads/fiducials; missing rows need classification.',
                         'No fabrication package is certified by this inventory.']}
    assert result['sha256_after'] == before
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.repo.resolve())
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('sha256_before','sha256_after','drc_counts','unconnected_records','model_summary')}, indent=2))
