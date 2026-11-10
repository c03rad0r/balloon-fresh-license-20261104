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

# ---------------------------------------------------------------------------
# REPRODUCIBILITY
#
# KiCad stamps every gerber, drill file and the .gbrjob with the wall clock and
# zipfile stamps every entry with the mtime.  Without normalisation a rebuild of
# an unchanged board differs from the committed package in 11 of 12 files and the
# only real change is a timestamp -- which makes "is the committed bundle still
# the design?" unanswerable by hashing.  Every emitted stamp is therefore fixed
# to the SOURCE COMMIT TIME of the board (deterministic per commit, and
# meaningful: the package is the package of that commit).
# ---------------------------------------------------------------------------


def export_epoch():
    """Canonical timestamp for emitted artefacts: SOURCE_DATE_EPOCH, else the
    source board's last commit time, else a frozen constant."""
    env = os.environ.get('SOURCE_DATE_EPOCH')
    if env:
        return int(env)
    try:
        out = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', INTERCON],
                             cwd=WT, capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return int(out.stdout.strip())
    except Exception:
        pass
    return 1762300000  # frozen fallback; only reached outside a git checkout

STAMP_RE = [
    (re.compile(r'(TF\.CreationDate,)[0-9T:+\-]+'), r'\g<1>{iso}'),
    (re.compile(r'(date )[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:]{8}'), r'\g<1>{nice}'),
    (re.compile(r'(date )[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}[+\-][0-9]{4}'), r'\g<1>{iso}'),
    (re.compile(r'("CreationDate": ") ?[0-9T:+\-]+'), r'\g<1>{iso}'),
]
# Every text extension kicad-cli emits, including the ones nothing uses for JLC,
# because the carrier package is a full artwork set: the adhesive layers are
# `.gta/.gba` and missing them left their CreationDate at build time, which is
# why a full `--check` could not go byte-green. `.gbr` covers the documentation
# layers KiCad names `<stem>-<Layer>.gbr`.
TEXT_EXT = {'.gtl', '.gbl', '.gts', '.gbs', '.gto', '.gbo', '.gtp', '.gbp',
            '.gta', '.gba', '.gm1', '.gbrjob', '.drl', '.gbr'}


def normalise_stamps(path, epoch=None):
    """Rewrite every wall-clock stamp in an exported text artefact to `epoch`."""
    import datetime
    epoch = export_epoch() if epoch is None else epoch
    dt = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
    iso = dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    nice = dt.strftime('%Y-%m-%d %H:%M:%S')
    changed = False
    for root, _dirs, files in os.walk(path):
        for f in files:
            if os.path.splitext(f)[1].lower() not in TEXT_EXT:
                continue
            full = os.path.join(root, f)
            with open(full, errors='replace') as fh:
                text = fh.read()
            new = text
            for rx, repl in STAMP_RE:
                new = rx.sub(repl.format(iso=iso, nice=nice), new)
            if new != text:
                with open(full, 'w') as fh:
                    fh.write(new)
                changed = True
    return changed


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
    d = open(path, 'rb').read()
    h = hashlib.sha1(b'blob %d\0' % len(d))
    h.update(d)
    return h.hexdigest()[:8]


def sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def centreline_bbox(board):
    """Edge.Cuts CENTRELINE extent, in mm.

    GetBoardEdgesBoundingBox() inflates by the outline line width (0.1 mm), so it
    reported 34.7 x 20.1 mm for a board whose drawn outline is 34.6 x 20.0 mm.
    A fabricator quotes the centreline; measure the centreline.
    """
    import pcbnew
    xs, ys = [], []
    for d in board.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if not hasattr(d, 'GetStart'):
            continue
        for pt in (d.GetStart(), d.GetEnd()):
            xs.append(pcbnew.ToMM(pt.x))
            ys.append(pcbnew.ToMM(pt.y))
    if not xs:
        bb = board.GetBoardEdgesBoundingBox()
        return pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    return max(xs) - min(xs), max(ys) - min(ys)


