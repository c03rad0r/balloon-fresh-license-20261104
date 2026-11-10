#!/usr/bin/env python3
"""Bounded 65x50 single-sided placement study (DESIGN CANDIDATE, unrouted).

Derived from the actual 26-part / 125-endpoint schematic export and the committed
candidate board. The source board is NEVER written: it is byte-copied here first,
and only that copy is stripped and re-placed.

Every stage runs in its own process because pcbnew invalidates SWIG handles after a
collection mutation, and a long chained script has been observed to segfault.

Run: /usr/bin/python3 study.py      # or one stage: copy|strip|place|annotate|verify
"""
import sys, json, hashlib, shutil, subprocess, re
from pathlib import Path
from collections import Counter
import pcbnew as pcb
from shapely.geometry import box, LineString
from shapely.ops import polygonize, unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import placement

SOURCE = ROOT / 'placement/core-placement.kicad_pcb'
BOARD = HERE / 'compact.kicad_pcb'
MOTOR = (33, 24, 63, 48)          # preserved 30 x 24 mm reservation, unchanged size
SITES = dict(placement.SITES)
SITES.update({'U3': (48, 10, 0), 'U4': (60, 10, 0), 'C7': (44.5, 9.4, 90),
              'C8': (56.5, 9.4, 90), 'SW2': (27, 28, 0), 'R9': (48, 19, 0),
              'R10': (48, 21, 0)})
for ref in ['U2', 'C4', 'L1', 'C5', 'C6', 'R7', 'R8']:   # buck cell: -5 mm in y
    x, y, a = SITES[ref]
    SITES[ref] = (x, y - 5, a)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def copper(b):
    return {'tracks_and_vias': len(list(b.GetTracks())),
            'copper_zones': sum(1 for z in b.Zones() if not z.GetIsRuleArea())}


def stage_copy():
    before = sha(SOURCE)
    shutil.copyfile(SOURCE, BOARD)
    shutil.copyfile(ROOT / 'placement/core-placement.kicad_pro', HERE / 'compact.kicad_pro')
    shutil.copyfile(ROOT / 'placement/fp-lib-table', HERE / 'fp-lib-table')
    require(sha(SOURCE) == before, 'source board changed during copy')
    print('copied source ->', BOARD.name, 'source_sha256', before, flush=True)


def stage_strip():
    """Remove inherited candidate copper from the COPY only.

    One removal class per PROCESS. Holding any handle (even a plain list of zones)
    across a Save/Load pair leaves a stale SWIG object and the next call aborts with
    'SwigPyObject has no attribute ...' or segfaults. Each class is therefore its own
    subprocess, and every handle is dropped before the board is saved.
    """
    b = pcb.LoadBoard(str(BOARD))
    keep = [z for z in b.Zones() if z.GetIsRuleArea()]
    require(len(keep) == 1, 'expected one board-level rule area, got %d' % len(keep))
    bb = keep[0].GetBoundingBox()
    require(all(abs(v - e) < 1e-6 for v, e in zip(
        [bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6],
        [48, 34, 78, 58])), 'inherited motor reservation is not 48..78 x 34..58')
    before = copper(b)
    del keep, bb, b
    r = subprocess.run([sys.executable, __file__, 'strip_zones'])
    if r.returncode:
        raise SystemExit('strip_zones failed rc=%d' % r.returncode)
    r = subprocess.run([sys.executable, __file__, 'strip_tracks'])
    if r.returncode:
        raise SystemExit('strip_tracks failed rc=%d' % r.returncode)
    b = pcb.LoadBoard(str(BOARD))
    after = copper(b)
    require(after['tracks_and_vias'] == 0 and after['copper_zones'] == 0,
            'copper survived the strip: %s' % after)
    (HERE / 'stripped.json').write_text(json.dumps(
        {'removed_in_copy_only': before, 'remaining': after,
         'source_sha256': sha(SOURCE)}, indent=2) + '\n')
    print('stripped', before, '->', after, flush=True)


def stage_strip_zones():
    b = pcb.LoadBoard(str(BOARD))
    removals = [z for z in list(b.Zones()) if not z.GetIsRuleArea()]
    require(len(removals) > 0, 'no copper zones to remove')
    for z in removals:
        b.Remove(z)
    pcb.SaveBoard(str(BOARD), b)
    print('removed copper zones:', len(removals), flush=True)


