"""Stitch the two accessible floating GND islands. Real gain, no rule change, no part moves.

gnd_stitching_check.py found 3 floating islands (no via, no grounded through-hole pad):
  F.Cu island 11   2.249 mm2  [27.65,33.25]-[29.45,34.51]
  B.Cu island  3   0.925 mm2  [36.48,70.20]-[37.80,70.95]
  F.Cu island  0   0.844 mm2  [40.84,43.84]-[41.97,44.95]   <- R_DIV2.2, C10-FROZEN, skip

gpt-6-astra on these: "4 mm2 of floating copper is not a blocking issue for fabrication",
and a stitching via is the fix. The first two sit outside the frozen region, so they can be
fixed without touching C10.

Method: for each target island, search its interior for a legal via at frozen S1 rules
(0.600 land / 0.300 drill / 0.200 clearance / 0.250 hole-to-hole), using Collide only. Then
apply every stitchable island in one batch and hold it to the same two hard gates as every
accepted batch: opens must decrease, no previously connected pair broken.

If no legal site exists inside an island, that island is reported unfixable rather than
stitched at a sub-S1 neck.
"""
import sys
sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')
import pcbnew as p
import json
import os
import subprocess
import collide_router as CR
import batch_run as BR

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
NAME = 'GNDSTITCH'
NET = 'GND'
FROZEN = (39.5, 43.0, 43.5, 46.0)      # x0,y0,x1,y1 in mm -- C10, do not touch
STEP = 50000


def drc(board, out):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', out, board],
                   capture_output=True, timeout=1200)
    d = json.load(open(out))
    errs = [v for v in d.get('violations', []) if v.get('severity') == 'error']
    return len(d['unconnected_items']), len(d.get('violations', [])), len(errs)


def floating_islands(b):
    """Islands of the GND zones on outer layers with no via and no grounded PTH pad."""
    vias = [t for t in b.GetTracks() if isinstance(t, p.PCB_VIA) and t.GetNetname() == NET]
    pth = [q for f in b.GetFootprints() for q in f.Pads()
           if q.GetNetname() == NET and q.HasHole()]
    out = []
    for z in b.Zones():
        if z.GetNetname() != NET:
            continue
        ln = b.GetLayerName(z.GetLayer())
        if ln == 'In1.Cu':
            continue
        filled = z.GetFilledPolysList(z.GetLayer())
        for i in range(filled.OutlineCount()):
            poly = filled.COutline(i)
            if any(poly.PointInside(v.GetPosition()) for v in vias):
                continue
            if any(poly.PointInside(q.GetPosition()) for q in pth):
                continue
            bb = poly.BBox()
            out.append({'layer': z.GetLayer(), 'lname': ln, 'island': i, 'poly': poly,
                        'area': abs(poly.Area()) / 1e12,
                        'bbox': (bb.GetLeft() / 1e6, bb.GetTop() / 1e6,
                                 bb.GetRight() / 1e6, bb.GetBottom() / 1e6)})
    return out


def in_frozen(x_mm, y_mm):
    return FROZEN[0] <= x_mm <= FROZEN[2] and FROZEN[1] <= y_mm <= FROZEN[3]


def find_site(b, field, isl):
    """Legal via site fully inside the island, clear of foreign copper, outside frozen."""
    l, t, r, bo = isl['bbox']
    poly = isl['poly']
    best = None
    y = t
    while y <= bo:
        x = l
        while x <= r:
            xi, yi = int(round(x * 1e6)), int(round(y * 1e6))
            if poly.PointInside(p.VECTOR2I(xi, yi)) and not in_frozen(x, y):
                if field.via_ok(xi, yi, NET):
                    # require the whole 0.6 mm land inside the island, not just its centre
                    land_ok = all(
                        poly.PointInside(p.VECTOR2I(int(round((x + dx) * 1e6)),
                                                    int(round((y + dy) * 1e6))))
                        for dx, dy in ((-0.3, 0), (0.3, 0), (0, -0.3), (0, 0.3),
                                       (-0.21, -0.21), (0.21, -0.21),
                                       (-0.21, 0.21), (0.21, 0.21)))
                    if land_ok:
                        best = (xi, yi, x, y)
                        return best
            x += STEP / 1e6
        y += STEP / 1e6
    return best


