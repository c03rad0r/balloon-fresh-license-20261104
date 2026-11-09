#!/usr/bin/env python3
"""set_assembly_attributes.py -- make the BOARD agree with the assembly plan.

WHY THIS EXISTS
---------------
Measured on the board of record: U_C has attrs=2, i.e. DNP=False, EXCLUDE_FROM_BOM=False,
EXCLUDE_FROM_POS_FILES=False. It is fully FITTED at board level while the documents, the BOM, the
CPL and the hand-fit list all say it is dropped. The artefact and the paperwork disagreed, and the
paperwork was the only place the decision lived.

That is the failure mode this repo has recorded repeatedly: two records asserting different values
with nothing surfacing it. Here one record was a FILE and the other was the BINARY that actually
gets fabricated. A hand-maintained excluded list can always drift from the board; attributes
cannot, because they travel with the object.

TWO DIFFERENT CLAIMS, TWO DIFFERENT ATTRIBUTE SETS
-------------------------------------------------
  DNP (not fitted at all)
      exclude_from_bom + exclude_from_pos_files + dnp
      -> in neither file, and flagged do-not-populate for anyone reading the board in KiCad

  HAND-FIT (fitted, but bought elsewhere and soldered by hand)
      exclude_from_bom + exclude_from_pos_files   (NOT dnp)
      -> in neither JLC file, but NOT marked do-not-populate, because the part IS on the final
         board (U3, U_LORA1280, the four wing sockets)

Conflating those two is what let six hand-fit parts sit in the CPL and ask JLC to place parts it
has no LCSC number for.

Usage:
  set_assembly_attributes.py <board> [--out <path>] [--check]
"""
import argparse
import sys

import pcbnew

DNP = ['U_C', 'U2', 'U5', 'U6', 'C_CAP1', 'C_CAP2',
       'U_CUT1', 'U_CUT2', 'U_CUT3', 'U_CUT4', 'U_HUB_CVT']
HAND_FIT = ['J_W1', 'J_W2', 'J_W3', 'J_W4', 'U3', 'U_LORA1280']

DNP_MASK = pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_DNP
HAND_MASK = pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES


def describe(attrs):
    return (f'DNP={bool(attrs & pcbnew.FP_DNP)} '
            f'EXCL_BOM={bool(attrs & pcbnew.FP_EXCLUDE_FROM_BOM)} '
            f'EXCL_POS={bool(attrs & pcbnew.FP_EXCLUDE_FROM_POS_FILES)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('board')
    ap.add_argument('--out', default='')
    ap.add_argument('--check', action='store_true',
                    help='only report; exit 1 if any part disagrees with the plan')
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.board)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}

    missing = [r for r in DNP + HAND_FIT if r not in fps]
    if missing:
        print(f'FAIL: references not on the board: {missing}')
        return 2

    bad = 0
    changed = 0
    for ref in DNP + HAND_FIT:
        fp = fps[ref]
        want = DNP_MASK if ref in DNP else HAND_MASK
        have = fp.GetAttributes()
        # only touch the three assembly bits; leave everything else (e.g. smd) alone
        new = (have & ~(DNP_MASK)) | want
        kind = 'DNP     ' if ref in DNP else 'HAND-FIT'
        if have != new:
            bad += 1
            print(f'  {ref:10s} {kind}  {describe(have)}  ->  {describe(new)}')
            if not args.check:
                fp.SetAttributes(new)
                changed += 1
        elif args.check:
            print(f'  {ref:10s} {kind}  correct')

    if args.check:
        print(f'\n{"PASS" if bad == 0 else "FAIL"}: {bad} part(s) disagree with the plan')
        return 0 if bad == 0 else 1

    if changed:
        pcbnew.Refresh()
        out = args.out or args.board
        pcbnew.SaveBoard(out, b)
        print(f'\n{changed} footprint(s) updated -> {out}')

        # verify by reloading, not by trusting the in-memory objects
        v = pcbnew.LoadBoard(out)
        vfps = {fp.GetReference(): fp for fp in v.GetFootprints()}
        still = [r for r in DNP + HAND_FIT
                 if vfps[r].GetAttributes() != ((vfps[r].GetAttributes() & ~DNP_MASK)
                                                | (DNP_MASK if r in DNP else HAND_MASK))]
        print(f'read-back: {len(still)} part(s) still wrong'
              + (f' {still}' if still else ' -- all agree'))
        return 0 if not still else 1

    print('nothing to change')
    return 0


if __name__ == '__main__':
    sys.exit(main())
