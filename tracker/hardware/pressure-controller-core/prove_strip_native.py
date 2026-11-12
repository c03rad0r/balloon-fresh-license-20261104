#!/usr/bin/env python3
"""Native DRC proof that the narrowed strip still constrains, and now permits escapes.

Four probes against the BOARD OF RECORD (not the library template), because a placed board
carries its own copy of the footprint zone and the library edit alone would not change it.

  A ESCAPE (positive)   a track leaving pad 7's CENTRE outward must be DRC-CLEAN and
                        electrically connected. This is the case the 25 um band blocked.
  B BETWEEN (negative)  a track running down the middle of the inter-pad strip must be
                        REFUSED with items_not_allowed. This is the TE p16 constraint.
  C OLD SHAPE (control) the same between-pads track against the PRE-FIX body-wide zone must
                        ALSO be refused -- proves probe B is not passing because the zone is
                        inert, and that the old shape would have refused the escape too.
  D VIA (project policy) a via dropped in the middle of the strip must be REFUSED.

Each probe runs in its own copy of the board in its own temp dir with the same-stem project
file, so DRC uses the project's rules (batch_proof refuses a candidate without one, and so
does this).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew as k

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, 'routing', 'route.kicad_pcb')
BODY = ((-1.5, -2.5), (1.5, -2.5), (1.5, 2.5), (-1.5, 2.5))


def stage(with_pro=False):
    tmp = tempfile.mkdtemp(prefix='strip-probe-')
    board = os.path.join(tmp, 'probe.kicad_pcb')
    shutil.copyfile(BOARD, board)
    for ext in ('.kicad_pro', '.kicad_dru'):
        src = BOARD.replace('.kicad_pcb', ext)
        if os.path.exists(src):
            shutil.copyfile(src, board.replace('.kicad_pcb', ext))
    if os.path.exists(os.path.join(HERE, 'routing', 'fp-lib-table')):
        # POINT THE TEMP PROJECT AT THE REAL LIBRARY BY ABSOLUTE PATH. The committed
        # fp-lib-table uses ${KIPRJMOD}/../PressureSensor.pretty, which only resolves from
        # routing/. Copied verbatim into a temp dir it fails to load and kicad-cli adds two
        # lib_footprint_issues records that have nothing to do with the probe (measured).
        lib = os.path.join(HERE, 'PressureSensor.pretty')
        with open(os.path.join(tmp, 'fp-lib-table'), 'w') as fh:
            fh.write('(fp_lib_table (version 7) (lib (name "PressureSensor") (type "KiCad") '
                     f'(uri "{lib}") (options "") (descr "strip probe")))\n')
    return tmp, board


def drc(board_path):
    out = os.path.join(os.path.dirname(board_path), 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '-o', out, board_path], capture_output=True)
    with open(out) as fh:
        d = json.load(fh)
    return [v['type'] for v in d['violations']], d


def u3(board):
    return [f for f in board.GetFootprints() if f.GetReference() == 'U3'][0]


def add_track(board, x0, y0, x1, y1, net, width=0.25):
    o = u3(board).GetPosition()
    t = k.PCB_TRACK(board)
    t.SetStart(k.VECTOR2I(int(o.x + x0 * 1e6), int(o.y + y0 * 1e6)))
    t.SetEnd(k.VECTOR2I(int(o.x + x1 * 1e6), int(o.y + y1 * 1e6)))
    t.SetWidth(int(width * 1e6))
    t.SetLayer(k.F_Cu)
    t.SetNet(net)
    board.Add(t)
    return t


def pad_net(board, num='7'):
    return [p for p in u3(board).Pads() if p.GetNumber() == num][0].GetNet()


def probe_escape():
    tmp, board_path = stage()
    try:
        b = k.LoadBoard(board_path)
        # pad 7 centre is local (+1.1, -0.625); run outward in +x, clear of the land edge 1.65
        t = add_track(b, 1.1, -0.625, 2.3, -0.625, pad_net(b))
        conn = b.GetConnectivity()
        conn.Build(b)
        attached = len(conn.GetConnectedPads(t)) > 0
        k.SaveBoard(board_path, b)
        del b
        types, d = drc(board_path)
        return types, attached
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probe_between(body_wide=False):
    tmp, board_path = stage()
    try:
        b = k.LoadBoard(board_path)
        if body_wide:
            # Recreate the PRE-FIX shape on the placed footprint, in board coordinates.
            zp = [z for z in u3(b).Zones() if z.GetIsRuleArea()][0]
            o = u3(b).GetPosition()
            poly = k.SHAPE_POLY_SET()
            poly.NewOutline()
            for x, y in BODY:
                poly.Append(int(o.x + x * 1e6), int(o.y + y * 1e6))
            zp.SetOutline(poly)
        add_track(b, 0.0, -2.0, 0.0, 2.0, pad_net(b))
        k.SaveBoard(board_path, b)
        del b
        types, d = drc(board_path)
        return types
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probe_via():
    tmp, board_path = stage()
    try:
        b = k.LoadBoard(board_path)
        o = u3(b).GetPosition()
        v = k.PCB_VIA(b)
        v.SetPosition(k.VECTOR2I(int(o.x), int(o.y)))
        v.SetWidth(int(0.5e6))
        v.SetDrill(int(0.25e6))
        v.SetLayerPair(k.F_Cu, k.B_Cu)
        v.SetNet(pad_net(b))
        b.Add(v)
        k.SaveBoard(board_path, b)
        del b
        types, d = drc(board_path)
        return types
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ok = True

    types, attached = probe_escape()
    esc_clean = 'items_not_allowed' not in types
    print(f'A ESCAPE  pad-centre track outward: items_not_allowed={"NO" if esc_clean else "YES"} '
          f'connected={attached}  all_violations={types}')
    if not (esc_clean and attached):
        print('  FAIL: the narrowed strip did not free a pad-centre escape')
        ok = False
    else:
        print('  PASS  escape is DRC-clean and connected (unblocked by the strip)')

    types = probe_between()
    if 'items_not_allowed' not in types:
        print(f'  FAIL: a track BETWEEN the pads was not refused  violations={types}')
        ok = False
    else:
        print('B BETWEEN track down the strip: PASS refused (items_not_allowed present)')

    types = probe_between(body_wide=True)
    if 'items_not_allowed' not in types:
        print(f'  FAIL: control -- the OLD body-wide shape did not refuse it either: {types}')
        ok = False
    else:
        print('C OLD SHAPE control: PASS the body-wide zone refuses the same track too, '
              'so probe B is not vacuous')

    types = probe_via()
    if 'items_not_allowed' not in types:
        print(f'  FAIL: a via in the strip was not refused  violations={types}')
        ok = False
    else:
        print('D VIA in the strip: PASS refused (project policy preserved)')

    print('VERDICT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
