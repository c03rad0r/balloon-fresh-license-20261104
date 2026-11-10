#!/usr/bin/env python3
"""Smallest-outline comparison: 80x60 baseline vs 65x50 single-sided vs two-sided.

Reports, with a denominator for every number:
  * board area and part counts per side
  * courtyard area PER SIDE, clipped to the outline
  * occupancy per side (clipped / own board area)
  * area held by each declared reservation
  * the smallest axis-aligned empty rectangle outside intended reservations

The single-sided 65x50 column is read from the UNMERGED candidate branch, so it is compared,
not modified. It is never a write target.
"""
import json
import subprocess
import sys
from pathlib import Path

import pcbnew as pcb
from shapely.geometry import LineString, box
from shapely.ops import polygonize, unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def crt(f):
    want = pcb.F_CrtYd if f.GetLayer() == pcb.F_Cu else pcb.B_CrtYd
    lines, rects = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() != want or not hasattr(g, 'GetShapeStr'):
            continue
        a, e = g.GetStart(), g.GetEnd()
        if g.GetShapeStr() == 'Rect':
            rects.append(box(a.x / 1e6, a.y / 1e6, e.x / 1e6, e.y / 1e6))
        else:
            lines.append(LineString([(a.x / 1e6, a.y / 1e6), (e.x / 1e6, e.y / 1e6)]))
    return unary_union(rects + list(polygonize(lines)))


def largest_empty_rect(blockers, x0, y0, x1, y1, step=0.25, exclude=None):
    """Largest axis-aligned all-free rectangle on a `step` grid.

    Uses the maximal-rectangle (histogram) algorithm -- O(W*H) -- after rasterising the
    blockers once. An earlier version tried every pair of free cells, which is O(n^4): on a
    52 x 46 board at 0.25 mm that is ~38k cells and it did not finish in 180 s, so the
    measurement never completed and would have been reported from a timeout. Each grid cell
    is tested as blocked if its CENTRE lies inside any blocker polygon, which is the honest
    reading of "the parts occupy this cell" at this grid pitch.

    `exclude` marks cells that are unavailable but are NOT part of the free area (a declared
    reservation that must stay empty), so the reported rectangle is genuinely routable space.
    """
    nx = int(round((x1 - x0) / step))
    ny = int(round((y1 - y0) / step))
    grid = [[1] * nx for _ in range(ny)]
    boxes = [b for b in blockers]
    if exclude is not None:
        boxes = boxes + [exclude]
    for j in range(ny):
        cy = y0 + (j + 0.5) * step
        for i in range(nx):
            cx = x0 + (i + 0.5) * step
            pt = box(cx - 1e-9, cy - 1e-9, cx + 1e-9, cy + 1e-9)
            for b in boxes:
                if b.intersects(pt):
                    grid[j][i] = 0
                    break
    best_area, best_geom = 0.0, None
    heights = [0] * nx
    for j in range(ny):
        for i in range(nx):
            heights[i] = heights[i] + 1 if grid[j][i] else 0
        # largest rectangle in histogram
        stack = []
        for i in range(nx + 1):
            h = heights[i] if i < nx else 0
            start = i
            while stack and stack[-1][1] > h:
                idx, hh = stack.pop()
                width = i - idx
                area = hh * width * step * step
                if area > best_area:
                    best_area = area
                    best_geom = (round(x0 + idx * step, 2),
                                 round(y0 + (j - hh + 1) * step, 2),
                                 round(width * step, 2), round(hh * step, 2))
                start = idx
            stack.append((start, h))
    return round(best_area, 1), best_geom


def measure(path, w, h, label, motor=None, module_keepout=None, source_note=None):
    b = pcb.LoadBoard(str(path))
    fps = list(b.GetFootprints())
    polys = {f.GetReference(): crt(f) for f in fps}
    sides = {f.GetReference(): ('top' if f.GetLayer() == pcb.F_Cu else 'bottom') for f in fps}
    outline = box(0, 0, w, h)

    def clip(side):
        return round(sum(polys[r].intersection(outline).area
                         for r in polys if sides[r] == side), 3)

    top_clip, bot_clip = clip('top'), clip('bottom')
    area = w * h
    row = {
        'label': label,
        'path': str(path),
        'board_mm': [w, h],
        'board_area_mm2': area,
        'source': source_note,
        'top_parts': sum(1 for r in sides if sides[r] == 'top'),
        'bottom_parts': sum(1 for r in sides if sides[r] == 'bottom'),
        'courtyard_top_total_mm2': round(sum(polys[r].area for r in polys if sides[r] == 'top'), 3),
        'courtyard_bottom_total_mm2': round(sum(polys[r].area for r in polys if sides[r] == 'bottom'), 3),
        'courtyard_top_clipped_mm2': top_clip,
        'courtyard_bottom_clipped_mm2': bot_clip,
        'occupancy_top_percent': round(top_clip / area * 100, 2),
        'occupancy_bottom_percent': round(bot_clip / area * 100, 2),
        'occupancy_both_percent': round((top_clip + bot_clip) / area * 100, 2),
        'occupancy_denominator': '%g x %g = %g mm2, per side; courtyards clipped to outline'
                                 % (w, h, area),
        'per_side_max_occupancy_percent': round(max(top_clip, bot_clip) / area * 100, 2),
    }
    reservations = {}
    if motor:
        # measured from the box actually used, not a hardcoded 720
        reservations['motor_30x24'] = round(box(*motor).intersection(outline).area, 3)
    if module_keepout:
        reservations['module_keepout'] = round(
            box(*module_keepout).intersection(outline).area, 3)
    row['reservations_mm2'] = reservations
    row['reservations_total_mm2'] = round(sum(reservations.values()), 3)
    row['reservations_percent_of_board'] = round(sum(reservations.values()) / area * 100, 2)

    blockers = list(polys.values())
    if module_keepout:
        blockers.append(box(*module_keepout))
    biggest, where = largest_empty_rect(
        blockers, 0, 0, w, h, 0.25,
        exclude=box(*motor) if motor else None)
    row['largest_empty_rect_outside_reservations_mm2'] = biggest
    row['largest_empty_rect_outside_reservations_at'] = where
    row['largest_empty_rect_grid_mm'] = 0.25
    return row


