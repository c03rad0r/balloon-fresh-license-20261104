"""Final control: is the trigger the DOUBLE save/refill cycle, not my added copper?

Established arms on the live board (save_probe.py), all 0 errors:
  A verbatim copy
  B LoadBoard -> SaveBoard                    (one cycle, no refill)
  C LoadBoard -> fill -> SaveBoard            (one cycle, with refill)

BRIDGE3 did something neither did:  LoadBoard -> add copper -> SaveBoard ->
                                    LoadBoard -> fill -> SaveBoard     (TWO cycles)

and yields 16 copper_edge_clearance errors on J_W2 pads that are byte-identical to the
live board's and sit tens of mm from the bridge.

This arm adds NO copper:
  F  LoadBoard -> SaveBoard -> LoadBoard -> fill -> SaveBoard   (two cycles)
  G  LoadBoard -> fill -> SaveBoard -> LoadBoard -> fill -> SaveBoard (three cycles)

If F reproduces the 16, the trigger is serialisation order and the errors were always
latent in the file -- nothing to do with my bridge, and a reason to distrust the CLI DRC
baseline entirely. If F is clean, my copper is implicated and BRIDGE3 stays rejected.
"""
import json
import os
import shutil
import subprocess

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
WORK = '/home/c08r4d0r/.hermes/cache/scratch/cycle-probe'


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


def sidecars(src, dst):
    for ext in ('kicad_pro', 'kicad_dru', 'kicad_prl'):
        s = src.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, dst.replace('.kicad_pcb', '.' + ext))


def main():
    os.makedirs(WORK, exist_ok=True)

    # F: two save cycles, no copper added
    f = os.path.join(WORK, 'F-two-cycles.kicad_pcb')
    shutil.copy(LIVE, f)
    sidecars(LIVE, f)
    b = p.LoadBoard(f)
    p.SaveBoard(f, b)
    b = p.LoadBoard(f)
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(f, b)
    rf = drc(f, os.path.join(WORK, 'F.json'))
    print('F  two save cycles, no copper added : %s' % rf)

    # G: three cycles
    g = os.path.join(WORK, 'G-three-cycles.kicad_pcb')
    shutil.copy(LIVE, g)
    sidecars(LIVE, g)
    b = p.LoadBoard(g)
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(g, b)
    b = p.LoadBoard(g)
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(g, b)
    rg = drc(g, os.path.join(WORK, 'G.json'))
    print('G  three save cycles                : %s' % rg)

    print('\n=== VERDICT')
    if rf['errors'] > 0:
        print('REPRODUCED WITH NO COPPER ADDED (%d errors).' % rf['errors'])
        print('The trigger is the save/refill cycle, NOT the bridge. These 16 edge errors')
        print('are latent in the file and can surface on any round-trip -- which means')
        print('"0 errors" from a single-pass CLI DRC is not a trustworthy gate for this')
        print('board. BRIDGE3 is exonerated on this specific point.')
    else:
        print('NOT reproduced without copper: the 16 require my added copper. BRIDGE3')
        print('stays rejected and the mechanism remains unexplained.')

    json.dump({'F_two_cycles': rf, 'G_three_cycles': rg},
              open(os.path.join(ROOT, 'cycle-probe.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
