"""Is the refill the trigger for the 16 J_W2 edge errors, or is it my added copper?

Known arms from save_probe.py (all on the live board, no routing):
  A verbatim      0 errors
  B save only     0 errors
  C save+refill   0 errors

BRIDGE3 (bridge + save + refill) gives 16 copper_edge_clearance on J_W2 pads.
Two arms remain untried and they separate the cause:

  D  BRIDGE3's routed board, DRC'd WITHOUT any refill
     -> 16 errors means my copper alone triggers them
     ->  0 errors means refill x my-copper together triggers them

  E  zone-fill comparison: total filled area of every zone, live-refilled vs bridge-refilled
     -> if a GND zone loses/gains area, the bridge changed the pour, and the edge errors
        may be real pour geometry rather than a reporting quirk
"""
import json
import os
import shutil
import subprocess

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
BRIDGE = os.path.join(ROOT, 'batches/BRIDGE3/routed.kicad_pcb')
WORK = '/home/c08r4d0r/.hermes/cache/scratch/refill-trigger'


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


def zone_areas(board_path):
    """Total filled area per zone, keyed by net+layer. Independent of refill timing."""
    b = p.LoadBoard(board_path)
    out = {}
    for z in b.Zones():
        key = '%s@%s' % (z.GetNetname(), b.GetLayerName(z.GetLayer()))
        try:
            area = z.GetFilledArea() / 1e12
        except Exception:
            area = -1.0
        out[key] = out.get(key, 0.0) + area
    return out


def main():
    os.makedirs(WORK, exist_ok=True)

    # --- D: bridge board, no refill ---
    dpath = os.path.join(WORK, 'D-bridge-norefill.kicad_pcb')
    shutil.copy(BRIDGE, dpath)
    copy_sidecars(BRIDGE, dpath)
    rd = drc(dpath, os.path.join(WORK, 'D.json'))
    print('D  BRIDGE3 routed, NO refill  : %s' % rd)

    # --- reference: BRIDGE3 as saved (already refilled) ---
    rbd = drc(BRIDGE, os.path.join(WORK, 'E.json'))
    print('E  BRIDGE3 routed, refilled   : %s' % rbd)

    print('\n=== D vs E')
    if rd['errors'] == 0 and rbd['errors'] > 0:
        print('REFILL IS THE TRIGGER: my copper alone is clean (%d), refilling with it '
              'present reveals %d edge errors.' % (rd['errors'], rbd['errors']))
    elif rd['errors'] > 0:
        print('MY COPPER ALONE triggers %d errors, independent of refill.' % rd['errors'])
    else:
        print('Neither arm reproduces them -- BRIDGE3 file state differs from what I DRC-ed.')

    # --- zone fill comparison ---
    print('\n=== ZONE FILL: live (refilled) vs bridge (refilled)')
    livefill = os.path.join(WORK, 'live-refilled.kicad_pcb')
    shutil.copy(LIVE, livefill)
    copy_sidecars(LIVE, livefill)
    lb = p.LoadBoard(livefill)
    p.ZONE_FILLER(lb).Fill(lb.Zones())
    p.SaveBoard(livefill, lb)
    la = zone_areas(livefill)
    ba = zone_areas(BRIDGE)
    for k in sorted(set(la) | set(ba)):
        dv = ba.get(k, 0) - la.get(k, 0)
        flag = '' if abs(dv) < 0.01 else '   <-- CHANGED'
        print('  %-28s live %9.2f  bridge %9.2f  delta %+8.2f%s'
              % (k, la.get(k, 0), ba.get(k, 0), dv, flag))

    json.dump({'D_no_refill': rd, 'E_refilled': rbd,
               'zones_live': la, 'zones_bridge': ba},
              open(os.path.join(ROOT, 'refill-trigger.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