def board_meta(path):
    import pcbnew
    b = pcbnew.LoadBoard(path)
    w, h = centreline_bbox(b)
    tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    return dict(
        w=w, h=h,
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


JLC_LAYERS = ('F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,'
              'F.Silkscreen,B.Silkscreen,Edge.Cuts')


def _export_native(board_path, outdir, name):
    """Export gerbers + drill.

    The layer list is package-specific and that difference is load-bearing:

      * ``interconnect`` is the JLC upload package, so it gets the minimal
        whitelist of layers JLC actually consumes.
      * every other package (the ``carrier``) is a documentation/artwork set and
        keeps the full layer table. Passing the JLC whitelist to it silently
        stripped F/B_Fab, F/B_Courtyard, F/B_Adhesive, Margin and the User.*
        layers that ``299e3790`` had deliberately restored, which made
        ``--check`` fail on a full build with 'ARTWORK-IDENTICAL, BYTES DIFFER'
        and 10 extra committed layers. Restoring the carrier's full layer set is
        the fix; do not relax ``--check`` instead.
    """
    os.makedirs(outdir, exist_ok=True)
    cmd = ['kicad-cli', 'pcb', 'export', 'gerbers',
           '--no-x2', '--subtract-soldermask']
    if name == 'interconnect':
        cmd += ['--layers', JLC_LAYERS]
    # else: no --layers => kicad-cli exports every enabled layer, which is what
    # the carrier package is supposed to contain.
    cmd += ['--output', outdir, board_path]
    g = subprocess.run(cmd, capture_output=True, text=True)
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


def verify_bypass_polarity(board):
    """KiCad pad 1 is K: MDD SS24's banded terminal must land here.

    This verifies board topology, not JLC's independent zero-angle model.
    """
    chain = ('SOLAR_P', 'SOLAR_MID1', 'SOLAR_MID2', 'SOLAR_N')
    for i, ref in enumerate(('D1', 'D2', 'D3')):
        fp = board.FindFootprintByReference(ref)
        pads = {} if fp is None else {p.GetNumber(): p.GetNetname() for p in fp.Pads()}
        expected = {'1': chain[i], '2': chain[i + 1]}
        if pads != expected:
            raise ValueError(f'{ref}: bypass polarity: expected K/pad1, A/pad2 {expected}, got {pads}')


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


def zipdir(src, dst, epoch=None):
    """Zip deterministically: sorted names, fixed per-entry mtime, no host paths."""
    import time
    epoch = export_epoch() if epoch is None else epoch
    date_time = time.gmtime(epoch)[:6]
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(src):
            for f in sorted(files):
                full = os.path.join(root, f)
                arc = os.path.relpath(full, src)
                info = zipfile.ZipInfo(arc, date_time=date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                with open(full, 'rb') as fh:
                    z.writestr(info, fh.read())


def build(name, board_path, parts, note, outroot=None):
    outroot = outroot or OUTROOT
    if name == 'interconnect':
        import pcbnew
        verify_bypass_polarity(pcbnew.LoadBoard(board_path))
    outdir = os.path.join(outroot, name)
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)

    meta = board_meta(board_path)
    board = meta['board']
    print(f"\n=== {name} ===")
    print(f"  board {sha8(board_path)}  {meta['w']:.1f} x {meta['h']:.1f} mm  "
          f"{meta['fp']} footprints  {meta['tracks']} tracks  {meta['vias']} vias")

    export(board_path, outdir, name)
    normalise_stamps(outdir)
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

    zipdir(outdir, os.path.join(outroot, f'{name}-jlcpcb-upload.zip'))
    zp = os.path.join(outroot, f'{name}-jlcpcb-upload.zip')
    print(f"  zip: {zp}  {os.path.getsize(zp)} B")
    return dict(name=name, holes=len(holes), dia=dict(bydia), board=sha8(board_path), zip=zp)


def provenance(outroot):
    """Write/verify the source hashes the package was built from."""
    files = {
        'tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb': INTERCON,
        'tracker/hardware/wing_board/wing_board_v9.kicad_pcb': CARRIER,
        'tracker/hardware/build_wing_order.py': os.path.abspath(__file__),
    }
    data = {rel: sha256(path) for rel, path in files.items()}
    path = os.path.join(outroot, 'source-sha256.json')
    with open(path, 'w') as fh:
        fh.write('{\n')
        items = sorted(data.items())
        for i, (rel, h) in enumerate(items):
            fh.write(f'  "{rel}": "{h}"' + (',\n' if i < len(items) - 1 else '\n'))
        fh.write('}\n')
    return data


def package_hashes(outroot, name):
    """sha256 of every file in the committed package, relative to outroot."""
    out = {}
    for root, _dirs, files in os.walk(os.path.join(outroot, name)):
        for f in files:
            full = os.path.join(root, f)
            out[os.path.relpath(full, outroot)] = sha256(full)
    zp = os.path.join(outroot, f'{name}-jlcpcb-upload.zip')
    if os.path.exists(zp):
        out[os.path.basename(zp)] = sha256(zp)
    return out


def check(args, names):
    """--check: rebuild into a scratch dir and prove the COMMITTED package matches.

    Writes nothing in docs/. Two verdicts, deliberately distinct:

      byte-identical    every file matches by sha256 (the strong result)
      artwork-identical the gerbers/drill describe the same features, but text
                        stamps or the export layer LIST differ (a real but
                        narrower defect: state it, do not call it green)

    Exit 0 only on byte-identical for every requested board.
    """
    import tempfile
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        'gerber_geom_diff', os.path.join(WT, 'tools', 'gerber_geom_diff.py'))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    geom_parse = _mod.parse
    with tempfile.TemporaryDirectory() as scratch:
        run_builds(args, names, outroot=scratch)
        fresh = {}
        for name in names:
            fresh.update(package_hashes(scratch, name))
        fresh['source-sha256.json'] = sha256(os.path.join(scratch, 'source-sha256.json'))
        committed = {}
        for name in names:
            committed.update(package_hashes(OUTROOT, name))
        sp = os.path.join(OUTROOT, 'source-sha256.json')
        if os.path.exists(sp):
            committed['source-sha256.json'] = sha256(sp)

        only_fresh = sorted(set(fresh) - set(committed))
        only_committed = sorted(set(committed) - set(fresh))
        differing = sorted(k for k in set(fresh) & set(committed) if fresh[k] != committed[k])

        print('\n=== reproducibility check ===')
        print(f'  files compared: {len(set(fresh) & set(committed))}')
        for k in only_fresh:
            print(f'  MISSING from commit: {k}')
        for k in only_committed:
            print(f'  EXTRA in commit:     {k}')
        for k in differing:
            print(f'  DIFFERS:             {k}')

        if not (only_fresh or only_committed or differing):
            print('  VERDICT: REPRODUCIBLE — committed package is byte-identical to a fresh build')
            print(f'  {len(fresh)} files matched by sha256')
            return 0

        # Second tier: is the ARTWORK the same?  A stamp-only or aperture-order
        # difference is not "the package builds from a different board".
        artwork_bad = []
        ext = tuple('.gtl,.gbl,.gts,.gbs,.gto,.gbo,.gtp,.gbp,.gm1,.drl'.split(','))
        for name in names:
            fa, fb = os.path.join(scratch, name), os.path.join(OUTROOT, name)
            if not os.path.isdir(fb):
                artwork_bad.append(f'{name}: absent from commit')
                continue
            for f in sorted(set(os.listdir(fa)) | set(os.listdir(fb))):
                if not f.endswith(ext):
                    continue
                pa, pb = os.path.join(fa, f), os.path.join(fb, f)
                if not (os.path.exists(pa) and os.path.exists(pb)):
                    artwork_bad.append(f'{name}/{f}: present on one side only')
                elif geom_parse(pa) != geom_parse(pb):
                    artwork_bad.append(f'{name}/{f}: ARTWORK DIFFERS')
        if artwork_bad:
            print('  VERDICT: STALE — the artwork itself changed:')
            for line in artwork_bad:
                print(f'    {line}')
            return 1
        print('  VERDICT: ARTWORK-IDENTICAL, BYTES DIFFER — the same features are drawn,')
        print('           but text stamps or the exported layer LIST differ. Not green:')
        print('           the committed package is not what this builder emits.')
        return 1


