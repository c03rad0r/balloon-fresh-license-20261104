"""Does an I2C GPIO expander actually solve U_C on v10? Measure proximity, not plausibility.

The operator asked for cheap parts that expose more SPI devices. The cheapest answer that needs
NO new MCU pins is an I2C GPIO expander (TCA9534 / PCF8574, ~$0.40, 8 GPIOs), because /I2C_SCL and
/I2C_SDA already exist and are already routed.

But "the bus exists" is not "the part can go there". A v10 fix needs the expander to sit near U_C
so four short traces reach U_C.6/7/14/15. If the I2C copper is 30 mm away, the part buys nothing.

This measures:
  - the extent of the routed I2C copper
  - the minimum distance from that copper to U_C's four control pads
  - whether the four pads are close enough together to fan out to one small part
"""
import math
import os

import pcbnew

MM = 1e6
BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
b = pcbnew.LoadBoard(BD)

UC = {'6': '/U_C_CS_N', '7': '/U_C_BUSY', '14': '/U_C_RESET_N', '15': '/U_C_IRQ'}


def fp_of(ref):
    for f in b.GetFootprints():
        if f.GetReference() == ref:
            return f
    return None


ucpads = {p.GetNumber(): p for p in fp_of('U_C').Pads() if p.GetNumber() in UC}
ucxy = {n: (p.GetPosition().x / MM, p.GetPosition().y / MM) for n, p in ucpads.items()}
print('U_C control pads:')
for n in sorted(UC, key=int):
    x, y = ucxy[n]
    print(f'  U_C.{n:>3s} {UC[n]:14s} ({x:.2f},{y:.2f})')


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


print('\nI2C copper extent and distance to U_C:')
for net in ('/I2C_SCL', '/I2C_SDA'):
    segs = [(t.GetStart(), t.GetEnd()) for t in b.GetTracks()
            if t.GetNetname() == net and t.GetClass() != 'PCB_VIA']
    if not segs:
        print(f'  {net}: NO COPPER')
        continue
    xs = [p.x / MM for s, e in segs for p in (s, e)]
    ys = [p.y / MM for s, e in segs for p in (s, e)]
    best = 1e9
    bestpad = None
    for n, (px, py) in ucxy.items():
        for s, e in segs:
            d = seg_dist(px, py, s.x / MM, s.y / MM, e.x / MM, e.y / MM)
            if d < best:
                best, bestpad = d, n
    print(f'  {net}: {len(segs)} segs, x {min(xs):.1f}..{max(xs):.1f}, '
          f'y {min(ys):.1f}..{max(ys):.1f}')
    print(f'    nearest approach to U_C.{bestpad} = {best:.2f} mm')

# how spread out are the four pads? a single small part must reach all four
xs = [v[0] for v in ucxy.values()]
ys = [v[1] for v in ucxy.values()]
print(f'\nfour-pad span: {(max(xs) - min(xs)):.2f} mm x {(max(ys) - min(ys)):.2f} mm')
print(f'  x {min(xs):.2f}..{max(xs):.2f}   y {min(ys):.2f}..{max(ys):.2f}')

# what sits between them, physically? U_C body itself plus the two pad columns
f = fp_of('U_C')
bx, by = f.GetPosition().x / MM, f.GetPosition().y / MM
print(f'  U_C body centre ({bx:.2f},{by:.2f})  '
      f'pads on two faces: left x~{min(xs):.1f}, right x~{max(xs):.1f}')
print('\n  NOTE the four pads are on OPPOSITE SIDES of the module, ~19.8 mm apart.')
print('  An expander would need to reach both sides, or the two right-hand signals')
print('  would have to cross to the left, or U_C could take them on separate pins.')
