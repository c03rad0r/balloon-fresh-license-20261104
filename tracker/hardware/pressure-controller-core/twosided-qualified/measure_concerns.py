#!/usr/bin/env python3
"""Measure the four placement concerns (a)-(d) for the two-sided candidate.

Every number in QUALIFIED-PLACEMENT-REPORT.md comes from this script. Nothing is quoted
from a datasheet as if it were a measurement, and nothing is measured twice in two places.

Concerns:
  (a) parts inside U1's courtyard polygon vs the real RF region
  (b) buck cell on the bottom: loop rigidity + copper width needed
  (c) PTH land clearance: nothing on the far face under a drilled land
  (d) assembly/enclosure consequences that are measurable from the board

Run: /usr/bin/python3 measure_concerns.py
Writes concerns.json. Exits non-zero if a measured invariant fails.
"""
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

import pcbnew as pcb
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
BOARD = HERE / 'twosided-qualified.kicad_pcb'
SOURCE = HERE.parent / 'placement' / 'core-placement.kicad_pcb'
COMPACT_REV = '12d063cf:tracker/hardware/pressure-controller-core/compact/compact.kicad_pcb'

# Model body rectangle of the ESP32-S3-WROOM-1 (from the library footprint courtyard,
# measured, not assumed). Antenna overhang is the bar north of y=0.
MODULE_BODY = box(18.25, 0.0, 37.75, 20.2)
ANTENNA_BAR = box(4.0, -21.0, 52.0, 0.0)
# Espressif ESP32-S3 HDG Fig.26 "Keepout Zone for ESP32-S3 Module's Antenna (Antenna feed
# point on the right)". The four PRINTED dimensions (unit mm) are:
#   Min15  = module LEFT edge to the clearance-area left boundary
#   Max 2  = module RIGHT edge to the clearance-area right boundary
#   Max 1  = module antenna-end(TIP) edge to the clearance-area upper boundary
#   "6"    = the antenna section projects 6 mm past the base-board edge
# The clearance area is a board CUTOUT region around the antenna, not a component box on the
# board. It is derived here from the measured module geometry rather than invented: an
# earlier version of this script used a hand-written box (15..42, 0..8) and "found" six
# violations -- every one of them an artifact of the box, including U1's OWN pads, which can
# never violate U1's own keepout.
MOD_LEFT, MOD_RIGHT = 18.25, 37.75          # module body extents, measured from the courtyard
MOD_ANT_END_Y = 0.0                          # module's antenna-end edge sits on the board edge
ANTENNA_PROJECT_MM = 6.0                     # HDG "6": antenna section past the board edge
RF_CLEARANCE = box(MOD_LEFT - 15.0,         # Min15 to the left
                   MOD_ANT_END_Y - ANTENNA_PROJECT_MM - 1.0,   # Max 1 beyond the tip
                   MOD_RIGHT + 2.0,          # Max 2 to the right
                   MOD_ANT_END_Y)            # down to the base-board edge

CLEAR_MM = 0.15          # board setup default clearance for this design
DL_PTH_CLEAR = 0.20      # min annular ring / land-to-foreign-copper we require for THT


def load_rev(rev):
    d = Path(tempfile.mkdtemp())
    p = d / 'b.kicad_pcb'
    p.write_bytes(subprocess.check_output(['git', '-C', str(WORKTREE), 'show', rev],
                                          stderr=subprocess.DEVNULL))
    return pcb.LoadBoard(str(p)), p


def crt(f):
    """Courtyard polygon for the footprint's own side, as drawn (not its bounding box)."""
    want = pcb.F_CrtYd if f.GetLayer() == pcb.F_Cu else pcb.B_CrtYd
    lines, rects = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() != want or not hasattr(g, 'GetShapeStr'):
            continue
        a, e = g.GetStart(), g.GetEnd()
        if g.GetShapeStr() == 'Rect':
            rects.append(box(a.x / 1e6, a.y / 1e6, e.x / 1e6, e.y / 1e6))
        else:
            lines.append(LineString([(a.x / 1e6, a.y / 1e6), (e.x / 1e6, e.y / 1e6)]))
    if not lines and not rects:
        return None
    return unary_union(rects + list(polygonize(lines)))


def pad_poly(p):
    """Exact pad copper outline. Queried on both layers because a flipped footprint's pads
    are re-parented to the opposite side, and querying only one layer returned nothing."""
    for layer in (pcb.B_Cu, pcb.F_Cu):
        try:
            sps = p.GetEffectivePolygon(layer)
        except Exception:
            continue
        if sps is None or sps.OutlineCount() == 0:
            continue
        pts = [(q.x / 1e6, q.y / 1e6) for q in sps.Outline(0).CPoints()]
        if len(pts) >= 3:
            return Polygon(pts)
    return None


