"""Is "24 violations" the real number, or an artefact of unfilled zones?

BRIDGE1 v2 showed 16 copper_edge_clearance errors on a REFILLED board that the live board's
DRC does not report. That suggests the live DRC baseline is being taken against stale or
unfilled zone data, which would understate the true violation count.

This settles it: DRC the live board exactly as it sits, then refill zones and DRC again.
Same board, same rules, one variable. If the counts differ, the number quoted for
order-readiness is wrong and the baseline must be refilled before any further accounting.
"""
import json
import os
import shutil
import subprocess

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
WORK = '/home/c08r4d0r/.hermes/cache/scratch/refill-check'


def drc(board, out):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', out, board],
                   capture_output=True, timeout=1200)
    d = json.load(open(out))
    return d


def summarise(tag, d):
    opens = len(d['unconnected_items'])
    viol = d.get('violations', [])
    errs = [v for v in viol if v.get('severity') == 'error']
    warns = [v for v in viol if v.get('severity') != 'error']
    print('%s' % tag)
    print('   opens %d   violations %d   (errors %d, warnings %d)'
          % (opens, len(viol), len(errs), len(warns)))
    kinds = {}
    for v in errs:
        kinds[v.get('type')] = kinds.get(v.get('type'), 0) + 1
    if kinds:
        print('   error types: %s' % kinds)
    return {'opens': opens, 'violations': len(viol),
            'errors': len(errs), 'warnings': len(warns),
            'error_types': kinds}


def main():
    os.makedirs(WORK, exist_ok=True)
    plain = os.path.join(WORK, 'as-is.kicad_pcb')
    refilled = os.path.join(WORK, 'refilled.kicad_pcb')
    shutil.copy(LIVE, plain)
    for ext in ('kicad_pro', 'kicad_dru'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, plain.replace('.kicad_pcb', '.' + ext))

    print('=== A: live board, exactly as committed')
    a = summarise('', drc(plain, os.path.join(WORK, 'as-is.json')))

    print('\n=== B: same board, zones refilled')
    b = p.LoadBoard(plain)
    nz = len(list(b.Zones()))
    filler = p.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    p.SaveBoard(refilled, b)
    for ext in ('kicad_pro', 'kicad_dru'):
        s = plain.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, refilled.replace('.kicad_pcb', '.' + ext))
    print('   refilled %d zone(s)' % nz)
    bres = summarise('', drc(refilled, os.path.join(WORK, 'refilled.json')))

    print('\n=== DELTA (refilled - as-is)')
    print('   opens %+d   violations %+d   errors %+d'
          % (bres['opens'] - a['opens'], bres['violations'] - a['violations'],
             bres['errors'] - a['errors']))

    if bres['errors'] != a['errors'] or bres['opens'] != a['opens']:
        print('\nVERDICT: DIFFERENT -- the DRC baseline must be taken on a REFILLED board.')
        print('         Numbers quoted from an unfilled board understate the real count.')
        if bres['error_types']:
            print('         refilled error types: %s' % bres['error_types'])
    else:
        print('\nVERDICT: IDENTICAL -- refill does not change the counts; the quoted')
        print('         numbers stand and BRIDGE1 v2 errors came from its own geometry.')

    json.dump({'as_is': a, 'refilled': bres},
              open(os.path.join(ROOT, 'refill-drc-compare.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
