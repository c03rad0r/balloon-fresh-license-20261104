"""Adopt a batch result ONLY if no violation TYPE regresses, not merely if the total drops.

DEADVIA passed my old criterion (failing 21 -> 19) while hiding +16 copper_edge_clearance,
because those 16 were an artefact of a missing .kicad_dru sidecar. The total-count test was
too weak: -2 dangling vias masked +16 edge errors.

This gate compares per-type counts before vs after and refuses on ANY increase, then copies
the sidecars so the candidate is DRC-ed under the same rules as the live board.

Usage: adopt_batch.py <batchname>
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
REL = 'docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, REL, 'latest.kicad_pcb')
SIDECARS = ('kicad_pro', 'kicad_dru', 'fp-lib-table')


def gate(board):
    r = subprocess.run(['/usr/bin/python3', '-B', 'tracker/hardware/check_drc.py',
                        '--board', board, '--json'],
                       cwd=ROOT, capture_output=True, text=True, timeout=1800)
    try:
        return json.loads(r.stdout[r.stdout.index('{'):])
    except Exception:
        return {'failing': -1, 'counts': {}}


def ensure_sidecars(board_path, ref):
    """Give `board_path` the same sidecar rules as `ref` -- DRC must use the project's rules."""
    for ext in SIDECARS:
        s = ref.replace('.kicad_pcb', '.' + ext)
        d = board_path.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s) and not os.path.exists(d):
            shutil.copy(s, d)
            print('  sidecar copied: %s' % os.path.basename(d))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    name = sys.argv[1]
    B = os.path.join(ROOT, REL, 'batches', name)
    cand = os.path.join(B, 'routed.kicad_pcb')
    if not os.path.exists(cand):
        print('no routed.kicad_pcb in %s' % B)
        return 2

    print('ensuring sidecars on candidate...')
    ensure_sidecars(cand, LIVE)

    before = gate(LIVE)
    after = gate(cand)
    cb, ca = before.get('counts', {}), after.get('counts', {})
    print('\n%-26s %8s %8s %s' % ('violation type', 'before', 'after', 'delta'))
    regressions = []
    for k in sorted(set(cb) | set(ca)):
        vb, va = cb.get(k, 0), ca.get(k, 0)
        d = va - vb
        flag = ''
        if d > 0:
            flag = '  <-- REGRESSION'
            regressions.append((k, vb, va))
        print('%-26s %8d %8d %+8d%s' % (k, vb, va, d, flag))
    print('\nfailing total: %s -> %s   regressions: %d'
          % (before.get('failing'), after.get('failing'), len(regressions)))

    ok = not regressions and after.get('failing', 1) < before.get('failing', 0)
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    if not ok:
        if regressions:
            print('  refused: these types increased: %s' % regressions)
        else:
            print('  refused: failing count did not decrease')
        return 2

    shutil.copy(cand, LIVE)
    for ext in SIDECARS:
        s = cand.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, LIVE.replace('.kicad_pcb', '.' + ext))
    print('ADOPTED -> latest.kicad_pcb')
    json.dump({'before': before, 'after': after, 'name': name},
              open(os.path.join(B, 'adopt.json'), 'w'), indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
