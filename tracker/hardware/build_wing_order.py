#!/usr/bin/env python3
"""build_wing_order.py -- assemble the JLCPCB upload set for the two solar boards.

Two boards, both electrically complete and both 2-layer:

  WING CARRIER   tracker/hardware/wing_board/wing_board_v9.kicad_pcb      184 x 25 mm
                 six solar-cell lands, front string SC1-3 and back string SC4-6 (ADR-065),
                 wing tab J1, three NPTH mounting holes, three fiducials.
                 The cells themselves are NOT placed by JLCPCB -- a solar cell has no LCSC
                 number. This board is the LAND PATTERN you solder cells onto, which is exactly
                 what was asked for.

  INTERCONNECT   tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb  35 x 20 mm
                 three SS24 bypass diodes across the per-wing cell string, plus the tab.

WHY THE CELLS ARE HAND-FIT AND NOT A BOM FAILURE
------------------------------------------------
`solar cell` is not a purchasable LCSC part at this size -- the cell is supplied by the panel
vendor. So the carrier board is ordered as BARE PCB plus the small passives, and the cells are
soldered by hand. That is not a gap; it is the point of the board.

USAGE
    /usr/bin/python3 tracker/hardware/build_wing_order.py
    /usr/bin/python3 tracker/hardware/build_wing_order.py --verify-only

Writes docs/fab/wing-order/{carrier,interconnect}/ and zips each.
"""
import argparse
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTROOT = os.path.join(WT, 'docs/fab/wing-order')

CARRIER = os.path.join(WT, 'tracker/hardware/wing_board/wing_board_v9.kicad_pcb')
INTERCON = os.path.join(WT, 'tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb')

# Parts JLCPCB can place. Everything else on these boards is either a bare land (solar cell,
# wing tab, test pad) or deliberately unpopulated (V2 provisions).
JLC_PARTS = {
    # designator: (comment, footprint, qty, LCSC)
    'D1': ('SS24', 'D_SMA', 1, 'C50645'),
    'D2': ('SS24', 'D_SMA', 1, 'C50645'),
    'D3': ('SS24', 'D_SMA', 1, 'C50645'),
}

# Layers JLCPCB needs for a 2-layer board.
NEEDED_2L = ['F_Cu.gtl', 'B_Cu.gbl', 'F_Mask.gts', 'B_Mask.gbs',
             'F_Silkscreen.gto', 'B_Silkscreen.gbo', 'Edge_Cuts.gm1']


def sha8(path):
    import hashlib
    d = open(path, 'rb').read()
    h = hashlib.sha1(b'blob %d\0' % len(d))
    h.update(d)
    return h.hexdigest()[:8]


def board_meta(path):
    import pcbnew
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    return dict(
        w=pcbnew.ToMM(bb.GetWidth()), h=pcbnew.ToMM(bb.GetHeight()),
        fp=len(b.GetFootprints()), tracks=len(tracks), vias=len(vias),
        board=b,
    )


def export(board_path, outdir, name):
    """Export gerbers + drill with the SAME recipe the hub order uses.

    --subtract-soldermask is not cosmetic: without it the silkscreen contains zero flashes
    (measured on the hub, 204 vs 0), because the mask subtraction is what knocks silk out
    around pads. A package built without it is a different artwork.
    """
    # Native export ignores disabled layers, even when explicitly requested.
    # Enable paste on an export-only copy; never alter source copper or rules.
    import pcbnew
    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        board = pcbnew.LoadBoard(board_path)
        enabled = board.GetEnabledLayers()
        enabled.AddLayer(pcbnew.F_Paste)
        enabled.AddLayer(pcbnew.B_Paste)
        board.SetEnabledLayers(enabled)
        if name == 'interconnect':
            for footprint in board.GetFootprints():
                if footprint.GetReference() not in JLC_PARTS:
                    for pad in footprint.Pads():
                        layers = pad.GetLayerSet()
                        layers.RemoveLayer(pcbnew.F_Paste)
                        layers.RemoveLayer(pcbnew.B_Paste)
                        pad.SetLayerSet(layers)
        export_path = os.path.join(scratch, os.path.basename(board_path))
        pcbnew.SaveBoard(export_path, board)
        return _export_native(export_path, outdir, name)


