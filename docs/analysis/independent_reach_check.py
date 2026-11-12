"""Independent check of the four-pair reachability loss on the LIVE board.

CLAIM (commit 1ed9cf9d): batch SPI1SCK_UC closed 3 opens (35 -> 32) but destroyed
reachability for FOUR pairs: /SPI1_MOSI U3.4<->U_C.4, /SPI1_MISO U3.3<->U_C.3,
+3V3 J_VCC.3<->U_C.1, +3V3 U3.1<->U_C.1.

This does not reuse their gate. It floods free space on the BEFORE board and the
AFTER board independently, with my own Collide-only field, and reports whether each
pair's two endpoints share a component. BEFORE = baseline/board.kicad_pcb,
AFTER = latest.kicad_pcb.

Read-only: opens nothing for writing.
"""
import pcbnew as p
import json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path('/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')))
import collide_router as R

BASE = HERE / 'bulk-route-20261107'
# Default: the batch's OWN before/after pair, which is what the claim was measured on.
BATCH = os.environ.get('BATCH_DIR')
if BATCH:
    BEFORE = BASE / BATCH / 'board.kicad_pcb'
    AFTER = BASE / BATCH / 'routed.kicad_pcb'
else:
    BEFORE = BASE / 'baseline' / 'board.kicad_pcb'
    AFTER = BASE / 'latest.kicad_pcb'

BOARD = (0, 0, 160000000, 160000000)      # generous; real outline is read from the board
CLEAR = int(os.environ.get('CLEAR', '200000'))
CAP = int(os.environ.get('CAP', '900000'))

PAIRS = [
    ('/SPI1_MOSI', 'U3', '4', 'U_C', '4'),
    ('/SPI1_MISO', 'U3', '3', 'U_C', '3'),
    ('+3V3', 'J_VCC', '3', 'U_C', '1'),
    ('+3V3', 'U3', '1', 'U_C', '1'),
]


def pad_pos(board, ref, num):
    for f in board.GetFootprints():
        if f.GetReference() != ref:
            continue
        for q in f.Pads():
            if q.GetNumber() == num:
                return q
    return None


def flood(field, pad, net, outline, cap=CAP):
    x0, y0, x1, y1 = outline
    c = pad.GetPosition()
    # SEED ONLY THE PAD'S OWN COPPER LAYERS. Seeding F.Cu at a B.Cu SMD pad silently
    # assumes a via IN THE PAD (drill-in-pad), which is forbidden by the frozen rules
    # and was the exact flaw that made open 31 look connected earlier. Layer changes
    # are still allowed anywhere ALONG the route, just not at the terminal.
    own = [l for l in (p.F_Cu, p.B_Cu) if pad.IsOnLayer(l)] or [p.F_Cu, p.B_Cu]
    seeds = []
    for l in own:
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                nx, ny = c.x + dx * R.GRID, c.y + dy * R.GRID
                if x0 <= nx <= x1 and y0 <= ny <= y1 and field.track_ok(nx, ny, l, net):
                    seeds.append((nx, ny, l))
    seen, stack = set(seeds), list(seeds)
    while stack and len(seen) < cap:
        cx, cy, l = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = cx + dx * R.GRID, cy + dy * R.GRID
            if not (x0 <= nx <= x1 and y0 <= ny <= y1):
                continue
            k = (nx, ny, l)
            if k in seen:
                continue
            if field.track_ok(nx, ny, l, net):
                seen.add(k)
                stack.append(k)
        other = p.B_Cu if l == p.F_Cu else p.F_Cu
        k2 = (cx, cy, other)
        if k2 not in seen and field.via_ok(cx, cy, net) and field.track_ok(cx, cy, other, net):
            seen.add(k2)
            stack.append(k2)
    return seen


def main():
    print('BEFORE:', BEFORE)
    print('AFTER :', AFTER)
    if not AFTER.exists():
        print('AFTER board not found, aborting')
        return
    out = {}
    for tag, path in (('BEFORE', BEFORE), ('AFTER', AFTER)):
        b = p.LoadBoard(str(path))
        op = p.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(op)
        bb = op.BBox()
        outline = (bb.GetLeft() - 1000000, bb.GetTop() - 1000000,
                   bb.GetRight() + 1000000, bb.GetBottom() + 1000000)
        boardsize = ((bb.GetRight() - bb.GetLeft()) / 1e6, (bb.GetBottom() - bb.GetTop()) / 1e6)
        field = R.Field(b, outline, CLEAR)
        print('\n%s  board %.1f x %.1f mm' % (tag, *boardsize))
        rows = {}
        for net, r1, n1, r2, n2 in PAIRS:
            pa, pb = pad_pos(b, r1, n1), pad_pos(b, r2, n2)
            if pa is None or pb is None:
                print('   %-12s %s.%s <-> %s.%s : PAD NOT FOUND' % (net, r1, n1, r2, n2))
                rows[net] = {'found': False}
                continue
            A = flood(field, pa, net, outline)
            B = flood(field, pb, net, outline)
            same = bool(A & B)
            rows[net] = {'found': True, 'reachable': same,
                         'cells_a': len(A), 'cells_b': len(B),
                         'capped': len(A) >= CAP or len(B) >= CAP}
            print('   %-12s %s.%s <-> %s.%s : reachable=%-5s cells %d / %d%s'
                  % (net, r1, n1, r2, n2, same, len(A), len(B),
                     '  (capped)' if rows[net]['capped'] else ''))
        out[tag] = rows

    print('\nDELTA (reachable BEFORE -> AFTER):')
    lost = []
    for net, *_ in PAIRS:
        b = out['BEFORE'].get(net, {}).get('reachable')
        a = out['AFTER'].get(net, {}).get('reachable')
        if b is True and a is False:
            lost.append(net)
            print('   LOST  %s' % net)
        elif b != a:
            print('   CHANGED %s : %s -> %s' % (net, b, a))
    print('\nlost pairs: %d  %s' % (len(lost), lost))
    (HERE / 'independent-reach-check.json').write_text(json.dumps({'before': out['BEFORE'],
                                                                   'after': out['AFTER'],
                                                                   'lost': lost}, indent=2))


if __name__ == '__main__':
    main()
