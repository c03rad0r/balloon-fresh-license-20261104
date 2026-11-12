"""Is there free F.Cu room to move D_BP1..D_BP4 to the top side?

The four SS24 bypass diodes currently sit on B.Cu at the four wing entry points. Moving them
to F.Cu would avoid JLC's second-side setup fee, but only if there is actual free copper area
where they can go AND the two nets they join are reachable.

This measures, for each diode:
  - its current pads, nets and the copper already on those nets per layer
  - the free F.Cu area in a disc around its present position (obstacles = pads of other nets,
    tracks on F.Cu, footprints on the top side)
  - the nearest F.Cu copper of each of the two nets it has to join

It does NOT move anything. A placement change on this board is an ADR-120 R3 gate.
"""
import math

import pcbnew

BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
MM = 1e6
b = pcbnew.LoadBoard(BD)


def S(x):
    return str(x)


# ---- collect F.Cu obstacles: every pad and track not on the diode's own nets
diode_nets = {}
for ref in ('D_BP1', 'D_BP2', 'D_BP3', 'D_BP4'):
    fp = next(f for f in b.GetFootprints() if f.GetReference() == ref)
    diode_nets[ref] = {S(p.GetNetname()) for p in fp.Pads() if S(p.GetNetname())}

obstacles = []          # (x, y, radius_or_halfextent, kind)
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref.startswith('D_BP'):
        continue
    for p in fp.Pads():
        pos = p.GetPosition()
        sz = p.GetSize()
        r = max(sz.x, sz.y) / 2 / MM
        obstacles.append((pos.x / MM, pos.y / MM, r, f'pad {ref}.{S(p.GetNumber())}', S(p.GetNetname())))

for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        continue
    if t.GetLayer() != pcbnew.F_Cu:
        continue
    s, e = t.GetStart(), t.GetEnd()
    obstacles.append(((s.x + e.x) / 2 / MM, (s.y + e.y) / 2 / MM,
                      math.hypot(e.x - s.x, e.y - s.y) / 2 / MM, 'track F.Cu', S(t.GetNetname())))

print(f'F.Cu obstacle entries: {len(obstacles)}\n')

# ---- per diode: free area + nearest same-net copper
for ref in ('D_BP1', 'D_BP2', 'D_BP3', 'D_BP4'):
    fp = next(f for f in b.GetFootprints() if f.GetReference() == ref)
    pos = fp.GetPosition()
    cx, cy = pos.x / MM, pos.y / MM
    own = diode_nets[ref]
    mynets = {e[4] for e in obstacles if e[4] in own}

    print(f'{ref}  at ({cx:6.2f},{cy:6.2f})  nets={sorted(own)}')

    # scan a 14 mm disc on F.Cu for free spots big enough for an SMA (4.3 x 2.6 body)
    RAD = 7.0
    STEP = 0.5
    NEED = 2.2          # half of the SMA's long dimension plus margin
    best = None
    for dx in [(-RAD + i * STEP) for i in range(int(2 * RAD / STEP) + 1)]:
        for dy in [(-RAD + j * STEP) for j in range(int(2 * RAD / STEP) + 1)]:
            x, y = cx + dx, cy + dy
            if not (2 <= x <= 70 and 2 <= y <= 78):
                continue
            clear = True
            mind = 99.0
            for ox, oy, orr, kind, net in obstacles:
                d = math.hypot(ox - x, oy - y) - orr
                if d < NEED:
                    clear = False
                    break
                mind = min(mind, d)
            if clear and (best is None or mind > best[2]):
                best = (x, y, mind)
    if best:
        print(f'   free F.Cu spot: ({best[0]:6.2f},{best[1]:6.2f})  clearance {best[2]:.2f} mm')
    else:
        print(f'   NO free F.Cu spot within {RAD} mm for an SMA body')

    # nearest F.Cu copper for each of the two nets it must join
    for net in sorted(own):
        fcu = [e for e in obstacles if e[4] == net]
        bcu_tracks = [t for t in b.GetTracks()
                      if S(t.GetNetname()) == net and t.GetLayer() == pcbnew.B_Cu
                      and t.GetClass() != 'PCB_VIA']
        vias = [t for t in b.GetTracks()
                if S(t.GetNetname()) == net and t.GetClass() == 'PCB_VIA']
        if fcu:
            dmin = min(math.hypot(e[0] - cx, e[1] - cy) - e[2] for e in fcu)
            where = 'F.Cu already present'
        elif vias:
            dmin = min(math.hypot(v.GetPosition().x / MM - cx, v.GetPosition().y / MM - cy) for v in vias)
            where = 'reachable via an existing VIA'
        else:
            dmin = float('inf')
            where = 'B.Cu only -- needs a new via'
        print(f'   net {net:16s} F.Cu copper: {dmin:6.2f} mm from centre  ({where})')

    # what is actually on the top side right here
    near = [e for e in obstacles
            if math.hypot(e[0] - cx, e[1] - cy) < 5.0 and e[4] != 'None']
    if near:
        names = sorted({e[3] for e in near})[:6]
        print(f'   top-side neighbours within 5 mm: {names}')
    print()
