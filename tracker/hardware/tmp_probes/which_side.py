"""Which side is every part on, and does that match the design intent?

D_BP1..D_BP4 being the ONLY bottom-side parts is the whole reason the top-only bundle exists.
If they are bottom by ACCIDENT (a footprint rotated/mirrored during placement) then the design
intent is "top" and the board should arguably be fixed rather than hand-soldered. If they are
bottom BY DESIGN, the top-only variant is a legitimate cost choice with a stated consequence.

So: report the side of every part, plus the evidence trail for each group.
"""
import pcbnew

BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
b = pcbnew.LoadBoard(BD)
MM = 1e6

rows = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    pos = fp.GetPosition()
    layer = fp.GetLayerName()          # 'F.Cu' or 'B.Cu'
    flipped = fp.IsFlipped()
    pkg = fp.GetFPID().GetLibItemName()
    val = fp.GetValue()
    rows.append((ref, layer, flipped, pos.x / MM, pos.y / MM, pkg, val,
                 fp.IsExcludedFromPosFiles(), fp.IsExcludedFromBOM()))

top = [r for r in rows if not r[2]]
bot = [r for r in rows if r[2]]

print(f'total footprints: {len(rows)}   top={len(top)}   bottom={len(bot)}\n')
print('BOTTOM-SIDE PARTS')
print(f'{"ref":12s} {"value":14s} {"package":26s} {"x":>7s} {"y":>7s}  DNP?')
for r in sorted(bot):
    print(f'{r[0]:12s} {str(r[5])[:14]:14s} {str(r[6])[:26]:26s} {r[3]:7.2f} {r[4]:7.2f}  '
          f'{"DNP" if r[8] else ("handfit" if r[7] else "PLACED")}')

print('\nALL PARTS BY GROUP (ref prefix), side tally')
from collections import defaultdict
groups = defaultdict(lambda: {'top': 0, 'bot': 0, 'refs': []})
for r in rows:
    # group by the alphabetic prefix, which is how the design names functional blocks
    pre = ''.join(ch for ch in r[0] if ch.isalpha())
    g = groups[pre]
    g['bot' if r[2] else 'top'] += 1
    g['refs'].append((r[0], 'B' if r[2] else 'T'))
for pre in sorted(groups):
    g = groups[pre]
    sides = ''.join(sorted({s for _, s in g['refs']}))
    print(f'  {pre:12s} top={g["top"]:2d} bottom={g["bot"]:2d}   sides={sides}')

print('\n=== rotation/orientation of the bottom parts (is a mirror plausible?)')
for r in sorted(bot):
    fp = next(f for f in b.GetFootprints() if f.GetReference() == r[0])
    print(f'  {r[0]:10s} orientation={fp.GetOrientationDegrees():7.1f} deg   '
          f'flipped={fp.IsFlipped()}')
