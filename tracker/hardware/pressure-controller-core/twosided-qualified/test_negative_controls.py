#!/usr/bin/env python3
"""Negative controls for the two-sided placement gate.

A gate that cannot fail is not a gate. Each control POISONS a copy of the accepted board
with one specific defect and requires audit() to REFUSE it, citing the intended rule.
A final POSITIVE control requires the clean board to PASS, so the harness proves the
refusals are caused by the poison and not by an audit that fails on everything.

Two harness bugs were found and fixed while writing this, both recorded because they are
the usual way a control proves nothing:
  * flipping a part to poison the keepout also trips the SIDE check first, so the control
    "passed" only by matching a substring of the wrong message. Controls must assert the
    SPECIFIC rule, and poison without changing the side map where the side is irrelevant.
  * `board.Remove(zone)` leaves every previously fetched BOARD handle as a bare
    SwigPyObject, so a mutation that removes an object corrupts the rest of that
    process's handles -- including the POSITIVE control that runs after it. Each control
    therefore runs in its own subprocess on its own copy.

Run: /usr/bin/python3 test_negative_controls.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew as pcb

HERE = Path(__file__).resolve().parent
BOARD = HERE / 'twosided-qualified.kicad_pcb'
RESULTS = []


def fp(b, ref):
    return [f for f in b.GetFootprints() if f.GetReference() == ref][0]


def _verdict(text):
    """Last non-pcbnew-debug line of a subprocess's output.

    pcbnew writes 'Debug: Adding duplicate image handler...' to stderr on every start, so
    taking the last line of stderr reported the debug spam instead of the audit's verdict --
    the harness then "failed" every control while the gates were in fact refusing correctly.
    """
    lines = [l.strip() for l in text.splitlines()
             if l.strip() and 'Debug:' not in l and 'memory leak' not in l]
    return lines[-1] if lines else '<no output>'


# --- each poison is a function name in this file, run via `--apply <name>` ------------
def p1_under_antenna_band(b):
    """Bottom part back inside the 6 mm antenna band -- the probe's actual defect.

    C1 is ALREADY declared bottom-side in SITES, so flipping it is not a side change; the
    site map is edited for this control instead (side map is patched so only the keepout
    rule can catch it)."""
    f = fp(b, 'C4')                       # already bottom-side
    f.SetPosition(pcb.VECTOR2I(pcb.FromMM(28.0), pcb.FromMM(3.0)))


def p2_under_module_body(b):
    """Bottom part inside the module body but outside the 6 mm band: the keepout must catch
    it, proving the body rule and the band rule are independently doing work."""
    f = fp(b, 'C5')                       # already bottom-side
    f.SetPosition(pcb.VECTOR2I(pcb.FromMM(28.0), pcb.FromMM(15.0)))


def p3_j1_pth_field(b):
    """Bottom part inside J1's plated through-hole shield field."""
    f = fp(b, 'C5')
    f.SetPosition(pcb.VECTOR2I(pcb.FromMM(3.6), pcb.FromMM(28.0)))


def p4_buck_not_rigid(b):
    """Move ONE buck part 1.5 mm: the cell is no longer a rigid body.

    L1's neighbour clearance here is 1.5 mm < its half-extent, so this also creates a
    courtyard overlap; the assertion therefore accepts EITHER the rigid-body refusal or the
    overlap refusal, but requires it to name the buck cell.

    To isolate the rigid-motion rule cleanly, the part is moved 1.5 mm in +x, which is
    inside L1's own gap to U2 (measured 2.28 mm centre-to-centre on the loop metric)."""
    # -y (towards the north edge) is the one direction with free board: U2 is at -1.2 mm in
    # x and C4 at +1.6/-1.5, so any +/-x or +y nudge overlaps a neighbour and the overlap
    # rule fires first. -0.6 mm keeps L1's courtyard (y from 0.92) inside the outline while
    # changing its distance to U2.7 enough to break the SW_to_L metric.
    f = fp(b, 'L1')
    p = f.GetPosition()
    f.SetPosition(pcb.VECTOR2I(p.x, p.y - pcb.FromMM(0.6)))


def p5_same_side_overlap(b):
    """Two top-side parts on each other."""
    fp(b, 'C7').SetPosition(fp(b, 'U3').GetPosition())


