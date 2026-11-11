#!/usr/bin/env python3
"""Option A: the MS5611 keep-out must be the strip BETWEEN the pads, not the whole body.

THE DEFECT (measured 2026-11-10, native DRC on compact.kicad_pcb): the project-local footprint
carries an F.Cu rule area over the nominal 3 x 5 mm body. All eight pads sit inside it, so every
track anchored at a PAD CENTRE is reported `items_not_allowed` -- 3 of 3 probes. The only legal
anchor band is 25 um, because the lands protrude 1.650 - 1.500 = 0.150 mm and a 0.25 mm track's
round end-cap radius (0.125 mm) consumes all but 0.025 mm of it.

TE p16 forbids tracks BETWEEN pads. The body-wide rule area also bans them OVER the pads, which is
the over-reach. Option A narrows the rule area to the inter-pad strip (2 x 0.55 = 1.10 mm) so the
cited constraint is still enforced while every pad becomes routable.

WHAT THIS FILE PINS, and each check must be able to FAIL:
  1. the keep-out is the inter-pad strip, on the four expected edges;
  2. the keep-out still forbids tracks/vias/pours (the TE constraint survives the edit);
  3. every pad CENTRE is outside the keep-out -- i.e. the footprint is routable at all;
  4. a pad-centre escape is now accepted by native DRC and is electrically connected;
  5. the keep-out still blocks a track that runs BETWEEN the pads.
Negative controls prove 1 and 3 are not vacuous: a body-wide keep-out (the old shape) must be
rejected, and a keep-out so narrow it no longer separates the columns must be rejected.
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew as k                                              # noqa: E402

NAME = 'MS5611-01BA03_TE_Recommended'
LIB = os.path.join(HERE, 'PressureSensor.pretty', NAME + '.kicad_mod')
BOARD = os.path.join(HERE, 'compact', 'compact.kicad_pcb')

# measured geometry (see FOOTPRINT-REPORT.md and draw_keepout_conflict.py)
PAD_INNER = 0.55          # inner edge of a pad column  = strip half-width
BODY_H = 2.5              # nominal body half-height
TOL = 1e-4


def require(cond, msg):
    if not cond:
        raise ValueError(msg)


def strip_box(z):
    """Return the zone's rectangle in footprint-local mm as (x0, y0, x1, y1)."""
    require(z.GetIsRuleArea(), 'zone is a rule area')
    pts = []
    for i in range(z.Outline().OutlineCount()):
        pts += [(p.x / 1e6, p.y / 1e6) for p in z.Outline().Outline(i).CPoints()]
    require(pts, 'zone has an outline')
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def check_local(fp):
    """Assertions 1-3, on a footprint object (library or embedded).

    A LIBRARY footprint stores its zone in footprint-local coordinates; a zone EMBEDDED in a placed
    board stores absolute board coordinates. Both must be checked against the same intent, so the
    expected rectangle is expressed in local terms and translated by the footprint origin.
    """
    zones = [z for z in fp.Zones() if z.GetIsRuleArea()]
    require(len(zones) == 1, f'exactly one rule area, found {len(zones)}')
    z = zones[0]

    # 2. the cited constraint must SURVIVE the narrowing
    require(z.GetDoNotAllowTracks(), 'keep-out still forbids tracks between pads')
    require(z.GetDoNotAllowVias(), 'keep-out still forbids vias between pads')
    require(z.GetDoNotAllowCopperPour(), 'keep-out still forbids pours between pads')
    require(set(z.GetLayerSet().Seq()) == {k.F_Cu}, 'keep-out is F.Cu only')

    # 1. it must be the inter-pad strip, not the body -- in the footprint's own frame
    x0, y0, x1, y1 = strip_box(z)
    o = fp.GetPosition()
    ox, oy = o.x / 1e6, o.y / 1e6
    lx0, lx1, ly0, ly1 = x0 - ox, x1 - ox, y0 - oy, y1 - oy
    require(abs(lx0 + PAD_INNER) < TOL, f'strip left edge {-PAD_INNER}, got {lx0}')
    require(abs(lx1 - PAD_INNER) < TOL, f'strip right edge +{PAD_INNER}, got {lx1}')
    require(abs(ly0 + BODY_H) < TOL, f'strip bottom {-BODY_H}, got {ly0}')
    require(abs(ly1 - BODY_H) < TOL, f'strip top +{BODY_H}, got {ly1}')

    # 3. every pad centre must be OUTSIDE it, or the footprint cannot be routed at all
    for p in fp.Pads():
        require(p.GetNumber(), 'pad has a number')
        c = p.GetPosition()
        cx, cy = c.x / 1e6 - ox, c.y / 1e6 - oy      # footprint frame
        inside = lx0 - TOL <= cx <= lx1 + TOL and ly0 - TOL <= cy <= ly1 + TOL
        require(not inside,
                f'pad {p.GetNumber()} centre ({cx:.3f},{cy:.3f}) is inside the keep-out')


