#!/usr/bin/env python3
"""Measure Python line/branch coverage of the real, isolated PCB proof pipeline.

Requires system pcbnew, Shapely and coverage.py (use a system-site-packages venv).
Run: python pipeline_coverage.py --out /absolute/new/scratch/directory
All three pipeline CLIs and unittest discovery execute under branch coverage.
The endpoint CLI reads evidence beside itself, so scripts and hardware inputs are
staged in a fresh repository-shaped scratch tree; tracked evidence is never used
as a substitute for freshly generated evidence. No routing is performed.
Coverage measures Python, NOT KiCad C++ internals or proof completeness.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PIN = '732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561'
STEM = 'hub_board_v10_lora1280_7of9'
MODULES = ('run_island_inventory.py', 'validate_stitching.py', 'endpoint_proof.py')


def assert_source(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != PIN:
        raise RuntimeError('Source SHA256 differs from pinned read-only board')


def reserve_output(path):
    path.mkdir(parents=True, exist_ok=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    source = repo / 'tracker/hardware' / (STEM + '.kicad_pcb')
    assert_source(source)
    reserve_output(out)
    stage = out / 'repo'
    scripts = stage / here.relative_to(repo)
    hardware = stage / 'tracker/hardware'
    scripts.mkdir(parents=True)
    hardware.mkdir(parents=True)
    for path in here.glob('*.py'):
        shutil.copy2(path, scripts / path.name)
    for pattern in (STEM + '.kicad_*', '*.kicad_dru', '*lib-table'):
        for path in source.parent.glob(pattern):
            shutil.copy2(path, hardware / path.name)
    env = dict(os.environ, COVERAGE_FILE=str(out / '.coverage'), PYTHONDONTWRITEBYTECODE='1')
    config = out / 'coverage.ini'
    config.write_text('[run]\nbranch = True\nsource = ' + str(scripts) + '\n[report]\ninclude =\n' + ''.join('    */' + name + '\n' for name in MODULES))
    base = [sys.executable, '-m', 'coverage']
    commands = [
        ('inventory', ['run_island_inventory.py', '--repo', str(stage), '--work', str(out/'inventory-work'), '--out', str(scripts/'islands.json')]),
        ('stitch', ['validate_stitching.py', '--repo', str(stage), '--work', str(out/'stitch-work'), '--inventory', str(scripts/'islands.json'), '--out', str(scripts/'native_validation.json')]),
        ('endpoint', ['endpoint_proof.py', '--evidence', str(out/'stitch-work'), '--out', str(scripts/'endpoint_validation.json')]),
        ('tests', ['-m', 'unittest', 'discover', '-s', str(scripts), '-p', 'test_*.py', '-v']),
    ]
    manifest: dict = dict(source_sha256=PIN, python=sys.version, stages=[])
    try:
        for context, command in commands:
            argv = base + ['run', '--rcfile', str(config), '--append', '--context', context] + command
            with (out/(context+'.log')).open('w') as log:
                result = subprocess.run(argv, cwd=scripts, env=env, stdout=log, stderr=subprocess.STDOUT)
            manifest['stages'].append(dict(context=context, command=argv, returncode=result.returncode))
            print(context, 'exit', result.returncode, flush=True)
            if result.returncode:
                raise RuntimeError(context + ' failed; see ' + str(out/(context+'.log')))
        inventory = json.loads((scripts/'islands.json').read_text())
        native = json.loads((scripts/'native_validation.json').read_text())
        endpoint = json.loads((scripts/'endpoint_validation.json').read_text())
        if (inventory['graph_sigma_components_minus_1'], inventory['affected_nets'], inventory['base_unconnected_pcbnew'], native['baseline_unconnected']) != (86,22,86,86):
            raise RuntimeError('86 records / 22 nets baseline crosscheck failed')
        if len(native['arms']) != inventory['isolated_total'] or len(endpoint['arms']) != inventory['isolated_total']:
            raise RuntimeError('Incomplete isolated-island experiment set')
        manifest['complete'] = True
        manifest['arm_count'] = len(endpoint['arms'])
    finally:
        assert_source(source)
        manifest['source_unchanged'] = True
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        for options in (['report', '-m'], ['json', '-o', str(out/'coverage.json')], ['html', '-d', str(out/'html')]):
            subprocess.run(base + [options[0], '--rcfile', str(config)] + options[1:], cwd=scripts, env=env, check=True)


if __name__ == '__main__':
    main()
