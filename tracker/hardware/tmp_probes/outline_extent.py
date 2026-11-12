"""Resolve 72.00 vs 72.10: measure the outline's CENTRELINE and its STROKE-INFLATED bbox separately.

Two numbers circulate in this repo for the same board. Both are correct; they measure different
things, and the difference is exactly one Edge.Cuts stroke width:

  centreline extent   what the fab cuts along -> the DIMENSION you order to
  bounding box        centreline inflated by half the stroke on each side -> what a renderer or a
                      bounding-box API reports

For a 4-layer board ordered at "72 x 80 mm" the centreline is the number that matters, because the
fab's outline tolerance is quoted against the drawn path, not against a stroke envelope.
"""
import pcbnew

BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
b = pcbnew.LoadBoard(BD)
MM = 1e6

print(f'board: {BD}\n')
shapes = [d for d in b.GetDrawings()
          if d.GetLayer() == pcbnew.Edge_Cuts and d.GetClass() == 'PCB_SHAPE']
print(f'Edge.Cuts PCB_SHAPE items: {len(shapes)}')

xs, ys, ws = [], [], []
for d in shapes:
    s, e = d.GetStart(), d.GetEnd()
    xs += [s.x / MM, e.x / MM]
    ys += [s.y / MM, e.y / MM]
    try:
        w = d.GetWidth() / MM
    except Exception:
        w = 0.0
    ws.append(w)

print(f'stroke widths present: {sorted(set(round(w, 4) for w in ws))} mm')
ctr_w = max(xs) - min(xs)
ctr_h = max(ys) - min(ys)
print(f'\nCENTRELINE extent : x {min(xs):.3f}..{max(xs):.3f}  = {ctr_w:.3f}')
print(f'                    y {min(ys):.3f}..{max(ys):.3f}  = {ctr_h:.3f}')

w = max(ws) if ws else 0.0
print(f'\nwith a {w:.3f} mm stroke, the drawn bbox is inflated by w/2 each side:')
print(f'  bbox extent     : {(ctr_w + w):.3f} x {(ctr_h + w):.3f} mm')
print(f'  bbox origin     : ({min(xs) - w / 2:.3f}, {min(ys) - w / 2:.3f})')

# also check any graphic arcs/circles that a bbox would catch but centreline min/max would not
others = {}
for d in b.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts:
        continue
    k = d.GetClass()
    others[k] = others.get(k, 0) + 1
print(f'\nother Edge.Cuts object classes: {others}')

print('\nVERDICT')
print(f'  order this board as {ctr_w:.2f} x {ctr_h:.2f} mm (centreline).')
print(f'  {ctr_w + w:.2f} x {ctr_h + w:.2f} is the same board measured with its stroke included —')
print('  not a different outline, and not a reason to re-draw anything.')
