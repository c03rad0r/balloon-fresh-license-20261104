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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    board = os.path.abspath(sys.argv[1])
    if not os.path.exists(board):
        print('no such board: %s' % board)
        return 2

    results = []
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
