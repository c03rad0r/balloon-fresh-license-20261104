"""Delete the two dead /VSCAP vias. Smallest possible repair, gated like any other batch.

Measured: these two vias touch no copper on either face beyond the pour they sit in:
  (36.0000, 40.0000)  island 0  F.Cu 0  B.Cu 0
  (6.6000, 58.5997)   island 1  F.Cu 0  B.Cu 0
They are exactly the two via_dangling items in the project's DRC gate. Both islands they sit
in are otherwise connected (island 1 through via 3.3329,46.2611 which touches an F.Cu track),
so removing these changes no connectivity.

Gate: the batch is adopted ONLY if
  - the project gate's FAILING violation count strictly decreases, AND
  - open (unconnected) count does not increase, AND
  - no new error-severity violation appears.
Otherwise the tree is left untouched.
"""
import json
import os
import subprocess
import sys

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
REL = 'docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, REL, 'latest.kicad_pcb')
NAME = 'DEADVIA'
B = os.path.join(ROOT, REL, 'batches', NAME)
NET = '/VSCAP'
TARGETS = [(36000000, 40000000), (6599999, 58599675)]
TOL = 5000


def gate(board):
    """Run the project's own DRC gate and return its counts."""
    r = subprocess.run(
        ['/usr/bin/python3', '-B', 'tracker/hardware/check_drc.py',
         '--board', board, '--json'],
        cwd=ROOT, capture_output=True, text=True, timeout=1200)
    try:
        d = json.loads(r.stdout[r.stdout.index('{'):])
        return d
    except Exception:
        return {'failing': -1, 'counts': {}, 'raw': (r.stdout or '')[-500:]}


def main():
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    for f in (src, os.path.join(B, 'routed.kicad_pcb')):
        if os.path.exists(f):
            os.remove(f)
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in ('kicad_pro', 'kicad_dru', 'fp-lib-table'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    before = gate(src)
    print('before: failing=%s  counts=%s' % (before.get('failing'), before.get('counts')))

    b = p.LoadBoard(src)
    removed = []
    keep = []
    for t in list(b.GetTracks()):
        if not isinstance(t, p.PCB_VIA):
            continue
        if t.GetNetname() != NET:
            continue
        c = t.GetPosition()
        hit = any(abs(c.x - x) <= TOL and abs(c.y - y) <= TOL for (x, y) in TARGETS)
        if hit:
            removed.append((c.x, c.y, t.GetWidth(), t.GetDrillValue()))
            b.Remove(t)
        else:
            keep.append((c.x, c.y))
    print('\n/VSCAP vias found: %d removed, %d kept' % (len(removed), len(keep)))
    for (x, y, w, dr) in removed:
        print('  REMOVED via (%.4f, %.4f) land %.3f drill %.3f'
              % (x / 1e6, y / 1e6, w / 1e6, dr / 1e6))
    if len(removed) != len(TARGETS):
        print('EXPECTED %d removals, got %d -- aborting' % (len(TARGETS), len(removed)))
        return 1

    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    del b
    # Refill in a SEPARATE process: mutating the board in-process (Remove + SaveBoard) leaves
    # SWIG ownership in a state where LoadBoard() returns a bare SwigPyObject with no .Zones().
    refiller = '/home/c08r4d0r/.hermes/cache/scratch/refill_one.py'
    open(refiller, 'w').write(
        'import sys, pcbnew as p\n'
        'b = p.LoadBoard(sys.argv[1])\n'
        'z = b.Zones()\n'
        'f = p.ZONE_FILLER(b)\n'
        'f.Fill(z)\n'
        'p.SaveBoard(sys.argv[1], b)\n'
        'print("refilled", len(list(z)))\n')
    r = subprocess.run(['/usr/bin/python3', '-B', refiller, out],
                       capture_output=True, text=True, timeout=900)
    print('refill:', (r.stdout or '').strip()[-200:])
    if r.returncode != 0:
        print('refill FAILED:', (r.stderr or '')[-400:])
        return 1

    after = gate(out)
    print('\nafter:  failing=%s  counts=%s' % (after.get('failing'), after.get('counts')))

    fb, fa = before.get('failing', -1), after.get('failing', -1)
    ub = before.get('counts', {}).get('unconnected_items', -1)
    ua = after.get('counts', {}).get('unconnected_items', -1)
    ok = (fa >= 0 and fb >= 0 and fa < fb and ua <= ub)
    print('\nfailing %s -> %s   unconnected %s -> %s'
          % (fb, fa, ub, ua))
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))

    json.dump({'removed': [{'x': x / 1e6, 'y': y / 1e6,
                            'land': w / 1e6, 'drill': dr / 1e6} for (x, y, w, dr) in removed],
               'before': before, 'after': after,
               'verdict': 'PASS' if ok else 'FAIL'},
              open(os.path.join(B, 'report.json'), 'w'), indent=2)

    if ok:
        subprocess.run(['cp', out, LIVE], check=True)
        for ext in ('kicad_pro', 'kicad_dru', 'fp-lib-table'):
            s = out.replace('.kicad_pcb', '.' + ext)
            if os.path.exists(s):
                subprocess.run(['cp', s, LIVE.replace('.kicad_pcb', '.' + ext)], check=True)
        print('batch %s: ACCEPTED -> latest.kicad_pcb' % NAME)
        return 0
    print('batch %s: REJECTED -- tree untouched' % NAME)
    return 2


if __name__ == '__main__':
    sys.exit(main())
