#!/usr/bin/env python3
"""build_order_bundle.py -- assemble the exact set of files to upload to JLCPCB.

WHY
---
The current gerbers are geometrically identical to the board of record (proved by
verify_gerbers_fresh.py) but live in a directory called `fab-11opens`, which names a board state
that no longer exists. A human uploading files reads directory names. The name is a defect even
though the bytes are fine.

This writes docs/fab/v10-order/ containing ONLY what JLCPCB needs, with names that say what they
are, plus a README stating the settings. It also zips the whole thing, because JLCPCB accepts a
single archive and that removes a class of upload mistake (forgetting a layer).

DNP parts are NOT in the BOM or CPL: they were stripped from the board attributes upstream
(set_assembly_attributes.py) and the exports are derived (export_fab_files.py). This script does
not re-derive them; it copies the derived pair so there is exactly one source of truth.
"""
import os
import shutil
import subprocess
import sys
import zipfile

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_GERB = os.path.join(WT, 'docs/analysis/bulk-route-20261107/fab-11opens')
SRC_ASM = os.path.join(WT, 'docs/analysis/bulk-route-20261107/assembly-generated')
OUT = os.path.join(WT, 'docs/fab/v10-order')
GERB = os.path.join(OUT, 'gerbers')

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


def main():
    if os.path.isdir(GERB):
        shutil.rmtree(GERB)
    os.makedirs(GERB, exist_ok=True)

    missing = []
    copied = []
    for name, what in NEEDED.items():
        src = os.path.join(SRC_GERB, name)
        if not os.path.exists(src):
            missing.append((name, what))
            continue
        shutil.copy2(src, os.path.join(GERB, name))
        copied.append((name, what, os.path.getsize(src)))

    if missing:
        print('MISSING REQUIRED FILES -- cannot build a valid order:')
        for n, w in missing:
            print(f'  {n:28s} ({w})')
        sys.exit(1)

    print(f'gerbers: {len(copied)} files')
    for name, what, sz in sorted(copied, key=lambda r: r[1]):
        print(f'  {what:14s} {name:28s} {sz:>9,d} B')

    # ---- assembly files
    asm_files = [('bom-jlc.csv', 'BOM (JLC format)'),
                 ('cpl-jlc.csv', 'CPL / pick-and-place'),
                 ('hand-fit.csv', 'hand-fit list (NOT sent to JLC)')]
    for name, what in asm_files:
        src = os.path.join(SRC_ASM, name)
        if not os.path.exists(src):
            print(f'MISSING assembly file: {src}')
            sys.exit(1)

    # BOM and CPL go IN the upload; hand-fit does not.
    for name in ('bom-jlc.csv', 'cpl-jlc.csv'):
        shutil.copy2(os.path.join(SRC_ASM, name), os.path.join(OUT, name))
    shutil.copy2(os.path.join(SRC_ASM, 'hand-fit.csv'), os.path.join(OUT, 'hand-fit-NOT-FOR-JLC.csv'))
    print('\nassembly:')
    for name, what in asm_files:
        print(f'  {what}')

    # ---- zip exactly what gets uploaded
    zpath = os.path.join(OUT, 'v10-jlcpcb-upload.zip')
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in NEEDED:
            z.write(os.path.join(GERB, name), f'gerbers/{name}')
        z.write(os.path.join(OUT, 'bom-jlc.csv'), 'bom-jlc.csv')
        z.write(os.path.join(OUT, 'cpl-jlc.csv'), 'cpl-jlc.csv')
    print(f'\nzip: {os.path.relpath(zpath, WT)}  '
          f'{os.path.getsize(zpath):,d} B  ({len(NEEDED) + 2} entries)')

    # ---- counts for the README, measured not remembered
    import csv
    bom = list(csv.DictReader(open(os.path.join(OUT, 'bom-jlc.csv'))))
    cpl = [r for r in csv.DictReader(open(os.path.join(OUT, 'cpl-jlc.csv'))) if r]

    # A BOM is GROUPED by part (one row per distinct part, designators comma-joined); a CPL is one
    # row per PLACEMENT. So the row counts legitimately differ -- 14 part rows vs 23 placements.
    # Comparing len(bom) to len(cpl) is a category error, not a check. Expand the designator lists
    # and compare SETS, which is the real invariant.
    def designators(rows):
        out = set()
        for r in rows:
            for d in (r.get('Designator') or '').replace('"', '').split(','):
                d = d.strip()
                if d:
                    out.add(d)
        return out

    bom_set = designators(bom)
    cpl_set = {r['Designator'].strip() for r in cpl if r.get('Designator', '').strip()}
    top = sum(1 for r in cpl if r.get('Layer', '').lower().startswith('t'))
    bot = sum(1 for r in cpl if r.get('Layer', '').lower().startswith('b'))

    print(f'\nbom: {len(bom)} part rows -> {len(bom_set)} designators')
    print(f'cpl: {len(cpl)} placements ({top} top / {bot} bottom) -> {len(cpl_set)} designators')
    if bom_set != cpl_set:
        print('FAIL: BOM and CPL designator SETS differ -- run check_order_files.py')
        print(f'  only in BOM: {sorted(bom_set - cpl_set)}')
        print(f'  only in CPL: {sorted(cpl_set - bom_set)}')
        sys.exit(1)
    print(f'  designator sets match: {len(cpl_set)} parts, {len(cpl)} placements')



if __name__ == '__main__':
    main()
