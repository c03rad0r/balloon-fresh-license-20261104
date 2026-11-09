#!/usr/bin/env python3
"""build_order_bundle.py -- assemble the exact set of files to upload to JLCPCB.

TWO VARIANTS, because which one you pick is a real cost decision and not a detail:

  (default)      double-sided: 23 placements, 19 top + 4 bottom.
                 JLCPCB offers double-sided placement ONLY on Standard PCBA, so this forfeits the
                 cheaper Economic tier and takes the full Standard fee structure.

  --top-only     single-sided: 19 placements, all top. D_BP1..D_BP4 (SS24, SMA) move to the hand-fit
                 list instead. Keeps ECONOMIC PCBA -- a materially different price -- at the cost of
                 four large, easily hand-soldered diodes.

Both variants are written, each in its own directory with its own zip, so whichever is chosen can be
uploaded without regenerating anything.

WHY
---
The current gerbers are geometrically identical to the board of record (proved by
verify_gerbers_fresh.py) but live in a directory called `fab-11opens`, which names a board state that
no longer exists. A human uploading files reads directory names. The name is a defect even though the
bytes are fine.

This writes ONLY what JLCPCB needs, with names that say what they are. It zips the whole thing,
because JLCPCB accepts a single archive and that removes a class of upload mistake (forgetting a
layer).

DNP parts are NOT in the BOM or CPL: they were stripped from the board attributes upstream
(set_assembly_attributes.py) and the exports are derived (export_fab_files.py). This script does not
re-derive them; it copies the derived pair so there is exactly one source of truth.
"""
import csv
import os
import shutil
import sys
import zipfile

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_GERB = os.path.join(WT, 'docs/analysis/bulk-route-20261107/fab-11opens')
SRC_ASM = os.path.join(WT, 'docs/analysis/bulk-route-20261107/assembly-generated')

# Layers JLCPCB needs for a 4-layer board. Deliberately a whitelist: a User_* or Adhesive layer in
# the archive is harmless but confusing, and a MISSING copper layer is fatal.
NEEDED = {
    'board-F_Cu.gtl': 'F.Cu',
    'board-In1_Cu.g1': 'In1.Cu',
    'board-In2_Cu.g2': 'In2.Cu',
    'board-B_Cu.gbl': 'B.Cu',
    'board-F_Mask.gts': 'F.Mask',
    'board-B_Mask.gbs': 'B.Mask',
    'board-F_Silkscreen.gto': 'F.Silkscreen',
    'board-B_Silkscreen.gbo': 'B.Silkscreen',
    'board-F_Paste.gtp': 'F.Paste',
    'board-B_Paste.gbp': 'B.Paste',
    'board-Edge_Cuts.gm1': 'Edge.Cuts',
    'board.drl': 'drill',
    'board-job.gbrjob': 'job',
}

# The only bottom-side placements on this board.
BOTTOM = {'D_BP1', 'D_BP2', 'D_BP3', 'D_BP4'}


def read_csv(p):
    with open(p, newline='') as f:
        return list(csv.DictReader(f))


def write_csv(p, rows, fields):
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def designators(row):
    for d in (row.get('Designator') or '').replace('"', '').split(','):
        d = d.strip()
        if d:
            yield d


def build(top_only):
    name = 'top-only' if top_only else 'double-sided'
    out = os.path.join(WT, 'docs/fab', f'v10-order-{name}')
    gerb = os.path.join(out, 'gerbers')
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(gerb, exist_ok=True)

    missing = [(n, w) for n, w in NEEDED.items() if not os.path.exists(os.path.join(SRC_GERB, n))]
    if missing:
        print('MISSING REQUIRED FILES -- cannot build a valid order:')
        for n, w in missing:
            print(f'  {n:28s} ({w})')
        sys.exit(1)
    for n in NEEDED:
        shutil.copy2(os.path.join(SRC_GERB, n), os.path.join(gerb, n))

    bom = read_csv(os.path.join(SRC_ASM, 'bom-jlc.csv'))
    cpl = read_csv(os.path.join(SRC_ASM, 'cpl-jlc.csv'))
    hand = read_csv(os.path.join(SRC_ASM, 'hand-fit.csv'))

    if top_only:
        new_bom = []
        for r in bom:
            keep = [d for d in designators(r) if d not in BOTTOM]
            if not keep:
                continue                      # the whole row was bottom parts
            r = dict(r)
            r['Designator'] = ','.join(keep)
            r['Quantity'] = str(len(keep))
            new_bom.append(r)
        bom = new_bom
        cpl = [r for r in cpl if r['Designator'].strip() not in BOTTOM]
        hand.append({
            'Designator': ','.join(sorted(BOTTOM)),
            'Val': 'SS24',
            'Package': 'D_SMA',
            'Quantity': str(len(BOTTOM)),
            'Note': 'bottom-side; hand-solder so the order stays on Economic PCBA',
        })

    write_csv(os.path.join(out, 'bom-jlc.csv'), bom,
              ['Comment', 'Designator', 'Footprint', 'Quantity', 'LCSC Part #'])
    write_csv(os.path.join(out, 'cpl-jlc.csv'), cpl, list(cpl[0].keys()))
    write_csv(os.path.join(out, 'hand-fit-NOT-FOR-JLC.csv'), hand, list(hand[0].keys()))

    zpath = os.path.join(out, 'v10-jlcpcb-upload.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in NEEDED:
            z.write(os.path.join(gerb, n), f'gerbers/{n}')
        z.write(os.path.join(out, 'bom-jlc.csv'), 'bom-jlc.csv')
        z.write(os.path.join(out, 'cpl-jlc.csv'), 'cpl-jlc.csv')

    # ---- the real invariant: designator SETS, not row counts
    bom_set = {d for r in bom for d in designators(r)}
    cpl_set = {r['Designator'].strip() for r in cpl if r.get('Designator', '').strip()}
    top = sum(1 for r in cpl if r.get('Layer', '').lower().startswith('t'))
    bot = sum(1 for r in cpl if r.get('Layer', '').lower().startswith('b'))
    print(f'\n=== {name}')
    print(f'  bom: {len(bom)} part rows -> {len(bom_set)} designators')
    print(f'  cpl: {len(cpl)} placements ({top} top / {bot} bottom) -> {len(cpl_set)} designators')
    if bom_set != cpl_set:
        print('  FAIL: BOM and CPL designator SETS differ')
        print(f'    only in BOM: {sorted(bom_set - cpl_set)}')
        print(f'    only in CPL: {sorted(cpl_set - bom_set)}')
        sys.exit(1)
    if top_only and bot:
        print(f'  FAIL: --top-only requested but {bot} bottom placement(s) remain')
        sys.exit(1)
    print(f'  sets match: {len(cpl_set)} parts, {len(cpl)} placements')
    print(f'  zip: {os.path.relpath(zpath, WT)}  {os.path.getsize(zpath):,d} B')
    return out


if __name__ == '__main__':
    build('--top-only' in sys.argv)
    if '--both' in sys.argv:
        build('--top-only' not in sys.argv)