def check_board():
    """Assertion 3 again, on the placed footprints, plus the embedded copies."""
    b = k.LoadBoard(BOARD)
    seen = 0
    for ref in ('U3', 'U4'):
        fp = [f for f in b.GetFootprints() if f.GetReference() == ref]
        require(len(fp) == 1, f'{ref} present once')
        seen += 1
        check_local(fp[0])
        # the EMBEDDED copy is what the router and DRC actually read; editing the library alone
        # changes nothing on an existing board. Assert both agree.
        z = [z for z in fp[0].Zones() if z.GetIsRuleArea()][0]
        x0, _, x1, _ = strip_box(z)
        o = fp[0].GetPosition()
        require(abs((x0 - o.x / 1e6) + PAD_INNER) < TOL
                and abs((x1 - o.x / 1e6) - PAD_INNER) < TOL,
                f'{ref} embedded keep-out is not the inter-pad strip')
    require(seen == 2, 'both sensor ports checked')
    return b


def escape_drc(centre=True):
    """Route an outward escape from pad 8 and return the DRC violation types."""
    tmp = tempfile.mkdtemp()
    try:
        board_path = os.path.join(tmp, 'probe.kicad_pcb')
        shutil.copyfile(BOARD, board_path)
        for ext in ('.kicad_pro', '.kicad_dru'):
            src = BOARD.replace('.kicad_pcb', ext)
            if os.path.exists(src):
                shutil.copyfile(src, board_path.replace('.kicad_pcb', ext))
        if os.path.exists(os.path.join(HERE, 'compact', 'fp-lib-table')):
            shutil.copyfile(os.path.join(HERE, 'compact', 'fp-lib-table'),
                            os.path.join(tmp, 'fp-lib-table'))

        b = k.LoadBoard(board_path)
        fp = [f for f in b.GetFootprints() if f.GetReference() == 'U3'][0]
        o = fp.GetPosition()
        pad = [p for p in fp.Pads() if p.GetNumber() == '8'][0]
        # pad 8 sits at local (+1.1, -1.875); pads run outward in +x
        sx = 1.1 if centre else 1.63
        t = k.PCB_TRACK(b)
        t.SetStart(k.VECTOR2I(int(o.x + sx * 1e6), int(o.y - 1.875e6)))
        t.SetEnd(k.VECTOR2I(int(o.x + (sx + 1.2) * 1e6), int(o.y - 1.875e6)))
        t.SetWidth(int(0.25e6))
        t.SetLayer(k.F_Cu)
        t.SetNet(pad.GetNet())
        b.Add(t)

        conn = b.GetConnectivity()
        conn.Build(b)
        attached = len(conn.GetConnectedPads(t)) > 0
        k.SaveBoard(board_path, b)
        del b

        out = os.path.join(tmp, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                        '-o', out, board_path], capture_output=True)
        data = json.load(open(out))
        types = [v['type'] for v in data['violations']]
        return types, attached
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_escape_is_legal():
    """Assertion 4: a pad-centre escape must now be clean AND actually connected."""
    types, attached = escape_drc(centre=True)
    require('items_not_allowed' not in types,
            'pad-centre escape still hits the keep-out: ' + ','.join(types))
    require(attached, 'escape track is not electrically connected to pad 8')


