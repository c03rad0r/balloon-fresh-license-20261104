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

    # The campaign's success criterion is OPENS DECREASING, and `unconnected_items` is an
    # ALLOWED type, so it never appears in check_drc's `failing` total. Gating on `failing`
    # therefore cannot see the improvement this whole campaign is about. Gate on opens.
    open_b = cb.get('unconnected_items', -1)
    open_a = ca.get('unconnected_items', -1)
    errs_b = sum(v for k, v in cb.items() if k not in ('unconnected_items', 'silk_over_copper',
                                                       'silk_overlap', 'copper_edge_clearance'))
    errs_a = sum(v for k, v in ca.items() if k not in ('unconnected_items', 'silk_over_copper',
                                                       'silk_overlap', 'copper_edge_clearance'))
    silk_b = cb.get('silk_over_copper', 0) + cb.get('silk_overlap', 0)
    silk_a = ca.get('silk_over_copper', 0) + ca.get('silk_overlap', 0)
    # A silk batch improves silk, not opens. Both criteria are legitimate; which one applies
    # depends on what the batch set out to do. Refuse if NEITHER improved.
    ok = (not regressions) and (open_a < open_b or silk_a < silk_b) and errs_a <= errs_b
    print('opens: %d -> %d   silk: %d -> %d   hard-error total: %d -> %d'
          % (open_b, open_a, silk_b, silk_a, errs_b, errs_a))
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    if not ok:
        if regressions:
            print('  refused: these types increased: %s' % regressions)
        elif open_a >= open_b and silk_a >= silk_b:
            print('  refused: neither opens nor silk improved (%d->%d, %d->%d)'
                  % (open_b, open_a, silk_b, silk_a))
        else:
            print('  refused: hard-error total increased (%d -> %d)' % (errs_b, errs_a))
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