def _export_native(board_path, outdir, name):
    os.makedirs(outdir, exist_ok=True)
    g = subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers',
                        '--no-x2', '--subtract-soldermask',
                        '--layers', 'F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts',
                        '--output', outdir, board_path],
                       capture_output=True, text=True)
    if g.returncode != 0:
        raise SystemExit(f'gerber export failed for {name}:\n{g.stdout[-1500:]}{g.stderr[-1500:]}')
    d = subprocess.run(['kicad-cli', 'pcb', 'export', 'drill',
                        '--format', 'excellon', '--drill-origin', 'absolute',
                        '--excellon-units', 'mm', '--output', outdir, board_path],
                       capture_output=True, text=True)
    if d.returncode != 0:
        raise SystemExit(f'drill export failed for {name}:\n{d.stdout[-1500:]}{d.stderr[-1500:]}')

    # normalise the stem so the package does not carry the build-machine's temp filename
    for f in sorted(os.listdir(outdir)):
        if f.startswith(name + '-') or f.startswith(name + '.'):
            continue
        stem, ext = os.path.splitext(f)
        if '-' in stem:
            suffix = stem.split('-', 1)[1]
            newname = f'{name}-{suffix}{ext}'
        else:
            newname = f'{name}{ext}'
        if newname != f:
            os.rename(os.path.join(outdir, f), os.path.join(outdir, newname))


def parse_drill(path):
    """Return (holes, tools). A bare `Tn` line SELECTS a tool; `TnCd` DEFINES one.

    Getting this backwards is how an earlier parser in this project reported 0 holes at
    0.200 mm when there were 12.
    """
    tools, holes, cur = {}, [], None
    for line in open(path, errors='replace'):
        line = line.strip()
        m = re.match(r'^T(\d+)(?:C([0-9.]+))?$', line)
        if m:
            if m.group(2) is not None:
                tools[m.group(1)] = m.group(2)
            else:
                cur = m.group(1)
            continue
        m = re.match(r'^X(-?[0-9.]+)Y(-?[0-9.]+)', line)
        if m:
            holes.append((cur, m.group(1), m.group(2)))
    return holes, tools


def write_bom(path, parts):
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Comment', 'Designator', 'Footprint', 'Quantity', 'LCSC Part #'])
        for desig, (comment, fp, qty, lcsc) in sorted(parts.items()):
            w.writerow([comment, desig, fp, qty, lcsc])


def write_cpl(path, board, H, parts):
    """Use KiCad's absolute-origin placement export, matching Gerber and drill.

    H is retained for API compatibility only; outline height is NOT an origin.
    Footprint anchors are the native placement datum, not a guessed pad bbox.
    """
    import pcbnew
    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        source = os.path.join(scratch, 'placement.kicad_pcb')
        native = os.path.join(scratch, 'native.csv')
        pcbnew.SaveBoard(source, board)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv',
                        '--units', 'mm', '--output', native, source], check=True,
                       capture_output=True, text=True)
        with open(native, newline='') as fh:
            positions = {row['Ref']: row for row in csv.DictReader(fh)}
    rows = []
    with open(path, 'w', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['Designator', 'Val', 'Package', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        for ref in sorted(parts):
            row = positions[ref]
            values = (ref, row['Val'], row['Package'], row['PosX'], row['PosY'],
                      row['Rot'], 'Top' if row['Side'] == 'top' else 'Bottom')
            writer.writerow(values)
            rows.append(values)
    return rows


def zipdir(src, dst):
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(src):
            for f in sorted(files):
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, src))