def stage_strip_tracks():
    b = pcb.LoadBoard(str(BOARD))
    removals = list(b.GetTracks())
    for t in removals:
        b.Remove(t)
    pcb.SaveBoard(str(BOARD), b)
    print('removed tracks/vias:', len(removals), flush=True)


def stage_place():
    b = pcb.LoadBoard(str(BOARD))
    require(copper(b) == {'tracks_and_vias': 0, 'copper_zones': 0}, 'copper present before moves')
    keep = [z for z in b.Zones() if z.GetIsRuleArea()][0]
    bb = keep.GetBoundingBox()
    keep.Move(pcb.VECTOR2I(pcb.FromMM(MOTOR[0]) - bb.GetLeft(), pcb.FromMM(MOTOR[1]) - bb.GetTop()))
    pcb.SaveBoard(str(BOARD), b)

    b = pcb.LoadBoard(str(BOARD))
    for f in b.GetFootprints():
        x, y, a = SITES[f.GetReference()]
        f.SetPosition(pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y)))
        f.SetOrientationDegrees(a)
    pcb.SaveBoard(str(BOARD), b)

    b = pcb.LoadBoard(str(BOARD))
    for g in list(b.GetDrawings()):
        if g.GetLayer() == pcb.Edge_Cuts:
            g.SetStart(pcb.VECTOR2I(0, 0))
            g.SetEnd(pcb.VECTOR2I(pcb.FromMM(65), pcb.FromMM(50)))
        else:
            b.Remove(g)
    pcb.SaveBoard(str(BOARD), b)
    print('placed', flush=True)


def stage_annotate():
    b = pcb.LoadBoard(str(BOARD))
    for text, x, y in [('DESIGN CANDIDATE 65 x 50 mm - UNROUTED', 32.5, 52.0),
                       ('30 x 24 MOTOR RESERVATION (UNQUALIFIED)', 33.5, 35.2),
                       ('PLACEMENT SIGNOFF REQUIRED - NO ROUTING', 33.5, 38.2)]:
        t = pcb.PCB_TEXT(b)
        t.SetText(text)
        t.SetLayer(pcb.Dwgs_User)
        t.SetPosition(pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y)))
        t.SetTextSize(pcb.VECTOR2I(pcb.FromMM(.7), pcb.FromMM(.7)))
        t.SetTextThickness(pcb.FromMM(.1))
        b.Add(t)
    pcb.SaveBoard(str(BOARD), b)
    print('annotated', flush=True)


def stage_stabilise():
    """Name-based UUIDs so two consecutive builds are byte-identical.

    Native constructors mint random UUIDs (measured: only the 3 annotation texts
    differed between two builds). Geometry is untouched; identity only.
    """
    import uuid as _uuid
    text = BOARD.read_text()
    counter = {'n': 0}

    def stable(m):
        counter['n'] += 1
        return '(uuid "' + str(_uuid.uuid5(_uuid.NAMESPACE_URL,
                                          'pressure-compact/' + str(counter['n']))) + '")'

    new = re.sub(r'\(uuid\s+"?[-0-9a-f]+"?\)', stable, text)
    BOARD.write_text(new)


def courtyard(f):
    lines, rects = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() != pcb.F_CrtYd:
            continue
        a, e = g.GetStart(), g.GetEnd()
        if g.GetShapeStr() == 'Rect':
            rects.append(box(a.x / 1e6, a.y / 1e6, e.x / 1e6, e.y / 1e6))
        else:
            require(g.GetShapeStr() == 'Line', 'unsupported courtyard shape')
            lines.append(LineString([(a.x / 1e6, a.y / 1e6), (e.x / 1e6, e.y / 1e6)]))
    poly = unary_union(rects + list(polygonize(lines)))
    require(not poly.is_empty, 'empty/missing courtyard ' + f.GetReference())
    return poly


def pad_signature(f):
    """Position-independent footprint identity: pads, geometry, layers, nets."""
    sig = []
    for p in f.Pads():
        pos = p.GetPosition() - f.GetPosition()
        sig.append((p.GetNumber(), pos.x, pos.y, p.GetSize().x, p.GetSize().y,
                    p.GetDrillSize().x, p.GetDrillSize().y, int(p.GetShape()),
                    tuple(sorted(pcb.LayerName(l) for l in p.GetLayerSet().Seq())),
                    p.GetNetname()))
    return sorted(sig)


