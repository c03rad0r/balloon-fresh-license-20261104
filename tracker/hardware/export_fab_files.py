#!/usr/bin/env python3
"""export_fab_files.py -- generate BOM + CPL FROM THE BOARD, so they cannot drift again.

WHY THIS REPLACES HAND-MAINTAINED CSV
------------------------------------
Measured 2026-11-09: the board had U_C fully fitted (attrs=2, DNP=False, EXCL_BOM=False) while the
BOM, the CPL and the hand-fit list all said it was dropped. Seventeen footprints disagreed with the
documented plan -- not one. The paperwork was the only place the decision lived, so the binary that
gets fabricated and the CSV that gets uploaded could diverge silently.

With the attributes now set on the board (see set_assembly_attributes.py), the exports are DERIVED,
not maintained. If someone changes a part's DNP bit, these files follow on the next run. That is the
structural fix; a corrected CSV is only a better snapshot.

WHAT IT WRITES
  bom-jlc.csv     LCSC BOM for JLCPCB: one line per distinct value/part, designators grouped
  cpl-jlc.csv     placement file, all fitted parts that JLC places
  hand-fit.csv    parts fitted on the final board but NOT placed by JLC (no LCSC number)

Y CONVENTION -- the thing my first checker got wrong
  pcbnew returns Y increasing DOWNWARD from a top-left origin. A fab position file wants Y
  increasing UPWARD from the bottom-left. So y_cpl = H - y_board, where H is the board's Y extent.
  Measured on this board the required offset is exactly H (80.000), and the previous hand-made CPL
  was 0.100 mm off on every row because it used 80.100.

Usage: export_fab_files.py <board.kicad_pcb> [--outdir DIR]
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

import pcbnew

MM = 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('board')
    ap.add_argument('--outdir', default='')
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.board)
    outdir = args.outdir or os.path.join(os.path.dirname(os.path.abspath(args.board)),
                                         'assembly-generated')
    os.makedirs(outdir, exist_ok=True)

    # board extent for the Y flip
    xs, ys = [], []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts and d.GetClass() == 'PCB_SHAPE':
            for p in (d.GetStart(), d.GetEnd()):
                xs.append(p.x / MM)
                ys.append(p.y / MM)
    X0, Y0, H = min(xs), min(ys), max(ys) - min(ys)
    print(f'board extent: x {min(xs):.3f}..{max(xs):.3f}  y {min(ys):.3f}..{max(ys):.3f}  H={H:.3f}')

    placed, hand = [], []
    for fp in b.GetFootprints():
        attrs = fp.GetAttributes()
        ref = fp.GetReference()
        fpid = str(fp.GetFPID().GetLibItemName())
        val = fp.GetValue()
        # CENTRE OF THE PAD ARRAY, not the footprint anchor.
        # Measured 2026-11-09: KiCad puts a PinHeader's anchor on PAD 1. Emitting the anchor put
        # J_HUB_PV 5.080 mm and J_PROG 6.350 mm from the centre of their own pin arrays -- 2.0 and
        # 2.5 pitches at 2.54 mm -- so JLC would rotate the header about the wrong point and the
        # pins would miss the holes. U1 was 1.587 mm off, U7 0.227 mm.
        # The same fix is in docs/analysis/make_cpl_from_board.py; both generators had it, because
        # both took the convenient number instead of the correct one.
        _pads = list(fp.Pads())
        if _pads:
            _xs0 = [(q.GetPosition().x - q.GetSize().x / 2) for q in _pads]
            _xs1 = [(q.GetPosition().x + q.GetSize().x / 2) for q in _pads]
            _ys0 = [(q.GetPosition().y - q.GetSize().y / 2) for q in _pads]
            _ys1 = [(q.GetPosition().y + q.GetSize().y / 2) for q in _pads]
            x = ((min(_xs0) + max(_xs1)) / 2) / MM
            y = ((min(_ys0) + max(_ys1)) / 2) / MM
        else:
            x, y = fp.GetPosition().x / MM, fp.GetPosition().y / MM
        side = 'Bottom' if fp.IsFlipped() else 'Top'
        row = dict(Designator=ref, Val=val, Package=fpid,
                   Mid_X=f'{x - X0:.4f}', Mid_Y=f'{H - (y - Y0):.4f}',
                   Layer=side, Rotation=f'{fp.GetOrientationDegrees():.1f}')
        if attrs & pcbnew.FP_EXCLUDE_FROM_POS_FILES:
            if not (attrs & pcbnew.FP_DNP):
                hand.append(row)          # fitted on the final board, not by JLC
            continue                       # DNP: in neither file
        placed.append(row)

    # ---- CPL
    cpl = os.path.join(outdir, 'cpl-jlc.csv')
    with open(cpl, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['Designator', 'Val', 'Package', 'Mid X', 'Mid Y',
                                           'Layer', 'Rotation'])
        w.writeheader()
        for r in sorted(placed, key=lambda r: r['Designator']):
            w.writerow({'Designator': r['Designator'], 'Val': r['Val'], 'Package': r['Package'],
                        'Mid X': r['Mid_X'], 'Mid Y': r['Mid_Y'], 'Layer': r['Layer'],
                        'Rotation': r['Rotation']})

    # ---- BOM. LCSC numbers are NOT derivable from the board: the board carries footprints, not
    # supplier part numbers. So the mapping is read from the existing curated CSV and only the
    # DESIGNATOR GROUPS are recomputed from the board. That keeps the verified numbers and makes
    # the membership follow the board.
    curated = os.path.join(os.path.dirname(os.path.abspath(args.board)), 'assembly-partial',
                           'asm-bom-jlc.csv')
    lcsc_by_ref = {}
    if os.path.exists(curated):
        with open(curated, newline='') as fh:
            for row in csv.DictReader(fh):
                for d in (row.get('Designator') or '').replace('"', '').split(','):
                    d = d.strip()
                    if d:
                        lcsc_by_ref[d] = (row.get('LCSC Part #', ''), row.get('Footprint', ''),
                                          row.get('Comment', ''))
    else:
        print(f'WARN: no curated BOM at {curated}; LCSC numbers will be blank')

    groups = defaultdict(list)
    for r in placed:
        if r['Designator'] in lcsc_by_ref:
            _l, _f, comment = lcsc_by_ref[r['Designator']]
        else:
            comment = r['Val']
        groups[(comment, r['Package'])].append(r['Designator'])

    bom = os.path.join(outdir, 'bom-jlc.csv')
    missing = []
    with open(bom, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Comment', 'Designator', 'Footprint', 'Quantity', 'LCSC Part #'])
        for (comment, pkg), refs in sorted(groups.items()):
            refs = sorted(refs)
            lcsc = lcsc_by_ref.get(refs[0], ('', '', ''))[0]
            if not lcsc:
                missing.append(refs[0])
            w.writerow([comment, ','.join(refs), pkg, len(refs), lcsc])

    # ---- hand-fit
    hf = os.path.join(outdir, 'hand-fit.csv')
    with open(hf, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Designator', 'Val', 'Package', 'Quantity', 'Note'])
        bypkg = defaultdict(list)
        for r in hand:
            bypkg[(r['Package'], r['Val'])].append(r['Designator'])
        for (pkg, val), refs in sorted(bypkg.items()):
            w.writerow([','.join(sorted(refs)), val, pkg, len(refs),
                        'fitted by hand, not placed by JLC'])

    print(f'\nplaced by JLC : {len(placed)}')
    print(f'hand-fit      : {len(hand)}')
    print(f'DNP           : {49 - len(placed) - len(hand)} (of 49 footprints)')
    print(f'\nwrote:\n  {bom}\n  {cpl}\n  {hf}')
    if missing:
        print(f'\nWARN: no LCSC number for {missing} -- JLC will reject those lines')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