def run_builds(args, names, outroot=None):
    outroot = outroot or OUTROOT
    results = []
    if 'carrier' in names:
        results.append(build(
            'carrier', CARRIER, {},
            'Solar cell carrier. Six solar-cell solder lands: SC1-SC3 on the front face and\n'
            'SC4-SC6 on the back face at the same X centres (ADR-065 parallel string), so the\n'
            'coincident bounding boxes are one cell seen from both sides, not a duplicated part.\n\n'
            'The cells have no LCSC number, so this is ordered as a BARE PCB and the cells are\n'
            'soldered by hand -- which is the purpose of the board.\n\n'
            'Two nets are single-pad by design: `GND` (no plane on this board) and `RF_FEED`\n'
            '(ADR-046 s2.4 V2 provision land).', outroot=outroot))
    if 'interconnect' in names:
        results.append(build(
            'interconnect', INTERCON, JLC_PARTS,
            'Per-wing bypass interconnect. Three SS24 (SMA) diodes across the cell string:\n'
            'SOLAR_P - SOLAR_MID1 - SOLAR_MID2 - SOLAR_N.\n\n'
            'These are NOT duplicates of the hub D_BP1..4: the hub carries bypass BETWEEN wings\n'
            '(W1_P..W1_N..W2_N..W3_N..GND) while this board carries PER-CELL bypass inside one wing.',
            outroot=outroot))
    provenance(outroot)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify-only', action='store_true',
                    help='alias for --check (kept for existing callers)')
    ap.add_argument('--check', action='store_true',
                    help='rebuild to scratch and prove the committed package matches; writes nothing')
    ap.add_argument('--interconnect-only', action='store_true', help='Leave carrier artifacts untouched')
    ap.add_argument('--out', help='write the package here instead of docs/fab/wing-order')
    args = ap.parse_args()

    names = ['interconnect'] if args.interconnect_only else ['carrier', 'interconnect']
    if args.check or args.verify_only:
        return check(args, names)

    results = run_builds(args, names, outroot=args.out)
    print("\n=== summary ===")
    for r in results:
        print(f"  {r['name']:<14} board {r['board']}  {r['holes']} holes  {os.path.basename(r['zip'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