def loop_metrics(fps):
    byref = {f.GetReference(): f for f in fps}

    def pad(ref, num, n=0):
        return [p for p in byref[ref].Pads() if p.GetNumber() == num][n]

    def gap(a, b):
        return round((a.GetPosition() - b.GetPosition()).EuclideanNorm() / 1e6, 2)

    return {'CIN_to_VIN_mm': gap(pad('C4', '1'), pad('U2', '2')),
            'CIN_to_PGND_mm': gap(pad('C4', '2'), pad('U2', '1')),
            'SW_to_L_mm': gap(pad('U2', '7'), pad('L1', '1')),
            'L_to_COUT_mm': gap(pad('L1', '2'), pad('C5', '1')),
            'COUT_to_VOS_mm': gap(pad('C5', '1'), pad('U2', '6')),
            'FB_divider_to_FB_mm': gap(pad('R7', '2'), pad('U2', '5')),
            'sensor_to_inductor_mm': gap(pad('U3', '1'), pad('L1', '2')),
            'sensor_to_S3shield_mm': gap(pad('U3', '1'), pad('U1', '41'))}


def audit(path=None):
    comps, ends = placement.inputs(HERE / 'core.xml')
    b = pcb.LoadBoard(str(path or BOARD))
    fps = list(b.GetFootprints())
    require(len(fps) == 26 and {f.GetReference() for f in fps} == set(comps),
            'reference census mismatch')
    # Layer first: a flipped part's courtyard lives on B.CrtYd and would otherwise be
    # reported as a missing courtyard instead of the real defect (a second-side part).
    for f in fps:
        require(f.GetLayer() == pcb.F_Cu, 'not single-sided: ' + f.GetReference())
    polys = {f.GetReference(): courtyard(f) for f in fps}
    actual = {}
    for f in fps:
        ref = f.GetReference()
        require(f.GetFPID().GetUniStringLibId() == comps[ref].findtext('footprint'),
                'footprint parity ' + ref)
        for p in f.Pads():
            if p.GetNumber():
                key = (ref, p.GetNumber())
                require(ends.get(key) == p.GetNetname(), 'net parity ' + str(key))
                actual[key] = p.GetNetname()
        require(polys[ref].intersection(box(*MOTOR)).area < 1e-8,
                'motor reservation occupied ' + ref)
        require(ref == 'U1' or polys[ref].intersection(box(4, -21.025, 52, 0)).area < 1e-8,
                'antenna keepout occupied ' + ref)
        x0, y0, x1, y1 = polys[ref].bounds
        require(x1 <= 65.0001 and y1 <= 50.0001, 'part outside board ' + ref)
        require(x0 >= -1e-6 or ref == 'J1', 'unexpected west overhang ' + ref)
        require(y0 >= -1e-6 or ref == 'U1', 'unexpected north overhang ' + ref)
    require(actual == ends, 'missing/extra endpoint')
    for i, f in enumerate(fps):
        for g in fps[i + 1:]:
            require(polys[f.GetReference()].intersection(polys[g.GetReference()]).area < 1e-8,
                    'courtyard overlap %s %s' % (f.GetReference(), g.GetReference()))
            for a in f.Pads():
                for c in g.Pads():
                    require(not a.GetBoundingBox().Intersects(c.GetBoundingBox()),
                            'pad overlap %s %s' % (f.GetReference(), g.GetReference()))
    byref = {f.GetReference(): f for f in fps}
    port_box = {}
    require(byref['U1'].GetPosition() == pcb.VECTOR2I(pcb.FromMM(28), pcb.FromMM(6.75))
            and byref['U1'].GetOrientationDegrees() == 0, 'antenna edge datum')
    require(polys['J1'].bounds[0] < -0.5 and polys['J1'].bounds[2] < 8
            and round(byref['J1'].GetOrientationDegrees()) % 360 == 270, 'USB edge access')
    for ref in ['U3', 'U4']:
        require(round(byref[ref].GetOrientationDegrees()) % 360 == 0, 'sensor port orientation ' + ref)
        ports = list(byref[ref].Zones())
        require(len(ports) == 1, 'sensor port keepout missing ' + ref)
        pbb = ports[0].GetBoundingBox()
        port = box(pbb.GetLeft() / 1e6, pbb.GetTop() / 1e6,
                   pbb.GetRight() / 1e6, pbb.GetBottom() / 1e6)
        for other, poly in polys.items():
            if other == ref:
                continue
            require(poly.intersection(port).area < 1e-8,
                    'sensor port access blocked by ' + other + ' on ' + ref)
        port_box[ref] = [round(v, 2) for v in port.bounds]
    require(not list(b.GetTracks()), 'candidate must be unrouted')
    require(all(z.GetIsRuleArea() for z in b.Zones()), 'unexpected copper zone')
    src = pcb.LoadBoard(str(SOURCE))
    src_sig = {f.GetReference(): pad_signature(f) for f in src.GetFootprints()}
    for f in fps:
        require(pad_signature(f) == src_sig[f.GetReference()],
                'footprint geometry/pad signature changed: ' + f.GetReference())
    # Qualified-footprint gate: the pinned library hash must still describe the part.
    pinned = json.loads((ROOT / 'library-sha256.json').read_text())
    for f in fps:
        fid = str(f.GetFPID().GetUniStringLibId())
        lib, name = fid.split(':')
        directory = (ROOT if lib == 'PressureSensor' else Path('/usr/share/kicad/footprints')) / (lib + '.pretty')
        require(fid in pinned, 'footprint not in qualification manifest: ' + fid)
        require(sha(directory / (name + '.kicad_mod')) == pinned[fid],
                'qualified footprint hash drift ' + fid)
    baseline_loops = loop_metrics(list(src.GetFootprints()))
    candidate_loops = loop_metrics(fps)
    # The buck cell is translated as a rigid body, so its internal loop metrics MUST be
    # bit-identical. Sensor-to-buck distance legitimately changes; report it, do not assert.
    rigid = ['CIN_to_VIN_mm', 'CIN_to_PGND_mm', 'SW_to_L_mm', 'L_to_COUT_mm',
             'COUT_to_VOS_mm', 'FB_divider_to_FB_mm']
    for key in rigid:
        require(baseline_loops[key] == candidate_loops[key],
                'rigid buck metric changed: %s %s -> %s'
                % (key, baseline_loops[key], candidate_loops[key]))
    loop_delta = {k: round(candidate_loops[k] - baseline_loops[k], 2)
                  for k in candidate_loops if k not in rigid}
    del src, src_sig
    total = sum(p.area for p in polys.values())
    inside = sum(p.intersection(box(0, 0, 65, 50)).area for p in polys.values())
    return {'references': 26, 'exported_endpoints': len(actual),
            'nets': len({v for v in actual.values()}),
            'side_counts': {'top': 26, 'bottom': 0},
            'footprints_with_courtyard': len(polys),
            'courtyard_area_total_mm2': round(total, 3),
            'courtyard_area_inside_board_mm2': round(inside, 3),
            'board_area_mm2': 3250.0,
            'courtyard_occupancy_percent_inside_board': round(inside / 3250 * 100, 2),
            'courtyard_occupancy_denominator': '65 x 50 mm outline = 3250 mm2; courtyards clipped to the outline',
            'courtyard_total_denominator': 'sum of all 26 courtyard polygons incl. the U1 antenna volume above the north edge',
            'motor_reservation_mm': list(MOTOR), 'motor_area_mm2': 720,
            'tracks': 0, 'vias': 0, 'courtyard_overlaps': 0, 'pad_bbox_overlaps': 0,
            'antenna_keepout_mm': [4, -21.025, 52, 0],
            'sensor_port_keepout_boxes_mm': port_box,
            'buck_cell_origin_shift_mm': -5,
            'power_loop_mm': candidate_loops,
            'power_loop_delta_vs_baseline_mm': loop_delta,
            'power_loop_mm_baseline': baseline_loops,
            'footprint_pad_signature_parity': 'all 26 footprints identical pad geometry/layers/nets vs source board'}


