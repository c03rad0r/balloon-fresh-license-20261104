"""Could a cheap mux/expander give U_C its four signals on v10?

The operator asked whether cheap parts exist to expose more SPI devices. They do. The question is
whether adding one helps HERE, and that turns on two numbers, not on availability:

  1. how many GPIOs are actually free            (2: IO3, IO42)
  2. how far U_C's four control pads are from    <- the one that decides it
     somewhere a part could physically sit

A mux only helps if you can ROUTE from U_C's pads to it. U_C sits on an SPI1 bus whose pins are
0 tracks on this board and whose only neighbours are ground pours. If the nearest place a part
could go is tens of millimetres away, a mux converts "4 missing GPIOs" into "4 impossible routes"
and changes nothing.

So this measures the geometry and reports it, rather than recommending a part because it exists.
"""
import math
import os

import pcbnew

MM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))
BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'

b = pcbnew.LoadBoard(BD)

UC_PINS = {'6': '/U_C_CS_N', '7': '/U_C_BUSY', '14': '/U_C_RESET_N', '15': '/U_C_IRQ'}


def pads_of(ref):
    for fp in b.GetFootprints():
        if fp.GetReference() == ref:
            return fp, list(fp.Pads())
    return None, []


def pxy(p):
    return p.GetPosition().x / MM, p.GetPosition().y / MM


# --- U_C control pads
fpUC, padsUC = pads_of('U_C')
uc = {}
for p in padsUC:
    if p.GetNumber() in UC_PINS:
        uc[p.GetNumber()] = pxy(p)

print('U_C control pads:')
for num, (x, y) in sorted(uc.items(), key=lambda kv: int(kv[0])):
    print(f'  U_C.{num:>3s} {UC_PINS[num]:14s} at ({x:.2f},{y:.2f})')

cx = sum(v[0] for v in uc.values()) / len(uc)
cy = sum(v[1] for v in uc.values()) / len(uc)
print(f'  centroid of the four: ({cx:.2f},{cy:.2f})')

# --- every DNP footprint big enough to host a SOT-23-6 / SOT-353 / MSOP
print('\nDNP or unpopulated footprints that could physically host a small logic part:')
cands = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref in ('U_C', 'U3', 'U1'):
        continue
    if fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_BOM or not fp.GetAttributes():
        pass
    pads = list(fp.Pads())
    if not pads:
        continue
    bx, by = fp.GetPosition().x / MM, fp.GetPosition().y / MM
    d = math.hypot(bx - cx, by - cy)
    excluded = bool(fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_BOM)
    cands.append((d, ref, str(fp.GetFPID().GetLibItemName()), excluded, len(pads), bx, by))

for d, ref, fpid, excluded, npads, bx, by in sorted(cands)[:14]:
    mark = 'DNP' if excluded else 'fit'
    print(f'  {d:7.2f} mm  {ref:10s} {fpid[:26]:26s} {mark:3s} {npads:2d} pads '
          f'at ({bx:.1f},{by:.1f})')

# --- what is already on the I2C nets (an expander would use these)
print('\nI2C nets available for a GPIO expander:')
for net in ('/I2C_SCL', '/I2C_SDA'):
    pads = [f'{fp.GetReference()}.{p.GetNumber()}' for fp in b.GetFootprints()
            for p in fp.Pads() if p.GetNetname() == net]
    tk = sum(1 for t in b.GetTracks() if t.GetNetname() == net and t.GetClass() != 'PCB_VIA')
    print(f'  {net:10s} {tk:3d} tracks   pads={pads}')

# --- free GPIOs, restated with their position so a mux could be near them
print('\nfree usable U1 pads and how far they are from U_C:')
fpU1, padsU1 = pads_of('U1')
FREE = {'15': 'IO3', '35': 'IO42'}
for p in padsU1:
    n = p.GetNumber()
    if n in FREE and not p.GetNetname():
        x, y = pxy(p)
        d = math.hypot(x - cx, y - cy)
        print(f'  U1.{n:>3s} {FREE[n]:6s} at ({x:.2f},{y:.2f})  {d:.2f} mm from U_C centroid')