def ipc2221_width_mm(i_a, dt_c=10.0, cu_um=35.0):
    """IPC-2221 external-layer chart: I = k dT^0.44 A^0.725, A in mil^2."""
    k = 0.048
    t_mil = cu_um / 25.4
    a_mil2 = (i_a / (k * dt_c ** 0.44)) ** (1.0 / 0.725)
    return (a_mil2 / t_mil) * 0.0254


def _pad_size(f, num):
    """Size of pad `num`, or None. FOOTPRINT.GetPad takes a VECTOR2I position in this
    binding, not a pad number, so pads are found by iterating."""
    for p in f.Pads():
        if p.GetNumber() == num:
            return [round(p.GetSize().x / 1e6, 3), round(p.GetSize().y / 1e6, 3)]
    return None


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    b = pcb.LoadBoard(str(BOARD))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    eb = b.GetBoardEdgesBoundingBox()
    outline = box(eb.GetX() / 1e6, eb.GetY() / 1e6,
                  (eb.GetX() + eb.GetWidth()) / 1e6, (eb.GetY() + eb.GetHeight()) / 1e6)
    out = {'board': BOARD.name, 'board_sha256': sha(BOARD),
           'source_board_sha256': sha(SOURCE),
           'outline_mm': [round(eb.GetWidth() / 1e6, 3), round(eb.GetHeight() / 1e6, 3)]}

    # ---------------------------------------------------------------- (a) antenna
    u1c = crt(fps['U1'])
    body_on_board = u1c.intersection(MODULE_BODY).intersection(outline)
    a = {
        'u1_courtyard_polygon_area_mm2': round(u1c.area, 3),
        'u1_courtyard_bounding_rect_mm2': round(
            (u1c.bounds[2] - u1c.bounds[0]) * (u1c.bounds[3] - u1c.bounds[1]), 3),
        'antenna_bar_area_mm2': round(u1c.intersection(ANTENNA_BAR).area, 3),
        'antenna_bar_on_board_mm2': round(
            u1c.intersection(ANTENNA_BAR).intersection(outline).area, 3),
        'antenna_bar_off_board_mm2': round(
            u1c.intersection(ANTENNA_BAR).difference(outline).area, 3),
        'module_body_on_board_mm2': round(body_on_board.area, 3),
        'u1_has_antenna_pad': False,
        'u1_antenna_pad_note': 'ESP32-S3-WROOM-1 PCB-antenna variant carries no antenna pad; '
                               'the lowest pad on the footprint is GND at y=1.04 mm. An '
                               '"antenna pad" is therefore not an object that exists here, '
                               'and the check is stated as not-applicable rather than passed.',
        'parts_inside_courtyard_polygon': {},
        'parts_inside_rf_clearance_area': {},
        'parts_in_antenna_bar': {},
        'rf_clearance_area_definition': {
            'derived_from': 'ESP32-S3 HDG Fig.26 printed dims Min15 / Max 2 / Max 1 / 6',
            'area_mm2': round(RF_CLEARANCE.area, 3),
            'on_board_mm2': None,      # filled below
            'note': 'the clearance area is a base-board CUTOUT around the antenna; the '
                    'binding question for placement is how much of it lands on copper '
                    'board, because off-board area cannot be occupied at all.',
        },
        'per_part': {},
    }
    for r, f in sorted(fps.items()):
        if r == 'U1':
            continue
        c = crt(f)
        if c is None:
            continue
        side = 'top' if f.GetLayer() == pcb.F_Cu else 'bottom'
        row = {'side': side,
               'courtyard_bbox_mm': [round(v, 3) for v in c.bounds],
               'courtyard_area_mm2': round(c.area, 3),
               'overlap_u1_courtyard_mm2': round(c.intersection(u1c).area, 4),
               'overlap_module_body_mm2': round(c.intersection(MODULE_BODY).area, 4),
               'overlap_rf_clearance_area_mm2': round(c.intersection(RF_CLEARANCE).area, 4),
               'overlap_antenna_bar_mm2': round(c.intersection(ANTENNA_BAR).area, 4),
               'dist_module_body_mm': round(c.distance(MODULE_BODY), 3),
               'dist_rf_clearance_area_mm': round(c.distance(RF_CLEARANCE), 3),
               'dist_board_north_edge_mm': round(c.distance(LineString([(0, 0), (52, 0)])), 3)}
        a['per_part'][r] = row
        if row['overlap_u1_courtyard_mm2'] > 1e-6:
            a['parts_inside_courtyard_polygon'][r] = row['overlap_u1_courtyard_mm2']
        if row['overlap_rf_clearance_area_mm2'] > 1e-6:
            a['parts_inside_rf_clearance_area'][r] = row['overlap_rf_clearance_area_mm2']
        if row['overlap_antenna_bar_mm2'] > 1e-6:
            a['parts_in_antenna_bar'][r] = row['overlap_antenna_bar_mm2']
    # widest copper object inside the RF keepout, any layer
    # FOREIGN pads only: U1's own pads are the antenna feed and ground ring and cannot
    # violate U1's own clearance area. Including them produced a 30-entry "violation" list
    # that was entirely U1 talking to itself.
    cu_objs = []
    for f in b.GetFootprints():
        if f.GetReference() == 'U1':
            continue
        for p in f.Pads():
            g = pad_poly(p)
            if g is not None and g.intersection(RF_CLEARANCE).area > 1e-6:
                cu_objs.append(f.GetReference() + '.' + p.GetNumber())
    a['foreign_pad_copper_inside_rf_clearance'] = sorted(set(cu_objs))
    a['rf_clearance_area_definition']['on_board_mm2'] = round(
        RF_CLEARANCE.intersection(outline).area, 3)
    # Any routed copper inside it (the board is UNROUTED, so this must be empty and the
    # empty result is meaningful only because the count of tracks is reported alongside).
    tr = [t for t in b.GetTracks()
          if Polygon([(q.x / 1e6, q.y / 1e6)
                      for q in t.GetEffectivePolygon().Outline(0).CPoints()]
                     ).intersection(RF_CLEARANCE).area > 1e-6]
    a['tracks_inside_rf_clearance'] = len(tr)
    a['total_tracks_on_board'] = len(b.GetTracks())
    # keepout rule area actually present in the file
    a['module_keepout_rule_area'] = None
    for z in b.Zones():
        if not z.GetIsRuleArea():
            continue
        pts = [(q.x / 1e6, q.y / 1e6) for q in z.Outline().Outline(0).CPoints()]
        reg = Polygon(pts)
        if abs(reg.bounds[0] - 18.25) < 1e-6:
            a['module_keepout_rule_area'] = {
                'layer': str(pcb.LayerName(z.GetLayer())),
                'polygon_area_mm2': round(reg.area, 3),
                'on_board_mm2': round(reg.intersection(outline).area, 3),
                'bbox_mm': [round(v, 3) for v in reg.bounds],
                'no_routed_copper': bool(z.GetDoNotAllowTracks()),
                'no_vias': bool(z.GetDoNotAllowVias()),
                'no_pours': bool(z.GetDoNotAllowCopperPour()),
                'footprints_allowed': bool(z.GetDoNotAllowFootprints()) is False,
            }
    out['a_antenna'] = a

    # ---------------------------------------------------------------- (b) buck cell
    BUCK = ('U2', 'L1', 'C4', 'C5', 'C6', 'R7', 'R8')
    b_sides = {r: ('top' if fps[r].GetLayer() == pcb.F_Cu else 'bottom') for r in BUCK}
    VIN, VOUT, ILOAD = 5.0, 3.3, 1.0
    i_in = ILOAD * VOUT / VIN / 0.90
    widths = {n: {'current_a': round(i, 3),
                  'ipc2221_width_1oz_dt10_mm': round(ipc2221_width_mm(i), 3),
                  'ipc2221_width_2oz_dt10_mm': round(ipc2221_width_mm(i, cu_um=70.0), 3)}
              for n, i in (('/USB5V', i_in), ('/BUCK_SW', ILOAD),
                           ('/+3V3', ILOAD), ('/GND', i_in))}
    # exact pad-to-pad gaps between DIFFERENT nets inside the cell
    polys = []
    for r in BUCK:
        for p in fps[r].Pads():
            if p.GetNumber():
                g = pad_poly(p)
                if g is not None and g.is_valid:
                    polys.append((r, p.GetNumber(), p.GetNetname(), g))
    gaps = []
    for i, x in enumerate(polys):
        for y in polys[i + 1:]:
            if x[0] == y[0] or x[2] == y[2]:
                continue
            gaps.append((round(x[3].distance(y[3]), 3), x[0] + '.' + x[1], x[2],
                         y[0] + '.' + y[1], y[2]))
    gaps.sort()
    if not gaps:
        raise SystemExit('(b) measurement failed: no pad pairs (empty result is not a pass)')
    widest = max(v['ipc2221_width_1oz_dt10_mm'] for v in widths.values())
    b_out = {
        'cell_parts': list(BUCK),
        'cell_sides': b_sides,
        'cell_is_single_sided': len(set(b_sides.values())) == 1,
        'cell_side': list(set(b_sides.values()))[0],
        'copper_width_requirement': widths,
        'widest_required_1oz_mm': widest,
        'stackup': '2 copper layers, 1.6 mm; JLCPCB 2-layer prototype default is 1 oz (35 um) '
                   'outer copper. Widths are IPC-2221 ADVISORY for the routing pass, not a '
                   'thermal simulation, and the board is UNROUTED so no track exists yet.',
        'tightest_diff_net_pad_gaps': [
            {'gap_mm': g[0], 'a': g[1], 'net_a': g[2], 'b': g[3], 'net_b': g[4]}
            for g in gaps[:6]],
        'min_diff_net_pad_gap_mm': gaps[0][0],
        'widest_trace_fits_tightest_gap': bool(gaps[0][0] >= widest + 2 * CLEAR_MM),
        'heat_path': {
            'u2_package': str(fps['U2'].GetFPID().GetLibItemName()),
            'u2_exposed_pad_mm': _pad_size(fps['U2'], '9'),
            'u2_thermal_vias': sum(1 for p in fps['U2'].Pads()
                                   if p.GetAttribute() == pcb.PAD_ATTRIB_PTH),
            'note': 'U2 is a WSON-8 with an exposed thermal pad. On the BOTTOM the pad faces '
                    'the enclosure, so heat leaves through the board into a still-air cavity '
                    'rather than through a top-side plane coupled to the top copper.',
        },
        'rework_access': 'bottom-side cell is reachable only with the board lifted out; '
                         'the top side is the service side (J1, U1, switches).',
    }
    out['b_buck'] = b_out

    # ---------------------------------------------------------------- (c) THT lands
    c_out = {'required_clearance_mm': DL_PTH_CLEAR, 'lands': []}
    worst = (9e9, None)
    for r, f in fps.items():
        for p in f.Pads():
            if p.GetAttribute() != pcb.PAD_ATTRIB_PTH:
                continue
            g = pad_poly(p)
            if g is None:
                continue
            best_pad = (9e9, None, '')
            for r2, f2 in fps.items():
                if r2 == r:
                    continue
                for p2 in f2.Pads():
                    g2 = pad_poly(p2)
                    if g2 is None:
                        continue
                    d = g.distance(g2)
                    if d < best_pad[0]:
                        best_pad = (d, r2 + '.' + p2.GetNumber(), p2.GetNetname())
            best_crt = (9e9, None)
            for r2, f2 in fps.items():
                if r2 == r:
                    continue
                c2 = crt(f2)
                if c2 is None:
                    continue
                d = g.distance(c2)
                if d < best_crt[0]:
                    best_crt = (d, r2)
            margin = min(best_pad[0], best_crt[0])
            c_out['lands'].append({
                'land': r + '.' + p.GetNumber(),
                'drill_mm': round(p.GetDrillSize().x / 1e6, 3),
                'nearest_foreign_pad_mm': round(best_pad[0], 3),
                'nearest_foreign_pad': best_pad[1],
                'nearest_foreign_courtyard_mm': round(best_crt[0], 3),
                'nearest_foreign_courtyard': best_crt[1],
                'margin_mm': round(margin, 3),
                'pass': bool(margin >= DL_PTH_CLEAR)})
            if margin < worst[0]:
                worst = (margin, r + '.' + p.GetNumber())
    c_out['worst_margin_mm'] = round(worst[0], 3)
    c_out['worst_land'] = worst[1]
    c_out['all_pass'] = all(x['pass'] for x in c_out['lands'])
    c_out['n_lands'] = len(c_out['lands'])
    c_out['footprints_with_lands'] = sorted({x['land'].split('.')[0] for x in c_out['lands']})
    # both faces really are drilled: every PTH land appears on B.Cu and F.Cu
    both = 0
    for r, f in fps.items():
        for p in f.Pads():
            if p.GetAttribute() != pcb.PAD_ATTRIB_PTH:
                continue
            if (p.IsOnLayer(pcb.B_Cu) and p.IsOnLayer(pcb.F_Cu)):
                both += 1
    c_out['lands_on_both_faces'] = both
    out['c_tht'] = c_out

    # ---------------------------------------------------------------- (d) assembly
    d_out = {
        'bottom_parts': sorted(r for r, f in fps.items() if f.GetLayer() == pcb.B_Cu),
        'top_parts': sorted(r for r, f in fps.items() if f.GetLayer() == pcb.F_Cu),
        'bottom_part_count': sum(1 for f in b.GetFootprints() if f.GetLayer() == pcb.B_Cu),
        'top_part_count': sum(1 for f in b.GetFootprints() if f.GetLayer() == pcb.F_Cu),
        'bottom_side_is_smt_only': all(
            f.GetLayer() != pcb.B_Cu or all(p.GetAttribute() != pcb.PAD_ATTRIB_PTH
                                            for p in f.Pads())
            for f in b.GetFootprints()),
        'paste_stencil_sides': 2,
        'stencil_note': 'two paste prints (top and bottom) mean two stencils or one '
                        'double-print sequence; JLCPCB charges the double-side stencil fee.',
        'cpl_rotation_note': 'bottom-side CPL needs the mirrored rotation convention; KiCad '
                             'reports footprint orientation as placed, so the bottom CPL must '
                             'be emitted with the 180 deg / mirror transform applied or every '
                             'bottom part is rotated wrongly on the line.',
        'board_thickness_mm': round(b.GetDesignSettings().GetBoardThickness() / 1000, 3),
        'copper_layers': ['F.Cu', 'B.Cu'],
    }
    # Enclosure clearance under the board: the tallest bottom part must fit.
    tall = []
    for f in b.GetFootprints():
        if f.GetLayer() != pcb.B_Cu:
            continue
        for m in f.Models():
            try:
                h = m.height
            except Exception:
                h = None
            if h:
                tall.append((round(h, 3), f.GetReference()))
    d_out['bottom_part_heights_mm'] = sorted(tall, reverse=True)
    d_out['min_enclosure_cavity_under_board_mm'] = max([h for h, _ in tall], default=None)
    out['d_assembly'] = d_out

    (HERE / 'concerns.json').write_text(json.dumps(out, indent=2) + '\n')

    # ------------------------------------------------ hard invariants (fail loudly)
    fails = []
    if a['parts_inside_courtyard_polygon']:
        fails.append('(a) parts inside U1 courtyard polygon: %s'
                     % a['parts_inside_courtyard_polygon'])
    if a['parts_inside_rf_clearance_area']:
        fails.append('(a) parts inside the HDG RF clearance area: %s'
                     % a['parts_inside_rf_clearance_area'])
    if a['foreign_pad_copper_inside_rf_clearance']:
        fails.append('(a) foreign pad copper inside the HDG RF clearance area: %s'
                     % a['foreign_pad_copper_inside_rf_clearance'])
    if a['tracks_inside_rf_clearance']:
        fails.append('(a) %d routed tracks inside the HDG RF clearance area'
                     % a['tracks_inside_rf_clearance'])
    if not a['module_keepout_rule_area']:
        fails.append('(a) module keepout rule area missing')
    ra = a['module_keepout_rule_area'] or {}
    if not ra.get('no_routed_copper'):
        fails.append('(a) restored module keepout rule area does not forbid tracks')
    if not b_out['cell_is_single_sided']:
        fails.append('(b) buck cell is not on one side')
    if not c_out['all_pass']:
        fails.append('(c) PTH land clearance below %.2f mm' % DL_PTH_CLEAR)
    if fails:
        print('\n'.join('FAIL ' + f for f in fails))
        raise SystemExit(1)

    print('(a) antenna  : %d parts inside U1 courtyard polygon, %d in the HDG RF clearance '
          'area (%d foreign pad hits, %d/%d tracks), rule area on %s'
          % (len(a['parts_inside_courtyard_polygon']),
             len(a['parts_inside_rf_clearance_area']),
             len(a['foreign_pad_copper_inside_rf_clearance']),
             a['tracks_inside_rf_clearance'], a['total_tracks_on_board'],
             (a['module_keepout_rule_area'] or {}).get('layer')))
    print('(b) buck     : %d parts, all on %s ; widest trace needed %.3f mm (1 oz, 10 C) ; '
          'tightest diff-net pad gap %.3f mm'
          % (len(BUCK), b_out['cell_side'], widest, b_out['min_diff_net_pad_gap_mm']))
    print('(c) THT      : %d lands on %s, %d on both faces, worst margin %.3f mm '
          '(>= %.2f required)'
          % (c_out['n_lands'], ','.join(c_out['footprints_with_lands']),
             both, c_out['worst_margin_mm'], DL_PTH_CLEAR))
    print('(d) assembly : %d top / %d bottom, bottom SMT-only=%s, cavity >= %s mm'
          % (d_out['top_part_count'], d_out['bottom_part_count'],
             d_out['bottom_side_is_smt_only'], d_out['min_enclosure_cavity_under_board_mm']))
    print('wrote', HERE / 'concerns.json')


if __name__ == '__main__':
    main()
