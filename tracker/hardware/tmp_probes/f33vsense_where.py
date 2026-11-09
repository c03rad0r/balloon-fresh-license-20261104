"""Where does /F33_VSENSE copper actually live, and how far is it from U1.21?

Replaces the buggy nearest-neighbour probe. That one reported -817852 mm, which is not a
measurement -- it is a distance that skipped the pad's half-extent subtraction because the
nearest track's projection fell outside the segment. A negative gap of 800 metres is a tool bug,
never a board fact, and shipping it would be worse than not measuring.
"""
import math

import pcbnew

MM = 1e6
BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
NET = '/F33_VSENSE'

b = pcbnew.LoadBoard(BD)

pad = None
for fp in b.GetFootprints():
    if fp.GetReference() == 'U1':
        for p in fp.Pads():
            if p.GetNumber() == '21':
                pad = p
pads = [(fp.GetReference(), p.GetNumber(), p.GetPosition(), p.GetSize())
        for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == NET]
tracks = [t for t in b.GetTracks() if t.GetNetname() == NET and t.GetClass() != 'PCB_VIA']
vias = [t for t in b.GetTracks() if t.GetNetname() == NET and t.GetClass() == 'PCB_VIA']

print(f'{NET}: {len(pads)} pads, {len(tracks)} tracks, {len(vias)} vias')
print('pads:')
for ref, num, pos, size in pads:
    print(f'  {ref}.{num:>3s} at ({pos.x / MM:.3f},{pos.y / MM:.3f}) '
          f'size {size.x / MM:.2f}x{size.y / MM:.2f}')

xs, ys = [], []
for t in tracks:
    for pt in (t.GetStart(), t.GetEnd()):
        xs.append(pt.x / MM)
        ys.append(pt.y / MM)
print(f'\ntrack extent: x {min(xs):.2f}..{max(xs):.2f}   y {min(ys):.2f}..{max(ys):.2f}')
print('layers:', sorted({b.GetLayerName(t.GetLayer()) for t in tracks}))

px, py = pad.GetPosition().x / MM, pad.GetPosition().y / MM
print(f'\nU1.21 centre = ({px:.3f},{py:.3f})')

best = (1e9, None)
for t in tracks:
    s, e = t.GetStart(), t.GetEnd()
    x1, y1, x2, y2 = s.x / MM, s.y / MM, e.x / MM, e.y / MM
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    tpar = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    cx, cy = x1 + tpar * dx, y1 + tpar * dy
    centre_d = math.hypot(px - cx, py - cy)
    if centre_d < best[0]:
        best = (centre_d, (x1, y1, x2, y2, b.GetLayerName(t.GetLayer()), t.GetWidth() / MM))

d, info = best
x1, y1, x2, y2, layer, w = info
bb = pad.GetBoundingBox()
half = min(bb.GetWidth(), bb.GetHeight()) / 2.0 / MM
print(f'nearest track: ({x1:.2f},{y1:.2f})->({x2:.2f},{y2:.2f}) {layer} w={w:.2f}')
print(f'centre-to-track distance: {d:.3f} mm')
print(f'pad half-min-extent: {half:.3f} mm -> pad centre to pad EDGE (short side)')
print(f'gap to a 1.5x0.9 pad short side: {d - 0.45 - w / 2:.3f} mm (approximate, along the short axis)')
print(f'gap to the pad\'s long end (0.75): {d - 0.75 - w / 2:.3f} mm')
