"""Find a MEASURED free position for the U_LORA1280 reference text.

The one remaining blocking silk violation is that footprint's reference text: bbox
(46.98,67.09)-(59.02,69.11), 12.04 x 2.02 mm, sitting straight across the part body over its
pad columns.

I already tried guessing (53.00,57.00) and it made things WORSE: silk 1 -> 4, because that
position collided with other silk. AGENTS.md 26 records the same failure class for trimming
(9 -> 12 violations). So: search, do not guess.

Method: candidate positions on a lattice across the board. For each, place the text and count
(a) silk-over-copper against every copper object, and (b) silk-over-silk against every other
silkscreen item. Accept only a position with ZERO of both, preferring one near the part and
inside the board. Report the best few, then verify the chosen one with check_silk.py.
"""
import json
import os
import shutil
import subprocess

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
REL = 'docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, REL, 'latest.kicad_pcb')
B = os.path.join(ROOT, REL, 'batches', 'SILKLORA2')
REF = 'U_LORA1280'
STEP = 250000          # 0.25 mm lattice
SIDE = ('kicad_pro', 'kicad_dru', 'fp-lib-table')


def copper_shapes(b):
    out = []
    for t in b.GetTracks():
        for l in (p.F_Cu, p.B_Cu):
            if t.IsOnLayer(l):
                out.append((t.GetEffectiveShape(l), 'copper'))
    for f in b.GetFootprints():
        for q in f.Pads():
            for l in (p.F_Cu, p.B_Cu):
                if q.IsOnLayer(l):
                    out.append((q.GetEffectiveShape(l), 'copper'))
    return out


def other_silk(b, skip_ref):
    """Every F.Silkscreen item except the reference text we are moving."""
    out = []
    for f in b.GetFootprints():
        for it in f.GraphicalItems():
            if it.GetLayer() == p.F_SilkS:
                out.append(it)
        if f.GetReference() != skip_ref and f.Reference().GetLayer() == p.F_SilkS:
            out.append(f.Reference())
    for d in b.GetDrawings():
        if d.GetLayer() == p.F_SilkS:
            out.append(d)
    return out


def main():
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in SIDE:
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    b = p.LoadBoard(src)

    rf = None
    for f in b.GetFootprints():
        if f.GetReference() == REF:
            rf = f.Reference()
            orig = rf.GetPosition()
            height = rf.GetTextHeight()
    if rf is None:
        print('reference not found')
        return 1
    # text extent relative to its own position
    bb0 = rf.GetBoundingBox()
    w = (bb0.GetRight() - bb0.GetLeft()) / 1e6
    h = (bb0.GetBottom() - bb0.GetTop()) / 1e6
    print('reference "%s" at (%.3f,%.3f)  extent %.2f x %.2f mm  height field %.3f'
          % (rf.GetText(), orig.x / 1e6, orig.y / 1e6, w, h, height / 1e6))

    outline = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline)
    obb = outline.BBox()

    cu = copper_shapes(b)
    silk = other_silk(b, REF)
    print('copper objects %d, other silk items %d' % (len(cu), len(silk)))

    cands = []
    x = obb.GetLeft() / 1e6 + 2.0
    while x < obb.GetRight() / 1e6 - 2.0:
        y = obb.GetTop() / 1e6 + 1.5
        while y < obb.GetBottom() / 1e6 - 1.5:
            # place and test
            rf.SetPosition(p.VECTOR2I(int(x * 1e6), int(y * 1e6)))
            tbb = rf.GetBoundingBox()
            # inside board?
            inside = (tbb.GetLeft() > obb.GetLeft() + 300000
                      and tbb.GetRight() < obb.GetRight() - 300000
                      and tbb.GetTop() > obb.GetTop() + 300000
                      and tbb.GetBottom() < obb.GetBottom() - 300000)
            if not inside:
                y += STEP / 1e6
                continue
            tshape = p.SHAPE_RECT(p.VECTOR2I(tbb.GetLeft(), tbb.GetTop()),
                                  p.VECTOR2I(tbb.GetRight(), tbb.GetBottom()))
            cu_hits = sum(1 for (s, _) in cu if p.SHAPE.Collide(tshape, s, 100000))
            silk_hits = 0
            for it in silk:
                try:
                    if p.SHAPE.Collide(tshape, it.GetEffectiveShape(), 100000):
                        silk_hits += 1
                except Exception:
                    pass
            if cu_hits == 0 and silk_hits == 0:
                d = ((x - orig.x / 1e6) ** 2 + (y - orig.y / 1e6) ** 2) ** 0.5
                cands.append((d, x, y))
            y += STEP / 1e6
        x += STEP / 1e6

    cands.sort()
    print('\nfree positions found: %d' % len(cands))
    for (d, x, y) in cands[:8]:
        print('   (%.2f, %.2f)  %.2f mm from original' % (x, y, d))
    if not cands:
        print('NO free position at this lattice -- report, do not force')
        rf.SetPosition(orig)
        return 1

    d, bx, by = cands[0]
    rf.SetPosition(p.VECTOR2I(int(bx * 1e6), int(by * 1e6)))
    print('\nchosen: (%.2f, %.2f)  %.2f mm from original' % (bx, by, d))

    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    del b
    for ext in SIDE:
        s = src.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, out.replace('.kicad_pcb', '.' + ext))

    print('\n--- check_silk on candidate ---')
    r = subprocess.run(['/usr/bin/python3', '-B', 'tracker/hardware/check_silk.py',
                        '--board', out], cwd=ROOT, capture_output=True, text=True, timeout=900)
    out_txt = (r.stdout or '') + (r.stderr or '')
    for ln in out_txt.splitlines():
        if 'SILK:' in ln or 'FAIL' in ln:
            print('   ', ln.strip()[:120])
    json.dump({'chosen': [bx, by], 'orig': [orig.x / 1e6, orig.y / 1e6],
               'candidates': [[x, y] for (_, x, y) in cands[:20]]},
              open(os.path.join(B, 'report.json'), 'w'), indent=2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