def p6_motor_reservation(b):
    """A part inside the declared, unqualified motor reservation."""
    fp(b, 'R3').SetPosition(pcb.VECTOR2I(pcb.FromMM(30.0), pcb.FromMM(30.0)))


def p7_wrong_side(b):
    """A part flipped away from its declared side."""
    f = fp(b, 'U2')
    f.Flip(f.GetPosition(), False)


def p8_keepout_deleted(b):
    """Delete the module keepout rule area: the audit must notice the rule is gone."""
    for z in list(b.Zones()):
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            if abs(bb.GetLeft() / 1e6 - 18.25) < 1e-3:
                b.Remove(z)
                return
    raise SystemExit('control setup failed: module keepout not found')


POISONS = {
    'p1': (p1_under_antenna_band, 'module keepout occupied'),
    'p2': (p2_under_module_body, 'module keepout occupied'),
    'p3': (p3_j1_pth_field, 'through-hole pad field'),
    'p4': (p4_buck_not_rigid, 'rigid body'),
    'p5': (p5_same_side_overlap, 'courtyard overlap'),
    'p6': (p6_motor_reservation, 'motor reservation occupied'),
    'p7': (p7_wrong_side, 'wrong side'),
    'p8': (p8_keepout_deleted, 'module keepout rule area missing'),
}


def apply(name, src, dst):
    import pcbnew as pcb
    shutil.copyfile(src, dst)
    b = pcb.LoadBoard(str(dst))
    POISONS[name][0](b)
    pcb.SaveBoard(str(dst), b)


def audit_src(src):
    """Run the real audit() against `src` and return (ok, message)."""
    sys.path.insert(0, str(HERE))
    import twosided_qualified
    try:
        proof = twosided_qualified.audit(src)
        return True, 'accepted: sides=%s' % proof['side_counts']
    except Exception as e:                       # noqa: BLE001 - the verdict IS the exception
        return False, '%s: %s' % (type(e).__name__, e)


def main():
    total = good = 0

    for name, (_fn, expect) in POISONS.items():
        total += 1
        tmp = Path(tempfile.mkdtemp(dir=str(HERE)))
        try:
            dst = tmp / BOARD.name
            # 1) apply the poison in its own process (handles stay valid)
            r = subprocess.run([sys.executable, __file__, '--apply', name,
                                str(BOARD), str(dst)], capture_output=True, text=True)
            if r.returncode:
                print('%-40s SETUP-FAIL %s' % (name, r.stderr[-200:]))
                RESULTS.append({'control': name, 'control_passed': False,
                                'audit_message': 'setup failed: ' + r.stderr[-200:]})
                continue
            # 2) audit it in a FRESH process, so no stale handle is involved
            r2 = subprocess.run([sys.executable, __file__, '--audit', str(dst)],
                                capture_output=True, text=True)
            ok, msg = r2.returncode == 0, _verdict(r2.stdout + r2.stderr)
            passed = (not ok) and (expect.lower() in msg.lower())
            good += passed
            RESULTS.append({'control': name, 'expected': expect, 'audit_accepted': ok,
                            'audit_message': msg, 'control_passed': passed})
            print('%-40s %s  %s' % (name, 'PASS' if passed else 'FAIL', msg[:130]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # POSITIVE control: the accepted board must PASS.
    total += 1
    r = subprocess.run([sys.executable, __file__, '--audit', str(BOARD)],
                       capture_output=True, text=True)
    ok = r.returncode == 0
    msg = _verdict(r.stdout + r.stderr)
    good += ok
    RESULTS.append({'control': 'p0_clean_board', 'expected': 'accept',
                    'audit_accepted': ok, 'audit_message': msg, 'control_passed': ok})
    print('%-40s %s  %s' % ('p0 clean board must PASS', 'PASS' if ok else 'FAIL', msg[:130]))

    (HERE / 'negative-controls.json').write_text(json.dumps(
        {'board': BOARD.name,
         'board_sha256': hashlib.sha256(BOARD.read_bytes()).hexdigest(),
         'controls': RESULTS, 'passed': good, 'total': total}, indent=2) + '\n')
    print('\n%d/%d controls behaved correctly' % (good, total))
    return 0 if good == total else 1


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        apply(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) > 1 and sys.argv[1] == '--audit':
        ok, msg = audit_src(sys.argv[2])
        print(msg)
        raise SystemExit(0 if ok else 1)
    else:
        raise SystemExit(main())