def largest_empty_rect(polys, blocked, x0, y0, x1, y1, step=0.25):
    """Largest axis-aligned empty rectangle by brute force on a coarse grid.

    Bounded by construction (65x50 at 0.25 mm => 260x200 cells), so this is a
    measured headroom figure, not a search for an optimum.
    """
    import math
    nx, ny = int((x1 - x0) / step), int((y1 - y0) / step)
    free = [[True] * ny for _ in range(nx)]
    for i in range(nx):
        cx = x0 + (i + 0.5) * step
        for j in range(ny):
            cy = y0 + (j + 0.5) * step
            from shapely.geometry import Point
            p = Point(cx, cy)
            if any(poly.intersects(p) for poly in polys) or (blocked and blocked.intersects(p)):
                free[i][j] = False
    best = 0.0
    box_best = None
    heights = [0] * ny
    for i in range(nx):
        for j in range(ny):
            heights[j] = heights[j] + 1 if free[i][j] else 0
        stack = []
        for j in range(ny + 1):
            h = heights[j] if j < ny else 0
            start = j
            while stack and stack[-1][1] >= h:
                s, hh = stack.pop()
                area = hh * (j - s) * step * step
                if area > best:
                    best = area
                    box_best = (x0 + (i - hh + 1) * step, y0 + s * step,
                                (hh) * step, (j - s) * step)
                start = s
            stack.append((start, h))
    return round(best, 3), box_best


