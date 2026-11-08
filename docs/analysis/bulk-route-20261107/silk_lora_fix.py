"""Fix U_LORA1280's silk-over-copper by moving body silk to F.Fab (AGENTS.md 26).

Measured: the footprint's silk box runs x 45.000-61.000, y 60.100-76.100 at 0.150 mm width.
Its pads are 2.00 x 1.20 with centres at x 45.850 and x 60.150, so their edges reach x 44.850
and x 61.150 -- outside the silk box's own edges. The two vertical silk segments therefore lie
across pads 1-8 and 9-16.

AGENTS.md 26 permits: move REFERENCE TEXT, and move silk GRAPHICS to the Fab layer. It forbids
touching pads, tracks, vias, zones, courtyards, the outline, or connectivity. It also records
that TRIMMING made things worse (9 -> 12 violations), so moving to Fab is the documented fix.

This does exactly that for the two offending vertical segments, writes a candidate, and runs
BOTH silk gates plus the DRC gate so the result is judged the same way the repo judges it.
Nothing is adopted here.
"""
import json
import os
import shutil
import subprocess

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
REL = 'docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, REL, 'latest.kicad_pcb')
B = os.path.join(ROOT, REL, 'batches', 'SILKLORA')
SIDE = ('kicad_pro', 'kicad_dru', 'fp-lib-table')


def run(cmd, timeout=900):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def silk_count(board):
    rc, out = run(['/usr/bin/python3', '-B', 'tracker/hardware/check_silk.py',
                   '--board', board])
    lines = [l for l in out.splitlines() if 'SILK:' in l or 'FAIL' in l]
    return rc, lines[:6]


def main():
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in SIDE:
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    print('BEFORE:')
    print('  ', silk_count(src))

    b = p.LoadBoard(src)
    moved = []
    for f in b.GetFootprints():
        if f.GetReference() != 'U_LORA1280':
            continue
        for it in list(f.GraphicalItems()):
            if it.GetLayer() != p.F_SilkS:
                continue
            if not isinstance(it, p.PCB_SHAPE):
                continue
            try:
                s, e = it.GetStart(), it.GetEnd()
            except Exception:
                continue
            # the two VERTICAL segments (constant x) are the ones crossing the pad columns
            if abs(s.x - e.x) <= 1000 and abs(s.y - e.y) > 1000000:
                it.SetLayer(p.F_Fab)
                moved.append(('vertical', s.x / 1e6, s.y / 1e6, e.y / 1e6))
    print('\nmoved %d vertical silk segment(s) to F.Fab: %s' % (len(moved), moved))
    if not moved:
        print('nothing moved -- no vertical silk segments found')
        return 1

    out = os.path.join(B, 'routed.kicad_pcb')
    # The reference text at (53.00,57.00) made things WORSE (silk 1 -> 4: it collided with
    # other silk there). AGENTS.md 26 records the same class of mistake with trimming
    # (9 -> 12 violations). Reverted: leave the reference where it is and keep only the
    # Fab-layer move, which measured 3 -> 1.
    p.SaveBoard(out, b)
    del b
    for ext in SIDE:
        s = src.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, out.replace('.kicad_pcb', '.' + ext))

    print('\nAFTER:')
    print('  ', silk_count(out))

    print('\n--- DRC gate on candidate ---')
    rc, o = run(['/usr/bin/python3', '-B', 'tracker/hardware/check_drc.py',
                 '--board', out, '--json'])
    i = o.find('{')
    print(o[i:i + 500] if i >= 0 else o[-500:])
    json.dump({'moved': moved}, open(os.path.join(B, 'report.json'), 'w'), indent=2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