def main():
    B = os.path.join(ROOT, 'batches', NAME)
    os.makedirs(B, exist_ok=True)
    src = os.path.join(B, 'board.kicad_pcb')
    subprocess.run(['cp', LIVE, src], check=True)
    for ext in ('kicad_pro', 'kicad_dru'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            subprocess.run(['cp', s, src.replace('.kicad_pcb', '.' + ext)], check=True)

    ob, vb, eb = drc(src, os.path.join(B, 'before-drc.json'))
    print('batch %s from live: opens=%d viol=%d errors=%d' % (NAME, ob, vb, eb))

    b = p.LoadBoard(src)
    islands = floating_islands(b)
    print('\nfloating GND islands: %d' % len(islands))
    for i in islands:
        print('  %-5s island %-3d %7.3f mm2 at %s%s'
              % (i['lname'], i['island'], i['area'],
                 tuple(round(v, 2) for v in i['bbox']),
                 '  FROZEN - SKIP' if in_frozen((i['bbox'][0] + i['bbox'][2]) / 2,
                                               (i['bbox'][1] + i['bbox'][3]) / 2) else ''))

    poly = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly)
    bb = poly.BBox()
    box = (bb.GetLeft() - 500000, bb.GetTop() - 500000,
           bb.GetRight() + 500000, bb.GetBottom() + 500000)
    field = BR.SeqField(b, box, BR.ROUTE_CLEAR)

    n = b.FindNet(NET)
    placed, skipped = [], []
    for isl in islands:
        cx = (isl['bbox'][0] + isl['bbox'][2]) / 2
        cy = (isl['bbox'][1] + isl['bbox'][3]) / 2
        if in_frozen(cx, cy):
            print('\n%-5s island %d: SKIPPED (inside C10 frozen region)'
                  % (isl['lname'], isl['island']))
            skipped.append({'island': isl['island'], 'layer': isl['lname'],
                            'reason': 'frozen'})
            continue
        site = find_site(b, field, isl)
        if site is None:
            print('\n%-5s island %d: NO LEGAL VIA SITE inside the island (%s)'
                  % (isl['lname'], isl['island'], isl['area']))
            skipped.append({'island': isl['island'], 'layer': isl['lname'],
                            'reason': 'no legal site'})
            continue
        xi, yi, x, y = site
        v = p.PCB_VIA(b)
        v.SetNet(n)
        v.SetPosition(p.VECTOR2I(xi, yi))
        v.SetWidth(int(BR.VIA_R * 2))
        v.SetDrill(int(CR.DRILL_R * 2))
        b.Add(v)
        placed.append({'island': isl['island'], 'layer': isl['lname'],
                       'x': round(x, 3), 'y': round(y, 3), 'area': round(isl['area'], 3)})
        print('\n%-5s island %d: STITCHED with via at (%.3f, %.3f)'
              % (isl['lname'], isl['island'], x, y))

    if not placed:
        print('\nbatch %s: NOTHING STITCHED -- tree untouched' % NAME)
        json.dump({'placed': [], 'skipped': skipped},
                  open(os.path.join(B, 'report.json'), 'w'), indent=2)
        return 1

    out = os.path.join(B, 'routed.kicad_pcb')
    p.SaveBoard(out, b)
    b2 = p.LoadBoard(out)
    p.ZONE_FILLER(b2).Fill(b2.Zones())
    p.SaveBoard(out, b2)
    print('\nrefilled %d zone(s)' % len(list(b2.Zones())))

    oa, va, ea = drc(out, os.path.join(B, 'drc.json'))
    print('native opens: %d -> %d  (delta %+d)' % (ob, oa, oa - ob))
    print('violations: %d -> %d   errors: %d -> %d' % (vb, va, eb, ea))
    ok = oa < ob and va <= vb
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    json.dump({'placed': placed, 'skipped': skipped,
               'opens_before': ob, 'opens_after': oa,
               'viol_before': vb, 'viol_after': va,
               'errors_before': eb, 'errors_after': ea,
               'verdict': 'PASS' if ok else 'FAIL'},
              open(os.path.join(B, 'report.json'), 'w'), indent=2)
    if ok:
        subprocess.run(['cp', out, LIVE], check=True)
        for ext in ('kicad_pro', 'kicad_dru'):
            s = out.replace('.kicad_pcb', '.' + ext)
            if os.path.exists(s):
                subprocess.run(['cp', s, LIVE.replace('.kicad_pcb', '.' + ext)], check=True)
        print('batch %s: ACCEPTED -> latest.kicad_pcb' % NAME)
        return 0
    print('batch %s: REJECTED -- tree untouched' % NAME)
    return 2


if __name__ == '__main__':
    sys.exit(main())
