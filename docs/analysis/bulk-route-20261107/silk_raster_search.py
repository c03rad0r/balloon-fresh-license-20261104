"""Find free space for the U_LORA1280 reference text by raster occupancy, not by guessing.

Status: the reference text is 12.05 x 2.01 mm at its current 1.27 mm height and 7.76 x 1.46 mm
at the 0.80 mm JLCPCB minimum. Every position tried by hand still overlapped copper, because
point-testing 2492 copper objects and 532 silk items per candidate is slow AND I was guessing
positions rather than searching.

Method here: rasterise copper and silk onto a 0.10 mm grid once, then slide the text footprint
over the grid as a max-filter. Any cell where the window contains zero occupied cells is a
legal position. That is O(board_area) instead of O(positions x objects), and it finds the
genuinely free rectangles instead of the ones I happen to think of.

Reports the best few free positions, preferring ones near the part, and writes the chosen
candidate. Verifies with check_silk.py.
"""
import json
import os
import shutil
import subprocess

import numpy as np
import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
REL = 'docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, REL, 'latest.kicad_pcb')
B = os.path.join(ROOT, REL, 'batches', 'SILKRASTER')
REF = 'U_LORA1280'
GRID = 100000          # 0.10 mm in nm
SIDE = ('kicad_pro', 'kicad_dru', 'fp-lib-table')


def raster(board, outline):
    bb = outline.BBox()
    x0, y0 = bb.GetLeft(), bb.GetTop()
    w = int((bb.GetRight() - bb.GetLeft()) // GRID) + 2
    h = int((bb.GetBottom() - bb.GetTop()) // GRID) + 2
    occ = np.zeros((h, w), dtype=bool)

    def stamp(shape, grow=GRID):
        sbb = shape.BBox()
        l = int((sbb.GetLeft() - x0) // GRID) - 1
        r = int((sbb.GetRight() - x0) // GRID) + 1
        t = int((sbb.GetTop() - y0) // GRID) - 1
        b = int((sbb.GetBottom() - y0) // GRID) + 1
        l, t = max(l, 0), max(t, 0)
        r, b = min(r, w - 1), min(b, h - 1)
        if r >= l and b >= t:
            occ[t:b + 1, l:r + 1] = True

    for t in board.GetTracks():
        for l in (p.F_Cu, p.B_Cu):
            if t.IsOnLayer(l):
                stamp(t.GetEffectiveShape(l))
    for f in board.GetFootprints():
        for q in f.Pads():
            for l in (p.F_Cu, p.B_Cu):
                if q.IsOnLayer(l):
                    stamp(q.GetEffectiveShape(l))
        for it in f.GraphicalItems():
            if it.GetLayer() == p.F_SilkS:
                try:
                    stamp(it.GetEffectiveShape())
                except Exception:
                    stamp_bb = it.GetBoundingBox()
                    l = max(int((stamp_bb.GetLeft() - x0) // GRID) - 1, 0)
                    r = min(int((stamp_bb.GetRight() - x0) // GRID) + 1, w - 1)
                    t = max(int((stamp_bb.GetTop() - y0) // GRID) - 1, 0)
                    b = min(int((stamp_bb.GetBottom() - y0) // GRID) + 1, h - 1)
                    if r >= l and b >= t:
                        occ[t:b + 1, l:r + 1] = True
        if f.GetReference() != REF and f.Reference().GetLayer() == p.F_SilkS:
            rb = f.Reference().GetBoundingBox()
            l = max(int((rb.GetLeft() - x0) // GRID) - 1, 0)
            r = min(int((rb.GetRight() - x0) // GRID) + 1, w - 1)
            t = max(int((rb.GetTop() - y0) // GRID) - 1, 0)
            b = min(int((rb.GetBottom() - y0) // GRID) + 1, h - 1)
            if r >= l and b >= t:
                occ[t:b + 1, l:r + 1] = True
    for d in board.GetDrawings():
        if d.GetLayer() == p.F_SilkS:
            db = d.GetBoundingBox()
            l = max(int((db.GetLeft() - x0) // GRID) - 1, 0)
            r = min(int((db.GetRight() - x0) // GRID) + 1, w - 1)
            t = max(int((db.GetTop() - y0) // GRID) - 1, 0)
            b = min(int((db.GetBottom() - y0) // GRID) + 1, h - 1)
            if r >= l and b >= t:
                occ[t:b + 1, l:r + 1] = True
    return occ, x0, y0, w, h


def main():
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    shutil.copy(LIVE, src)
    for ext in SIDE:
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, src.replace('.kicad_pcb', '.' + ext))

    b = p.LoadBoard(src)
    outline = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline)

    rf = None
    for f in b.GetFootprints():
        if f.GetReference() == REF:
            rf = f.Reference()
            orig = rf.GetPosition()
    rf.SetTextHeight(800000)
    rf.SetTextWidth(800000)
    rf.SetTextThickness(150000)
    tb = rf.GetBoundingBox()
    tw = int((tb.GetRight() - tb.GetLeft()) // GRID) + 1
    th = int((tb.GetBottom() - tb.GetTop()) // GRID) + 1
    print('text extent at 0.80 mm: %d x %d cells (%.2f x %.2f mm)'
          % (tw, th, tw * GRID / 1e6, th * GRID / 1e6))

    occ, x0, y0, w, h = raster(b, outline)
    print('raster %d x %d cells, occupied %d' % (w, h, int(occ.sum())))

    # max-filter: a window is free if it contains no occupied cell
    from numpy.lib.stride_tricks import sliding_window_view
    if tw >= w or th >= h:
        print('text larger than board')
        return 1
    win = sliding_window_view(occ, (th, tw))
    free = ~win.any(axis=(2, 3))
    ys, xs = np.where(free)
    print('free positions: %d' % len(xs))
    if len(xs) == 0:
        print('NO free position for this text size -- report, do not force')
        return 1

    # prefer near the part, and inside the board with margin
    ox, oy = orig.x, orig.y
    cand = []
    for yy, xx in zip(ys, xs):
        cx = x0 + (xx + tw // 2) * GRID
        cy = y0 + (yy + th // 2) * GRID
        d = ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5
        cand.append((d, cx, cy))
    cand.sort()
    print('nearest free positions to the original:')
    for (d, cx, cy) in cand[:6]:
        print('   (%.2f, %.2f)  %.2f mm away' % (cx / 1e6, cy / 1e6, d / 1e6))

    d, cx, cy = cand[0]
    rf.SetPosition(p.VECTOR2I(int(cx), int(cy)))
    print('\nchosen (%.2f, %.2f)' % (cx / 1e6, cy / 1e6))

    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    del b
    for ext in SIDE:
        s = src.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, out.replace('.kicad_pcb', '.' + ext))

    print('\n--- check_silk ---')
    r = subprocess.run(['/usr/bin/python3', '-B', 'tracker/hardware/check_silk.py',
                        '--board', out], cwd=ROOT, capture_output=True, text=True, timeout=900)
    for ln in ((r.stdout or '') + (r.stderr or '')).splitlines():
        if 'SILK:' in ln or 'FAIL' in ln:
            print('   ', ln.strip()[:120])
    json.dump({'chosen': [cx / 1e6, cy / 1e6], 'free_count': len(xs)},
              open(os.path.join(B, 'report.json'), 'w'), indent=2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
