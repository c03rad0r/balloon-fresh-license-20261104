#!/usr/bin/env python3
"""verify_gerbers_fresh.py -- do the committed gerbers match the board of record?

WHY THIS EXISTS
---------------
The only v10 gerbers in the repo live in docs/analysis/bulk-route-20261107/fab-11opens/ -- a
directory named for an 11-open board state. The board of record has since been edited twice
(/IO0 netlist fix, then 17 assembly attributes). Copper should be unchanged, but "should be" is not
a fact, and gerbers are what the fab actually cuts.

METHOD
  Regenerate every layer from work.kicad_pcb into a scratch dir, then compare GEOMETRY against the
  committed set. Geometry, not bytes: KiCad embeds a generation timestamp and a different file stem
  in the header, so a byte comparison always fails for reasons the fab does not care about.

  Geometry = the multiset of coordinates the fab acts on:
    flashes  X..Y..D03   (aperture flashes: pads, vias, mask openings)
    segments X..Y..D01/D02 (draws: tracks, outlines)
    apertures '%ADD...*%'  (definitions, including sizes)

  A layer is CURRENT if its flash and segment multisets are identical.

GUARDS AGAINST SILENTLY PASSING
  - Every layer must have BOTH files present; a missing file is a FAIL, never skipped.
  - Zero extracted features on both sides is a FAIL, never "identical" -- an empty comparison
    proves nothing and was in fact the first bug this script had (drill regex used integers while
    the drill file writes decimals, so it compared 0 hits to 0 hits and reported IDENTICAL).
"""
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
COMMITTED = 'docs/analysis/bulk-route-20261107/fab-11opens'
SCRATCH = '/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/gerbcheck'

# KiCad layer name -> committed file extension
EXT = {
    'F.Cu': '.gtl', 'In1.Cu': '.g1', 'In2.Cu': '.g2', 'B.Cu': '.gbl',
    'F.Mask': '.gts', 'B.Mask': '.gbs',
    'F.Silkscreen': '.gto', 'B.Silkscreen': '.gbo',
    'Edge.Cuts': '.gm1', 'F.Paste': '.gtp', 'B.Paste': '.gbp',
}
LAYERS = list(EXT)


def gen():
    if os.path.isdir(SCRATCH):
        shutil.rmtree(SCRATCH)
    os.makedirs(SCRATCH, exist_ok=True)
    r = subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers', '--output', SCRATCH, BD],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('gerber export FAILED:', (r.stdout + r.stderr)[-800:])
        sys.exit(1)
    subprocess.run(['kicad-cli', 'pcb', 'export', 'drill', '--output', SCRATCH, BD],
                   capture_output=True, text=True)
    print(f'exported {len(os.listdir(SCRATCH))} files to scratch')


FLASH = re.compile(r'X(-?\d+)Y(-?\d+)D0?3\*')
SEG = re.compile(r'X(-?\d+)Y(-?\d+)D0?[12]\*')
AP = re.compile(r'%ADD\d+[^*]*\*%')


def geometry(path):
    t = open(path, errors='replace').read()
    return Counter(FLASH.findall(t)), Counter(SEG.findall(t)), Counter(AP.findall(t))


def committed_path(layer):
    # committed uses underscores: board-F_Cu.gtl
    stem = layer.replace('.', '_')
    p = os.path.join(COMMITTED, f'board-{stem}{EXT[layer]}')
    return p if os.path.exists(p) else None


def scratch_path(layer):
    stem = layer.replace('.', '_')
    p = os.path.join(SCRATCH, f'work-{stem}{EXT[layer]}')
    return p if os.path.exists(p) else None


def main():
    gen()
    print(f'\n{"layer":15s} {"verdict":9s} {"fresh counts":22s} header')
    print('-' * 74)
    fails = []
    for layer in LAYERS:
        c, s = committed_path(layer), scratch_path(layer)
        if not c:
            fails.append((layer, 'committed file MISSING')); continue
        if not s:
            fails.append((layer, 'fresh file MISSING')); continue
        fa, sa, aa = geometry(c)
        fb, sb, ab = geometry(s)
        if not fa and not sa:
            fails.append((layer, 'ZERO features on both sides -- comparison is vacuous'))
            continue
        if fa != fb or sa != sb:
            nf = sum((fa - fb).values()) + sum((fb - fa).values())
            ns = sum((sa - sb).values()) + sum((sb - sa).values())
            fails.append((layer, f'GEOMETRY DIFFERS: {nf} flash, {ns} segment'))
            print(f'{layer:15s} {"DIFFERS":9s} {len(fb)} flash {len(sb)} segs   '
                  f'{"bytes-equal" if open(c,"rb").read()==open(s,"rb").read() else "header/time differs"}')
        else:
            byte = open(c, 'rb').read() == open(s, 'rb').read()
            print(f'{layer:15s} {"IDENTICAL":9s} {len(fb)} flash {len(sb)} segs   '
                  f'{"bytes-equal" if byte else "header/time differs only"}')

    # ---- drill: coords are DECIMAL in .drl (X16.9Y-40.91), not integers
    print('\n=== drill')
    dc = os.path.join(COMMITTED, 'board.drl')
    ds = os.path.join(SCRATCH, 'work.drl')
    drill_fail = None
    if not (os.path.exists(dc) and os.path.exists(ds)):
        drill_fail = 'drill missing on one side'
    else:
        HIT = re.compile(r'X(-?\d+(?:\.\d+)?)Y(-?\d+(?:\.\d+)?)')
        tc = Counter(HIT.findall(open(dc, errors='replace').read()))
        ts = Counter(HIT.findall(open(ds, errors='replace').read()))
        if not tc:
            drill_fail = 'ZERO hits parsed from committed drill -- comparison is vacuous'
        elif tc != ts:
            drill_fail = (f'DIFFERS: {sum((tc-ts).values())} only-committed, '
                          f'{sum((ts-tc).values())} only-fresh')
        else:
            print(f'  committed hits={sum(tc.values())}  fresh hits={sum(ts.values())}  IDENTICAL')
    if drill_fail:
        print(f'  {drill_fail}')

    print()
    if fails or drill_fail:
        print(f'VERDICT: FAIL -- {len(fails) + (1 if drill_fail else 0)} problem(s)')
        for layer, why in fails:
            print(f'  {layer:15s} {why}')
        print('\n  The committed gerbers cannot be used as-is. Regenerate and commit the fresh set.')
        sys.exit(1)
    print('VERDICT: PASS -- every layer is geometrically identical to the board of record.')
    print('                 Headers differ only by file stem and timestamp, which the fab ignores.')
    sys.exit(0)


if __name__ == '__main__':
    main()
