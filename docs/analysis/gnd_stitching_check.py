"""Astra's criticism, taken literally: is EVERY outer GND island actually stitched?

gpt-6-astra (2026-11-07), on this board:
  "All 48 GND vias lie inside In1 does not establish that every outer island is
   adequately stitched. ... Multiple vias could all be in the same island."

That is the right objection and my earlier probe did not answer it. A filled island with
no via and no grounded through-hole pad is FLOATING COPPER: it is not a return path, it is
an antenna, and it can be a fabrication concern.

Method: for each GND zone polygon on F.Cu and B.Cu, build the island's polygon and count
its own vias / grounded pads touching it. Report per island: area, whether it has at least
one via or PTH pad, and its bounding box so any floating island can be located.
"""
import pcbnew as p
import json
from pathlib import Path

BOARD = Path('/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb')
NET = 'GND'


def main():
    b = p.LoadBoard(str(BOARD))

    vias = [t for t in b.GetTracks()
            if isinstance(t, p.PCB_VIA) and t.GetNetname() == NET]
    pth = []
    for f in b.GetFootprints():
        for q in f.Pads():
            if q.GetNetname() == NET and q.HasHole():
                pth.append(q)
    print('GND vias: %d   GND through-hole pads: %d' % (len(vias), len(pth)))

    results = {}
    for z in b.Zones():
        if z.GetNetname() != NET:
            continue
        layer = z.GetLayer()
        lname = b.GetLayerName(layer)
        if lname in ('In1.Cu',):
            continue                       # the reference plane, not an outer pour
        filled = z.GetFilledPolysList(layer)
        n = filled.OutlineCount()
        print('\n%s on %s : %d island(s)' % (NET, lname, n))
        islands = []
        for i in range(n):
            poly = filled.COutline(i)
            # per-island probe: does any via / PTH pad sit inside this island?
            n_via = 0
            for v in vias:
                if poly.PointInside(v.GetPosition()):
                    n_via += 1
            n_pad = 0
            for q in pth:
                if poly.PointInside(q.GetPosition()):
                    n_pad += 1
            bb = poly.BBox()
            area = abs(poly.Area()) / 1e12
            islands.append({
                'island': i, 'area_mm2': round(area, 3),
                'vias_inside': n_via, 'pth_pads_inside': n_pad,
                'stitched': (n_via + n_pad) > 0,
                'bbox_mm': [round(bb.GetLeft() / 1e6, 2), round(bb.GetTop() / 1e6, 2),
                            round(bb.GetRight() / 1e6, 2), round(bb.GetBottom() / 1e6, 2)],
            })
            flag = '' if (n_via + n_pad) > 0 else '   <-- FLOATING'
            print('  island %-3d area %8.3f mm2  vias %2d  pth %2d%s'
                  % (i, area, n_via, n_pad, flag))
        results[lname] = islands

    total = sum(len(v) for v in results.values())
    floating = [dict(layer=ln, **isl) for ln, isls in results.items()
                for isl in isls if not isl['stitched']]
    float_area = sum(x['area_mm2'] for x in floating)
    print('\n=== SUMMARY')
    print('outer GND islands: %d' % total)
    print('FLOATING (no via, no PTH pad): %d' % len(floating))
    print('floating copper area: %.3f mm2' % float_area)
    for f in sorted(floating, key=lambda x: -x['area_mm2'])[:15]:
        print('   %-6s island %-3d %8.3f mm2 at %s'
              % (f['layer'], f['island'], f['area_mm2'], f['bbox_mm']))

    out = {'net': NET, 'islands': results, 'floating_count': len(floating),
           'floating_area_mm2': round(float_area, 3),
           'floating': floating,
           'verdict': ('ALL OUTER ISLANDS STITCHED' if not floating else
                       'FLOATING COPPER PRESENT - each island needs a via or a '
                       'justification for removal')}
    (BOARD.parent.parent.parent / 'gnd-stitching.json').write_text(json.dumps(out, indent=2))
    print('\nverdict: %s' % out['verdict'])


if __name__ == '__main__':
    main()