def stage_space():
    b = pcb.LoadBoard(str(BOARD))
    polys = [courtyard(f) for f in b.GetFootprints()]
    antenna = box(4, -21.025, 52, 0)
    motor = box(*MOTOR)
    free_area = 3250.0 - sum(p.intersection(box(0, 0, 65, 50)).area for p in polys)
    biggest_all, where_all = largest_empty_rect(polys + [antenna], None, 0, 0, 65, 50)
    biggest_outside_motor, where_out = largest_empty_rect(polys + [antenna], motor, 0, 0, 65, 50)
    min_edge = min(min(p.bounds[0] for p in polys if p.bounds[0] >= 0),
                   min(p.bounds[1] for p in polys if p.bounds[1] >= 0),
                   min(65 - p.bounds[2] for p in polys),
                   min(50 - p.bounds[3] for p in polys))
    # Tightest outline that still encloses THIS placement, honouring the two intentional
    # overhangs (U1 antenna over the north edge, J1 USB shell over the west edge).
    need_x1 = max(p.bounds[2] for p in polys)
    need_y1 = max(p.bounds[3] for p in polys)
    need_x0 = min(p.bounds[0] for p in polys if p.bounds[0] >= 0)
    need_y0 = min(p.bounds[1] for p in polys if p.bounds[1] >= 0)
    out = {'courtyard_free_area_inside_board_mm2': round(free_area, 3),
           'tightest_outline_from_this_placement_mm': [round(need_x1, 2), round(need_y1, 2)],
           'placement_extents_mm': [round(need_x0, 2), round(need_y0, 2),
                                    round(need_x1, 2), round(need_y1, 2)],
           'courtyard_free_area_percent': round(free_area / 3250 * 100, 2),
           'largest_single_empty_rectangle_mm2': biggest_all,
           'largest_single_empty_rectangle_at_mm': [round(v, 2) for v in where_all],
           'largest_empty_rectangle_outside_motor_reservation_mm2': biggest_outside_motor,
           'largest_empty_rectangle_outside_motor_at_mm': [round(v, 2) for v in where_out],
           'motor_reservation_fully_empty': bool(sum(p.intersection(motor).area for p in polys) == 0),
           'minimum_courtyard_to_board_edge_mm': round(min_edge, 2),
           'grid_step_mm': 0.25,
           'method': 'brute-force largest axis-aligned empty rectangle on a 0.25 mm grid, courtyards + antenna keepout blocked'}
    (HERE / 'space.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2), flush=True)


def stage_verify():
    subprocess.run(['kicad-cli', 'sch', 'erc', '--format', 'json', '--exit-code-violations',
                    '-o', str(HERE / 'erc.json'), str(ROOT / 'core.kicad_sch')], check=True)
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
                    '-o', str(HERE / 'core.xml'), str(ROOT / 'core.kicad_sch')], check=True)
    (HERE / 'core.xml').write_text(re.sub(r'<date>[^<]*</date>', '<date>NORMALISED</date>',
                                          (HERE / 'core.xml').read_text()))
    proof = audit()
    proof['source_sha256'] = sha(SOURCE)
    proof['source_board_sha256'] = sha(ROOT / 'placement/core-placement.kicad_pcb')
    proof['board_sha256'] = sha(BOARD)
    proof['baseline_dimensions_mm'] = [80, 60]
    proof['candidate_dimensions_mm'] = [65, 50]
    proof['area_reduction_percent'] = round((4800 - 3250) / 4800 * 100, 2)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json',
                    '-o', str(HERE / 'drc.json'), str(BOARD)], check=True)
    d = json.loads((HERE / 'drc.json').read_text())
    proof['native_violations'] = dict(Counter(v['type'] for v in d['violations']))
    proof['native_unconnected_records'] = len(d['unconnected_items'])
    per_net, cross = {}, []
    for rec in d['unconnected_items']:
        nets = set()
        for item in rec['items']:
            m = re.search(r'\[(.*?)\]', item['description'])
            if m:
                nets.add(m.group(1))
        require(len(nets) == 1, 'unconnected record spans different nets: %s' % nets)
        net = next(iter(nets))
        per_net[net] = per_net.get(net, 0) + 1
    proof['native_opens_by_net'] = dict(sorted(per_net.items()))
    proof['native_opens_note'] = ('record counts are DRC spanning-edge accounting, not endpoint '
                                  'connectivity; the per-net split moves with placement geometry')
    # Parity against the UNROUTED baseline (routing/batch0 = the 77-open placement, pre-pour).
    # Same parts, same nets, different geometry: if the per-net open structure is unchanged the
    # placement moved parts without changing what is unconnected.
    base_board = ROOT / 'routing/batch0.kicad_pcb'
    base_report = HERE / 'baseline-drc.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json',
                    '-o', str(base_report), str(base_board)], check=True)
    bd = json.loads(base_report.read_text())
    base_per = {}
    for rec in bd['unconnected_items']:
        nets = {m.group(1) for item in rec['items']
                for m in [re.search(r'\[(.*?)\]', item['description'])] if m}
        require(len(nets) == 1, 'baseline unconnected record spans nets: %s' % nets)
        net = next(iter(nets))
        base_per[net] = base_per.get(net, 0) + 1
    proof['unrouted_baseline'] = {'board': 'routing/batch0.kicad_pcb (80x60, pre-pour)',
                                  'unconnected_records': len(bd['unconnected_items']),
                                  'opens_by_net': dict(sorted(base_per.items())),
                                  'violations': dict(Counter(v['type'] for v in bd['violations']))}
    proof['opens_by_net_parity_with_unrouted_baseline'] = base_per == per_net
    proof['drc_scope'] = 'native kicad-cli pcb drc --severity-all on the candidate copy'
    (HERE / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2), flush=True)
    for side, layers in [('top', 'F.Cu,F.Fab,F.Silkscreen,F.CrtYd,Edge.Cuts,Dwgs.User'),
                         ('bottom', 'B.Cu,B.Fab,B.CrtYd,Edge.Cuts,Dwgs.User')]:
        svg = HERE / (side + '.svg')
        subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers, '--mode-single',
                        '--exclude-drawing-sheet', '--page-size-mode', '2', '-o', str(svg)]
                       + (['--mirror'] if side == 'bottom' else []) + [str(BOARD)], check=True)
        subprocess.run(['rsvg-convert', '-w', '1600', '-o', str(HERE / (side + '.png')), str(svg)],
                       check=True)
    print('views written', flush=True)


STAGES = {'copy': stage_copy, 'strip': stage_strip, 'strip_zones': stage_strip_zones,
          'strip_tracks': stage_strip_tracks, 'place': stage_place,
          'annotate': stage_annotate, 'stabilise': stage_stabilise,
          'space': stage_space, 'verify': stage_verify}

if __name__ == '__main__':
    if len(sys.argv) > 1:
        STAGES[sys.argv[1]]()
    else:
        for name in ['copy', 'strip', 'place', 'annotate', 'stabilise', 'space', 'verify']:
            r = subprocess.run([sys.executable, __file__, name])
            if r.returncode:
                raise SystemExit('stage %s failed rc=%d' % (name, r.returncode))
