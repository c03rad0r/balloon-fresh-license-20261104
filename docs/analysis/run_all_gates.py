#!/usr/bin/env python3
"""Run the SAME gate suite as scripts/git-hooks/pre-commit-board-gates.py, on any board.

WHY THIS EXISTS
The pre-commit hook runs five gates and takes no board argument -- it inspects the staged set.
That means I cannot run "the project gate suite" against an analysis board from the hook, and
in practice I ran only two of the five by hand (check_drc, check_schematic_parity). I never ran
check_silk until a separate discovery, and never ran check_socket_edge_tracks at all.

A partial gate suite is how a board looks green while a binding requirement is unmet. This
script names all five, runs each with the correct argument form, and prints one verdict.

Argument forms differ per gate and that is worth recording:
  check_drc.py                --board <path>
  check_schematic_parity.py   --board <path>
  check_socket_edge_tracks.py <path>        (positional)
  check_hv_lanes.py           --board <path> (report-only without --strict)
  check_silk.py               --board <path>
"""
import os
import subprocess
import sys

HW = 'tracker/hardware'

GATES = [
    ('check_drc.py', ['--board', None], True),
    ('check_schematic_parity.py', ['--board', None], True),
    ('check_socket_edge_tracks.py', [None], True),
    ('check_hv_lanes.py', [None], False),   # report-only by design (ADR-143), positional board
    ('check_silk.py', ['--board', None], True),
]

# The pre-commit hook also runs this, BEFORE any of the above, and this runner did not -- which is
# how a 'five gates, authoritative' status was quoted while a sixth gate went unchecked. It is a
# pytest file, not a check_*.py script, and it needs an interpreter with BOTH pytest and pcbnew.
ROUTER_AGREEMENT = 'tests/test_router_grid_validator_agreement.py'
ROUTER_AGREEMENT_PYTHONS = [
    os.path.expanduser('~/venvs/kicad/bin/python'),
    '/usr/bin/python3',
]

KICAD_PYTHON = os.path.expanduser('~/venvs/kicad/bin/python')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    board = os.path.abspath(sys.argv[1])
    if not os.path.exists(board):
        print('no such board: %s' % board)
        return 2

    results = []

    # SIXTH GATE FIRST, exactly as the pre-commit hook orders it.
    ra_path = os.path.join(os.path.dirname(HW), '..', ROUTER_AGREEMENT)
    ra_path = os.path.abspath(ra_path)
    ra_status = 'MISSING'
    if not os.path.exists(ra_path):
        print('%-32s MISSING (hook REFUSES in this case)' % 'router_agreement')
    else:
        ran = False
        for py in ROUTER_AGREEMENT_PYTHONS:
            if not os.path.exists(py):
                continue
            r = subprocess.run([py, '-B', ra_path], capture_output=True, text=True, timeout=1800)
            out = (r.stdout or '') + (r.stderr or '')
            if 'ModuleNotFoundError' in out and 'pcbnew' in out:
                continue
            if 'ModuleNotFoundError' in out and 'pytest' in out:
                continue      # wrong interpreter, try the next (matches the hook's behaviour)
            ran = True
            ra_status = 'PASS' if r.returncode == 0 else 'FAIL'
            npass = out.count('PASS ')
            print('\n=== %-30s %s  (%d tests)' % ('router_agreement', ra_status, npass))
            if r.returncode != 0:
                for ln in out.strip().splitlines()[-6:]:
                    print('    ' + ln)
            break
        if not ran:
            ra_status = 'REFUSED'
            print('%-32s REFUSED -- no interpreter with pytest+pcbnew' % 'router_agreement')
    results.append(('router_agreement', ra_status, True))

    for (script, argfmt, blocking) in GATES:
        path = os.path.join(HW, script)
        if not os.path.exists(path):
            print('%-32s MISSING' % script)
            results.append((script, 'MISSING', blocking))
            continue
        args = [a if a is not None else board for a in argfmt]
        r = subprocess.run(['/usr/bin/python3', '-B', path] + args,
                           capture_output=True, text=True, timeout=1800)
        out = (r.stdout or '') + (r.stderr or '')
        tail = [ln for ln in out.splitlines()
                if any(k in ln for k in ('FAIL', 'SILK:', 'DRC:', 'PARITY:', 'PASS', 'VERDICT',
                                         'conformance', 'REFUSED'))]
        ok = r.returncode == 0
        status = 'PASS' if ok else 'FAIL'
        if not blocking and ok:
            status = 'PASS (report-only)'
        print('\n=== %-30s %s' % (script, status))
        for ln in tail[:6]:
            print('   ', ln.strip()[:130])
        if not ok and not tail:
            print('    ', out.strip().splitlines()[-1][:130] if out.strip() else '(no output)')
        results.append((script, status, blocking))

    print('\n' + '=' * 62)
    blocking_fails = [s for (s, st, b) in results if b and not st.startswith('PASS')]
    for (s, st, b) in results:
        print('  %-32s %s%s' % (s, st, '' if b else '   [non-blocking]'))
    print('=' * 62)
    print('VERDICT: %s'
          % ('ALL BLOCKING GATES PASS' if not blocking_fails
             else '%d BLOCKING GATE(S) FAIL: %s' % (len(blocking_fails), blocking_fails)))
    return 0 if not blocking_fails else 1


if __name__ == '__main__':
    sys.exit(main())