# The SAME module-body keepout rectangle is applied to every row. U1 is the same footprint
# at the same position (28.00, 6.75) on all three boards, so its courtyards are identical and
# the reservation is directly comparable. Applying it to only one row would make the
# "largest empty rectangle" column apples-to-oranges.
MODULE_KEEPOUT = (18.25, -21.0, 37.75, 20.2)


def main():
    import tempfile
    # Stable scratch location OUTSIDE the repo: a mkdtemp inside HERE left a transient
    # path in the committed JSON (`.../tmpc5whyflv/compact.kicad_pcb`) that does not exist
    # for any reader of the committed table.
    scratch = Path.home() / '.hermes/profiles/manager/cache/scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    tmp = scratch

    # baseline 80x60 from master
    src = ROOT / 'placement' / 'core-placement.kicad_pcb'
    base = measure(src, 80, 60, '80 x 60 baseline (master, all top)',
                   motor=(48, 34, 78, 58), module_keepout=MODULE_KEEPOUT,
                   source_note='placement/core-placement.kicad_pcb @ 04219c23')

    # 65x50 single-sided from the unmerged candidate branch (read-only, via git show)
    single_path = tmp / 'compact-12d063cf.kicad_pcb'
    # ROOT is .../pressure-controller-core; the worktree root is 3 levels up. Deriving it as
    # parents[4] landed in ~/worktrees, where `git show` fails silently and the single-sided
    # column came out empty -- a comparison table missing its middle column.
    worktree = ROOT.parents[2]
    r = subprocess.run(['git', '-C', str(worktree), 'show',
                        '12d063cf:tracker/hardware/pressure-controller-core/compact/compact.kicad_pcb'],
                       capture_output=True)
    if r.returncode == 0:
        single_path.write_bytes(r.stdout)
        single = measure(single_path, 65, 50, '65 x 50 single-sided (unmerged candidate)',
                         motor=(33, 24, 63, 48), module_keepout=MODULE_KEEPOUT,
                         source_note='compact/compact.kicad_pcb @ 12d063cf (branch '
                                     'pr-pressure-compact-placement, NOT on master)')
    else:
        single = {'label': '65 x 50 single-sided', 'error': 'could not read 12d063cf',
                  'stderr': r.stderr.decode()[:300]}

    # two-sided candidate
    two = measure(HERE / 'twosided-qualified.kicad_pcb', 52, 46,
                  '52 x 46 two-sided (this candidate)',
                  motor=(22, 22, 52, 46), module_keepout=MODULE_KEEPOUT,
                  source_note='twosided-qualified/twosided-qualified.kicad_pcb')

    rows = [base, single, two]
    out = {'rows': rows, 'grid_step_mm': 0.25}

    # size deltas, computed from the measured areas (not from the nominal numbers)
    ab = base['board_area_mm2']
    for r in rows:
        if 'board_area_mm2' in r:
            r['delta_vs_80x60_percent'] = round((r['board_area_mm2'] - ab) / ab * 100, 2)
    if 'board_area_mm2' in single and 'board_area_mm2' in two:
        out['two_vs_single_percent'] = round(
            (two['board_area_mm2'] - single['board_area_mm2'])
            / single['board_area_mm2'] * 100, 2)
        out['two_vs_single_mm2'] = two['board_area_mm2'] - single['board_area_mm2']
    (HERE / 'outline-comparison.json').write_text(json.dumps(out, indent=2) + '\n')

    hdr = ('| metric | 80x60 baseline | 65x50 single-sided | 52x46 two-sided |')
    print(hdr)
    print('|---|---|---|---|')
    for k in ('board_mm', 'board_area_mm2', 'top_parts', 'bottom_parts',
              'courtyard_top_clipped_mm2', 'courtyard_bottom_clipped_mm2',
              'occupancy_top_percent', 'occupancy_bottom_percent',
              'per_side_max_occupancy_percent', 'reservations_total_mm2',
              'reservations_percent_of_board',
              'largest_empty_rect_outside_reservations_mm2', 'delta_vs_80x60_percent'):
        vals = []
        for r in rows:
            v = r.get(k, '-')
            vals.append(str(v))
        print('| %s | %s |' % (k, ' | '.join(vals)))
    print()
    print('two-sided vs single-sided: %s mm2 (%s %%)' % (
        out.get('two_vs_single_mm2'), out.get('two_vs_single_percent')))
    print(json.dumps(out, indent=2))
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
