#!/usr/bin/env python3
"""Panel arithmetic for the wing interconnect, derived from measured board geometry.

The question this answers: to reach JLCPCB's **Standard PCBA minimum of
70 x 70 mm**, how must a 34.6 x 20.0 mm board be panelised, and how many fit?

Every input is either measured from the board file or quoted from a JLCPCB page;
nothing is guessed.  Sources for the quoted rules are in
`docs/fab/wing-order/PANELIZATION.md` §Sources.

    /usr/bin/python3 tools/wing_panel_arithmetic.py

Exit 0 always (this is an arithmetic report, not a gate).
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, '..', 'tracker', 'hardware'))

# ---------------------------------------------------------------------------
# MEASURED from tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb
# (Edge.Cuts centreline; see tracker/hardware/measure_wing_interconnect.py)
BOARD_W = 34.6      # mm, Edge.Cuts centreline X extent
BOARD_H = 20.0      # mm, Edge.Cuts centreline Y extent
AREA_MM2 = BOARD_W * BOARD_H

# QUOTED: JLCPCB Standard PCBA single-PCB minimum is 70 x 70 mm; panel maximum
# 250 x 250 mm (recommended).  Rails 5-8 mm (use 5); board-to-board spacing for
# mouse-bite panels 1.6-2.0 mm (use 2.0).
MIN_ASSEMBLY = 70.0
MAX_PANEL = 250.0
RAIL = 5.0
GAP = 2.0


def panel_size(nx, ny, rail=RAIL, gap=GAP):
    w = 2 * rail + nx * BOARD_W + (nx - 1) * gap
    h = 2 * rail + ny * BOARD_H + (ny - 1) * gap
    return w, h


def main():
    print(f'board                     {BOARD_W} x {BOARD_H} mm  '
          f'({AREA_MM2:.2f} mm^2 = {AREA_MM2/100:.2f} cm^2)')
    print(f'assembly minimum          {MIN_ASSEMBLY} x {MIN_ASSEMBLY} mm (Standard PCBA, single PCB OR panel)')
    print(f'panel maximum             {MAX_PANEL} x {MAX_PANEL} mm (recommended)')
    print(f'assumed rail / gap        {RAIL} mm / {GAP} mm')
    print()
    print(f'{"grid":>6} {"n-up":>5} {"panel W":>9} {"panel H":>9} {">=70x70":>8} '
          f'{"<=250x250":>10} {"product cm2":>12} {"panel cm2":>10} {"utilisation":>12}')
    rows = []
    for ny in range(1, 13):
        for nx in range(1, 8):
            n = nx * ny
            w, h = panel_size(nx, ny)
            ok_min = w >= MIN_ASSEMBLY and h >= MIN_ASSEMBLY
            ok_max = w <= MAX_PANEL and h <= MAX_PANEL
            if not ok_min or not ok_max:
                continue
            prod = n * AREA_MM2 / 100
            pan = w * h / 100
            rows.append((n, w, h, prod, pan, prod / pan))
            print(f'{nx}x{ny:<4} {n:>5} {w:>9.1f} {h:>9.1f} {"yes":>8} {"yes":>10} '
                  f'{prod:>12.2f} {pan:>10.2f} {100*prod/pan:>11.1f}%')

    if rows:
        rows.sort(key=lambda r: (r[0], r[4]))
        n, w, h, prod, pan, util = rows[0]
        print(f'\nSMALLEST legal assembly panel: {n}-up at {w:.1f} x {h:.1f} mm '
              f'({100*util:.1f}% laminate utilisation)')
        print(f'  laminate per board: {pan/n:.2f} cm^2 vs {AREA_MM2/100:.2f} cm^2 as a '
              f'single board = {pan/n/(AREA_MM2/100):.2f}x')
        best = max(rows, key=lambda r: r[5])
        print(f'BEST utilisation: {best[0]}-up at {best[1]:.1f} x {best[2]:.1f} mm '
              f'({100*best[5]:.1f}%)')
    else:
        print('NO grid satisfies both the 70x70 minimum and the 250x250 maximum')

    print('\n--- V-cut is NOT an option, arithmetically moot ---')
    print('  V-cut min panel is also 70 x 70 mm, but JLCPCB: "V-cut is not supported')
    print('  for 0.4 mm board thickness" -> routed/mouse-bite tabs are the only route.')

    print('\n--- connectivity of the panel ---')
    print('  Edge.Cuts is 4 straight segments forming a closed rectangle: the outline')
    print('  carries NO castellation, NO notch and NO slot, so nothing in the board')
    print('  outline itself conflicts with a tab. The one feature that matters is')
    print('  J1 (the wing tab, SMD 4.0 x 1.2 pads, nearest copper 1.60 mm from the')
    print('  left edge) and SC3/D3 (1.60/1.65 mm from the right edge): depanel')
    print('  stress and burr land on the two edges that carry the board\'s function.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
