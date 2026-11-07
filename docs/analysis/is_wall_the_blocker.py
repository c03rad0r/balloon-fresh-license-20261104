"""Does REMOVING the /SPI1_SCK wall restore /SPI1_MISO and /SPI1_MOSI?

The wall is a single B.Cu track: (35.250,13.650)->(35.250,16.250), 2.60 mm, /SPI1_SCK.
Two batches have now re-created walls trying to route that net. Before spending more
compute on it, measure whether those two nets are actually gated by this copper.

Method: take the pre-batch board (which has NO /SPI1_SCK wall), and flood
/SPI1_MISO and /SPI1_MOSI pairs seed-correctly on the pad's own copper layers.
This is the BEFORE case of the reachability gate, run alone, so it answers a
different and more useful question than "did a batch break something":
IS THERE A CLEAN PATH TODAY?

Read-only.
"""
import pcbnew as p
import json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path('/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')))
import collide_router as R

BASE = HERE / 'bulk-route-20261107'
BOARD_PATH = BASE / os.environ.get('BOARD', 'batches/SPI1SCK_UC/board.kicad_pcb')
CLEAR = int(os.environ.get('CLEAR', '200000'))
CAP = int(os.environ.get('CAP', '1500000'))

PAIRS = [
    ('/SPI1_MISO', 'U3', '3', 'U_C', '3'),
    ('/SPI1_MOSI', 'U3', '4', 'U_C', '4'),
]


def pad_of(b, ref, num):
    for f in b.GetFootprints():
        if f.GetReference() == ref:
            for q in f.Pads():
                if q.GetNumber() == num:
                    return q
    return None


def flood(field, pad, net, box, cap=CAP):
    x0, y0, x1, y1 = box
    c = pad.GetPosition()
    own = [l for l in (p.F_Cu, p.B_Cu, p.In1_Cu, p.In2_Cu) if pad.IsOnLayer(l)] or [p.F_Cu]
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
    return seen, own


def main():
    b = p.LoadBoard(str(BOARD_PATH))
    op = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(op)
    bb = op.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    field = R.Field(b, box, CLEAR)
    print('board: %s' % BOARD_PATH)
    print('clearance: %.3f mm   (0.200 rule%s)' % (CLEAR / 1e6,
          '' if CLEAR == 200000 else ' + guard'))

    walls = [(t.GetStart(), t.GetEnd(), t.GetNetname(), b.GetLayerName(t.GetLayer()))
             for t in b.GetTracks()
             if not isinstance(t, p.PCB_VIA) and t.GetNetname() == '/SPI1_SCK']
    print('/SPI1_SCK tracks present: %d' % len(walls))

    for net, r1, n1, r2, n2 in PAIRS:
        pa, pb = pad_of(b, r1, n1), pad_of(b, r2, n2)
        if not pa or not pb:
            print('  %s: pad missing' % net)
            continue
        A, own_a = flood(field, pa, net, box)
        B, own_b = flood(field, pb, net, box)
        same = bool(A & B)
        import math
        best = None
        if not same and A and B:
            for k in list(A)[:3000]:
                for k2 in list(B)[:3000]:
                    d = math.hypot(k[0] - k2[0], k[1] - k2[1])
                    if best is None or d < best:
                        best = d
        print('  %-12s %s.%s <-> %s.%s  seeds on %s  reachable=%-5s  cells %d / %d%s'
              % (net, r1, n1, r2, n2,
                 ','.join(b.GetLayerName(l) for l in own_a),
                 same, len(A), len(B),
                 '' if same or best is None else '  nearest %.4f mm' % (best / 1e6)))


if __name__ == '__main__':
    main()