def build(name, board_path, parts, note):
    outdir = os.path.join(OUTROOT, name)
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)

    meta = board_meta(board_path)
    board = meta['board']
    print(f"\n=== {name} ===")
    print(f"  board {sha8(board_path)}  {meta['w']:.1f} x {meta['h']:.1f} mm  "
          f"{meta['fp']} footprints  {meta['tracks']} tracks  {meta['vias']} vias")

    export(board_path, outdir, name)
    drls = [f for f in os.listdir(outdir) if f.endswith('.drl')]
    if len(drls) != 1:
        raise SystemExit(f'{name}: expected 1 drill file, found {drls}')
    holes, tools = parse_drill(os.path.join(outdir, drls[0]))
    from collections import Counter
    bydia = Counter(tools.get(t, '?') for t, _, _ in holes)
    print(f"  drill: {len(holes)} holes  " + "  ".join(f'{d}mm x{n}' for d, n in sorted(bydia.items())))

    if parts:
        write_bom(os.path.join(outdir, 'bom-jlc.csv'), parts)
        rows = write_cpl(os.path.join(outdir, 'cpl-jlc.csv'), board, meta['h'], parts)
        print(f"  assembly: {len(rows)} placements, all top")
    else:
        print("  assembly: none -- bare PCB only")

    with open(os.path.join(outdir, 'README.md'), 'w') as fh:
        fh.write(f'# {name}\n\n{note}\n\n'
                 f'- board `{sha8(board_path)}`, {meta["w"]:.1f} x {meta["h"]:.1f} mm, 2-layer\n'
                 f'- drill {len(holes)} holes: '
                 + ', '.join(f'{d} mm x {n}' for d, n in sorted(bydia.items())) + '\n'
                 f'- gerbers exported with `--no-x2 --subtract-soldermask`\n')

    # whitelist-check the copper layers before zipping: a missing copper layer is fatal and
    # a package that "looks complete" is not evidence
    present = set(os.listdir(outdir))
    missing = [l for l in NEEDED_2L if l.split('.')[0].replace('_', '-') not in
               ' '.join(present).replace('_', '-')]
    for l in NEEDED_2L:
        stem = l.split('.')[0]
        if not any(stem.lower() in p.lower().replace('-', '_') for p in present):
            raise SystemExit(f'{name}: required layer {l} missing from the export')

    zipdir(outdir, os.path.join(OUTROOT, f'{name}-jlcpcb-upload.zip'))
    zp = os.path.join(OUTROOT, f'{name}-jlcpcb-upload.zip')
    print(f"  zip: {zp}  {os.path.getsize(zp)} B")
    return dict(name=name, holes=len(holes), dia=dict(bydia), board=sha8(board_path), zip=zp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify-only', action='store_true')
    ap.add_argument('--interconnect-only', action='store_true', help='Leave carrier artifacts untouched')
    args = ap.parse_args()

    results = []
    if not args.interconnect_only:
        results.append(build(
            'carrier', CARRIER, {},
            'Solar cell carrier. Six solar-cell solder lands: SC1-SC3 on the front face and\n'
            'SC4-SC6 on the back face at the same X centres (ADR-065 parallel string), so the\n'
            'coincident bounding boxes are one cell seen from both sides, not a duplicated part.\n\n'
            'The cells have no LCSC number, so this is ordered as a BARE PCB and the cells are\n'
            'soldered by hand -- which is the purpose of the board.\n\n'
            'Two nets are single-pad by design: `GND` (no plane on this board) and `RF_FEED`\n'
            '(ADR-046 s2.4 V2 provision land).'))
    results.append(build(
        'interconnect', INTERCON, JLC_PARTS,
        'Per-wing bypass interconnect. Three SS24 (SMA) diodes across the cell string:\n'
        'SOLAR_P - SOLAR_MID1 - SOLAR_MID2 - SOLAR_N.\n\n'
        'These are NOT duplicates of the hub D_BP1..4: the hub carries bypass BETWEEN wings\n'
        '(W1_P..W1_N..W2_N..W3_N..GND) while this board carries PER-CELL bypass inside one wing.'))

    print("\n=== summary ===")
    for r in results:
        print(f"  {r['name']:<14} board {r['board']}  {r['holes']} holes  {os.path.basename(r['zip'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
