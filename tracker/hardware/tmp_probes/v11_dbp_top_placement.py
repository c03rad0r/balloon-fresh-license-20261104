"""v11 §1 blocker: find a TOP-side placement for all four wing bypass diodes.

The v11 spec searched a 20x20 mm window with a 2.5 mm pad-to-copper tolerance and found ZERO
candidate sites for D_BP3 -- "/W2_SOLAR_N has 220 F.Cu segments and /W3_SOLAR_N has 314, yet they
occupy opposite halves of the board at that corner."

That conclusion may be a tolerance artefact rather than a geometry fact. This probe re-searches with:
  - a WIDER window (30 mm, not 20)
  - a graded tolerance: report the best achievable per diode at 1.0 / 2.5 / 5.0 / 10.0 mm
  - both rotations, plus 0/90/180/270
  - and, crucially, for each candidate it reports the SHORTEST new copper a route would need, which
    is the number that decides whether "needs new copper" means one stub or a 40 mm trunk.

Method note: distance-to-copper is computed to the NEAREST F.Cu segment of the target net, measured
segment-wise (not centroid-wise). Segments are the real obstacles and the real sources; a centroid
distance flatters a long meandering net.
"""
import math

import pcbnew

BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
MM = 1e6
b = pcbnew.LoadBoard(BD)

DIODES = {
    'D_BP1': ('/W1_SOLAR_P', '/W1_SOLAR_N'),
    'D_BP2': ('/W1_SOLAR_N', '/W2_SOLAR_N'),
    'D_BP3': ('/W2_SOLAR_N', '/W3_SOLAR_N'),
    'D_BP4': ('/W3_SOLAR_N', 'GND'),
}
# SS24 in SMA: pad centres 4.00 mm apart on the long axis.
PAD_SEP = 4.00


def segments_of(net, layer):
    out = []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            continue
        if t.GetLayer() != layer:
            continue
        if str(t.GetNetname()) != net:
            continue
        s, e = t.GetStart(), t.GetEnd()
        out.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM))
    return out


def dist_pt_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def nearest(segs, px, py):
    if not segs:
        return float('inf'), None
    best, where = float('inf'), None
    for x1, y1, x2, y2 in segs:
        d = dist_pt_seg(px, py, x1, y1, x2, y2)
        if d < best:
            best, where = d, (x1, y1, x2, y2)
    return best, where


# obstacles on F.Cu that are NOT the diode's own nets: pads and tracks of everything else
def obstacles(exclude_nets):
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if str(p.GetNetname()) in exclude_nets:
                continue
            pos = p.GetPosition()
            sz = p.GetSize()
            out.append((pos.x / MM, pos.y / MM, max(sz.x, sz.y) / 2 / MM))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            continue
        if t.GetLayer() != pcbnew.F_Cu:
            continue
        if str(t.GetNetname()) in exclude_nets:
            continue
        s, e = t.GetStart(), t.GetEnd()
        out.append(((s.x + e.x) / 2 / MM, (s.y + e.y) / 2 / MM,
                    math.hypot(e.x - s.x, e.y - s.y) / 2 / MM))
    return out


TOLERANCES = [1.0, 2.5, 5.0, 10.0]
WINDOW = 30.0
STEP = 1.0

print(f'board {BD}')
print(f'window +/-{WINDOW/2:.0f} mm around each v10 site, step {STEP} mm, both axes')
print('candidate = both pads land within the stated distance of SAME-NET F.Cu copper,')
print('and the site itself is clear of other nets by >= 2.0 mm\n')

summary = {}
for ref, nets in DIODES.items():
    fp = next(f for f in b.GetFootprints() if f.GetReference() == ref)
    pos = fp.GetPosition()
    cx, cy = pos.x / MM, pos.y / MM
    segsA = segments_of(nets[0], pcbnew.F_Cu)
    segsB = segments_of(nets[1], pcbnew.F_Cu)
    obs = obstacles(set(nets))

    print(f'=== {ref}  v10 at ({cx:.2f},{cy:.2f})   {nets[0]}  [B.Cu segs? / F.Cu {len(segsA)}]   '
          f'{nets[1]}  [F.Cu {len(segsB)}]')
    if not segsA:
        print(f'    {nets[0]} has NO F.Cu copper at all -- every candidate needs a full trunk')
    if not segsB:
        print(f'    {nets[1]} has NO F.Cu copper at all -- every candidate needs a full trunk')

    best_by_tol = {}
    n_by_tol = {t: 0 for t in TOLERANCES}
    overall_best = None

    r = int(WINDOW / 2 / STEP)
    for i in range(-r, r + 1):
        for j in range(-r, r + 1):
            x, y = cx + i * STEP, cy + j * STEP
            if not (2.0 <= x <= 70.0 and 2.0 <= y <= 78.0):
                continue
            # site must be clear of other nets
            clear = True
            for ox, oy, orr in obs:
                if math.hypot(ox - x, oy - y) - orr < 2.0:
                    clear = False
                    break
            if not clear:
                continue
            for rot in (0, 90, 180, 270):
                a = math.radians(rot)
                dx, dy = (PAD_SEP / 2) * math.cos(a), (PAD_SEP / 2) * math.sin(a)
                p1 = (x - dx, y - dy)
                p2 = (x + dx, y + dy)
                dA = min(nearest(segsA, *p1)[0], nearest(segsA, *p2)[0])
                dB = min(nearest(segsB, *p1)[0], nearest(segsB, *p2)[0])
                worst = max(dA, dB)
                for t in TOLERANCES:
                    if worst <= t:
                        n_by_tol[t] += 1
                if overall_best is None or worst < overall_best[0]:
                    overall_best = (worst, x, y, rot, dA, dB)

    for t in TOLERANCES:
        print(f'    <= {t:4.1f} mm : {n_by_tol[t]:4d} candidate placements')
    if overall_best:
        w, x, y, rot, dA, dB = overall_best
        print(f'    BEST: ({x:.1f},{y:.1f}) rot {rot}  worst pad {w:.2f} mm '
              f'({nets[0]} {dA:.2f}, {nets[1]} {dB:.2f})')
        summary[ref] = (x, y, rot, w)
    else:
        print('    BEST: none found -- no clear site in the window')
    print()

print('=== VERDICT PER DIODE')
for ref in DIODES:
    if ref in summary:
        x, y, rot, w = summary[ref]
        verdict = 'PLACE, add short stub' if w <= 2.5 else (
            'PLACE, needs routed connection' if w <= 5.0 else 'PROBLEM: needs long trunk')
        print(f'  {ref}: ({x:.1f},{y:.1f}) rot {rot}  worst {w:.2f} mm  -> {verdict}')
    else:
        print(f'  {ref}: NO SITE')
