#!/usr/bin/env python3
"""check_order_files.py -- do the BOM and CPL agree, and does the CPL match the board?

JLC rejects or silently mis-places when these disagree:

  BOM designators <-> CPL designators   both must describe the SAME parts
  CPL designators <-> board footprints  every placed part, minus explicit DNP
  CPL coordinates <-> board positions   after applying the required axis convention

THE Y-AXIS CONVENTION, WHICH MY FIRST VERSION OF THIS CHECK GOT WRONG
--------------------------------------------------------------------
Measured on this board: every CPL row satisfies `y_cpl = 80.10 - y_board`. The CPL is Y-FLIPPED
relative to `pcbnew.GetPosition()`, and that flip is REQUIRED, not a defect -- pcbnew returns Y
increasing DOWNWARD from a top-left origin, while a fabrication position file uses Y increasing
UPWARD from the bottom-left.

The first version compared the two systems directly and reported an 80 mm error on every single
part. It would have condemned a correct file -- and worse, it reported J_W2/J_W4 as "Y swapped"
when the board itself simply differs from the file by the required flip. So this now applies the
flip and reports the RESIDUAL, which is the only number that means anything.

HAND-FIT PARTS MUST NOT BE IN THE CPL
------------------------------------
A part in the CPL but not the BOM is a part the assembler is told to place and was never told to
buy. Measured: six such rows (J_W1-4, U3, U_LORA1280) -- the wing sockets and the NiceRF modules,
bought elsewhere and soldered by hand. They must be in NEITHER file.

Usage:
  check_order_files.py <board.kicad_pcb> <bom.csv> <cpl.csv> [--dnp ref,...] [--height 80.0]
"""
import argparse
import csv
import sys

import pcbnew

MM = 1e6
TOL_MM = 0.05          # placement tolerance accepted in the check


def read_designators(path, column):
    out = set()
    with open(path, newline='') as fh:
        for row in csv.DictReader(fh):
            cell = row.get(column, '') or ''
            for d in cell.replace('"', '').split(','):
                d = d.strip()
                if d:
                    out.add(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('board')
    ap.add_argument('bom')
    ap.add_argument('cpl')
    ap.add_argument('--dnp', default='')
    ap.add_argument('--hand-fit', default='',
                    help='refs soldered by hand, bought elsewhere: excluded from BOTH files')
    ap.add_argument('--height', type=float, default=None,
                    help='board Y height for the flip; measured from Edge.Cuts if omitted')
    args = ap.parse_args()

    dnp = {d.strip() for d in args.dnp.split(',') if d.strip()}
    hand = {d.strip() for d in args.hand_fit.split(',') if d.strip()}
    b = pcbnew.LoadBoard(args.board)

    if args.height is None:
        ys = []
        for d in b.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts and d.GetClass() == 'PCB_SHAPE':
                ys += [d.GetStart().y / MM, d.GetEnd().y / MM]
        H = max(ys) - min(ys)
    else:
        H = args.height

    board_all = {fp.GetReference() for fp in b.GetFootprints()}
    board_fitted = {fp.GetReference() for fp in b.GetFootprints()
                    if not (fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_BOM)}
    pos = {fp.GetReference(): (fp.GetPosition().x / MM, fp.GetPosition().y / MM)
           for fp in b.GetFootprints()}

    bom = read_designators(args.bom, 'Designator')
    cpl = read_designators(args.cpl, 'Designator')

    ok = True
    print(f'board Y extent (flip height) : {H:.2f} mm')
    print(f'board footprints             : {len(board_all)}')
    print(f'board fitted (not excl-BOM)  : {len(board_fitted)}')
    print(f'BOM designators              : {len(bom)}')
    print(f'CPL designators              : {len(cpl)}')

    only_bom = bom - cpl
    only_cpl = cpl - bom
    print('\nBOM vs CPL')
    if only_bom:
        ok = False
        print(f'  ONLY IN BOM (ordered, never placed): {sorted(only_bom)}')
    if only_cpl:
        ok = False
        print(f'  ONLY IN CPL (placed, never ordered): {sorted(only_cpl)}')
    if not only_bom and not only_cpl:
        print('  identical sets — OK')

    print('\nCPL vs board fitted, excluding declared DNP')
    expected = board_fitted - dnp - hand
    if hand & cpl:
        ok = False
        print(f'  HAND-FIT BUT IN CPL (JLC cannot buy it): {sorted(hand & cpl)}')
    if hand & bom:
        ok = False
        print(f'  HAND-FIT BUT IN BOM (JLC has no LCSC for it): {sorted(hand & bom)}')
    miss = expected - cpl
    extra = cpl - board_all
    if dnp & cpl:
        ok = False
        print(f'  DECLARED DNP BUT STILL IN CPL: {sorted(dnp & cpl)}')
    if miss:
        ok = False
        print(f'  FITTED ON BOARD, MISSING FROM CPL: {sorted(miss)}')
    if extra:
        ok = False
        print(f'  IN CPL, NOT ON BOARD: {sorted(extra)}')
    if not miss and not extra and not (dnp & cpl):
        print('  every fitted part placed, no DNP placed — OK')

    print(f'\nCPL coordinates vs board positions, after Y flip (y -> {H:.2f} - y)')
    worst, worst_ref, offs = 0.0, None, []
    with open(args.cpl, newline='') as fh:
        for row in csv.DictReader(fh):
            ref = (row.get('Designator') or '').strip()
            if ref not in pos:
                continue
            try:
                x = float(row.get('Mid X'))
                y = float(row.get('Mid Y'))
            except (TypeError, ValueError):
                ok = False
                print(f'  {ref}: unparseable coordinates')
                continue
            bx, by = pos[ref]
            ey = H - by
            d = max(abs(bx - x), abs(ey - y))
            offs.append(d)
            if d > worst:
                worst, worst_ref = d, ref
    if offs:
        mean = sum(offs) / len(offs)
        print(f'  worst deviation: {worst:.4f} mm ({worst_ref})')
        print(f'  mean  deviation: {mean:.4f} mm over {len(offs)} rows')
        if worst > TOL_MM:
            ok = False
            print(f'  EXCEEDS {TOL_MM} mm')
        else:
            print(f'  within {TOL_MM} mm — OK')

    print('\nVERDICT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