def check_between_pads_still_blocked():
    """Assertion 5: a track running between the columns must STILL be refused."""
    tmp = tempfile.mkdtemp()
    try:
        board_path = os.path.join(tmp, 'probe.kicad_pcb')
        shutil.copyfile(BOARD, board_path)
        for ext in ('.kicad_pro', '.kicad_dru'):
            src = BOARD.replace('.kicad_pcb', ext)
            if os.path.exists(src):
                shutil.copyfile(src, board_path.replace('.kicad_pcb', ext))
        if os.path.exists(os.path.join(HERE, 'compact', 'fp-lib-table')):
            shutil.copyfile(os.path.join(HERE, 'compact', 'fp-lib-table'),
                            os.path.join(tmp, 'fp-lib-table'))
        b = k.LoadBoard(board_path)
        fp = [f for f in b.GetFootprints() if f.GetReference() == 'U3'][0]
        o = fp.GetPosition()
        pad = [p for p in fp.Pads() if p.GetNumber() == '8'][0]
        t = k.PCB_TRACK(b)
        # straight down the middle of the inter-pad gap
        t.SetStart(k.VECTOR2I(int(o.x), int(o.y - 2.0e6)))
        t.SetEnd(k.VECTOR2I(int(o.x), int(o.y + 2.0e6)))
        t.SetWidth(int(0.25e6))
        t.SetLayer(k.F_Cu)
        t.SetNet(pad.GetNet())
        b.Add(t)
        k.SaveBoard(board_path, b)
        del b
        out = os.path.join(tmp, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                        '-o', out, board_path], capture_output=True)
        types = [v['type'] for v in json.load(open(out))['violations']]
        require('items_not_allowed' in types,
                'a track run BETWEEN the pads was NOT refused -- the TE constraint is gone')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def negative_controls():
    """Prove the geometry checks can fail."""
    b = k.LoadBoard(BOARD)
    fp = [f for f in b.GetFootprints() if f.GetReference() == 'U3'][0]
    z = [x for x in fp.Zones() if x.GetIsRuleArea()][0]

    # control 1: the OLD body-wide shape must be rejected
    saved = k.SHAPE_POLY_SET(z.Outline())
    body = k.SHAPE_POLY_SET()
    body.NewOutline()
    for x, y in ((-1.5, -2.5), (1.5, -2.5), (1.5, 2.5), (-1.5, 2.5)):
        body.Append(int(x * 1e6), int(y * 1e6))
    z.SetOutline(body)
    try:
        check_local(fp)
    except ValueError as e:
        require('centre' in str(e) or 'edge' in str(e),
                f'body-wide control rejected for the wrong reason: {e}')
        print('REJECT body-wide keep-out (the pre-fix shape)')
    else:
        raise RuntimeError('negative control accepted: body-wide keep-out')
    z.SetOutline(saved)

    # control 2: a keep-out too narrow to separate the columns must be rejected
    narrow = k.SHAPE_POLY_SET()
    narrow.NewOutline()
    for x, y in ((-0.2, -2.5), (0.2, -2.5), (0.2, 2.5), (-0.2, 2.5)):
        narrow.Append(int(x * 1e6), int(y * 1e6))
    z.SetOutline(narrow)
    try:
        check_local(fp)
    except ValueError:
        print('REJECT strip too narrow to separate the pad columns')
    else:
        raise RuntimeError('negative control accepted: over-narrow keep-out')
    z.SetOutline(saved)
    del b


if __name__ == '__main__':
    digest = hashlib.sha256(open(LIB, 'rb').read()).hexdigest()
    lib = k.FootprintLoad(os.path.join(HERE, 'PressureSensor.pretty'), NAME)
    require(lib is not None, 'library footprint loads')
    check_local(lib)
    print(f'PASS library keep-out is the inter-pad strip (sha256 {digest[:16]}...)')

    check_board()
    print('PASS U3/U4 placed and embedded keep-outs match')

    check_between_pads_still_blocked()
    print('PASS a track run between the pads is still refused (TE p16 constraint intact)')

    check_escape_is_legal()
    print('PASS pad-centre escape is DRC-clean and electrically connected')

    negative_controls()
    print('PASS negative controls: body-wide and over-narrow keep-outs both rejected')

    pinned = json.loads(open(os.path.join(HERE, 'library-sha256.json')).read())
    require(pinned['PressureSensor:' + NAME] == digest, 'library-sha256.json still pins this file')
    print('PASS library-sha256.json pin matches the file on disk')
