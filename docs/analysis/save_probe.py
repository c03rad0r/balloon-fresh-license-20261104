"""Does pcbnew SaveBoard itself introduce the 16 copper_edge_clearance errors?

BRIDGE3's before-drc (a byte copy of the live board) shows 0 errors. Its routed.kicad_pcb
shows 16, all "Pad 2/3/4 of J_W2 on F.Cu/B.Cu" 0.05 mm from Edge.Cuts. Refilling zones
alone did NOT produce them (refill-drc-compare: identical, 0 errors).

The remaining variable is the save path: LoadBoard -> SaveBoard. If a no-op save
reproduces the 16, then the errors are a property of how pcbnew rewrites the file, not of
my bridge geometry -- and the live file's DRC has been reading an edge rule that the
rewritten file does not.

Three arms, same board, no routing at all:
  A  live file copied verbatim                       (control)
  B  LoadBoard -> SaveBoard, no modification         (isolates the save)
  C  LoadBoard -> SaveBoard -> ZONE_FILLER -> SaveBoard  (isolates save + refill)
"""
import json
import os
import shutil
import subprocess

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
WORK = '/home/c08r4d0r/.hermes/cache/scratch/save-probe'


def drc(board, out):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', out, board],
                   capture_output=True, timeout=1200)
    d = json.load(open(out))
    viol = d.get('violations', [])
    errs = [v for v in viol if v.get('severity') == 'error']
    kinds = {}
    for v in errs:
        kinds[v.get('type')] = kinds.get(v.get('type'), 0) + 1
    return {'opens': len(d['unconnected_items']), 'viol': len(viol),
            'errors': len(errs), 'kinds': kinds}


def copy_sidecars(src, dst):
    for ext in ('kicad_pro', 'kicad_dru', 'kicad_prl'):
        s = src.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, dst.replace('.kicad_pcb', '.' + ext))


def main():
    os.makedirs(WORK, exist_ok=True)

    # A: control
    a = os.path.join(WORK, 'A-verbatim.kicad_pcb')
    shutil.copy(LIVE, a)
    copy_sidecars(LIVE, a)
    ra = drc(a, os.path.join(WORK, 'A.json'))
    print('A  verbatim copy        : %s' % ra)

    # B: no-op save
    b = os.path.join(WORK, 'B-saved.kicad_pcb')
    shutil.copy(LIVE, b)
    copy_sidecars(LIVE, b)
    bd = p.LoadBoard(b)
    p.SaveBoard(b, bd)
    rb = drc(b, os.path.join(WORK, 'B.json'))
    print('B  load+save (no edit)  : %s' % rb)

    # C: save + refill
    c = os.path.join(WORK, 'C-refilled.kicad_pcb')
    shutil.copy(LIVE, c)
    copy_sidecars(LIVE, c)
    cd = p.LoadBoard(c)
    p.ZONE_FILLER(cd).Fill(cd.Zones())
    p.SaveBoard(c, cd)
    rc = drc(c, os.path.join(WORK, 'C.json'))
    print('C  save+refill          : %s' % rc)

    print('\n=== ANALYSIS')
    if rb['errors'] > ra['errors']:
        print('SaveBoard alone introduces %d error(s): the errors are a SERIALISATION '
              'artefact, not board geometry.' % (rb['errors'] - ra['errors']))
        print('  kinds: %s' % rb['kinds'])
        print('  => The live file cannot be DRC-ed with edge checks after any pcbnew '
              'round-trip, so "0 errors" on the live file is NOT a clean bill of health.')
    elif rc['errors'] > ra['errors'] and rb['errors'] == ra['errors']:
        print('Refill (not the save) introduces the errors.')
    else:
        print('Neither save nor refill introduces errors -- the 16 come from BRIDGE3 '
              'routing geometry.')

    json.dump({'A_verbatim': ra, 'B_saved': rb, 'C_saved_refilled': rc},
              open(os.path.join(ROOT, 'save-probe.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
