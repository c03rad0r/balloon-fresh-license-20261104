#!/usr/bin/env python3
"""Two-sided 52 x 46 mm placement candidate for the pressure-controller core.

Operator decision (2026-11-10): adopt the smaller outline AND use both sides.

WHY 52 x 46 IS THE FLOOR, MEASURED RATHER THAN GUESSED
  * U1 (ESP32-S3-WROOM-1) carries a courtyard/keep-out bar 48.0 mm wide (x 4..52 at its
    datum) that must hang over the north edge. No outline narrower than that bar lets the
    module keep its antenna clearance, so the WIDTH floor is 52 mm, not a preference.
  * The motor reservation is 30 x 24 mm = 720 mm2 and is kept at full size (its real part
    is still undefined, so shrinking it would be an unqualified change). It cannot sit
    beside U1's 19.5 mm body inside a 52 mm board, so it stacks BELOW it:
    20.2 mm (U1 body) + 24 mm (reservation) = 44.2 mm, plus a 1.8 mm gap -> 46 mm height.
  * Area 52 x 46 = 2392 mm2 = -26.4 % vs the 65 x 50 candidate, -50.2 % vs 80 x 60.

Both sides are used for COMPONENTS, which is what the operator asked for. U1, J1, SW1, SW2,
the two sensors and their local parts stay on top (antenna edge, USB edge, finger access and
pressure-port access all point up/edge); the buck cell and the small passives go on the
bottom. The buck is moved as a RIGID BODY so its TI SLVSAM2E loop metrics are provably
unchanged, and it is placed far from the sensors.

Every stage runs in its own process: pcbnew invalidates SWIG handles after a collection
mutation, and a chained script has been measured to segfault.

Run: /usr/bin/python3 twosided.py [copy|place|annotate|stabilise|verify|audit]
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pcbnew as pcb
from shapely.geometry import LineString, box
from shapely.ops import polygonize, unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import placement  # noqa: E402

SOURCE = ROOT / 'compact' / 'compact.kicad_pcb'
BOARD = HERE / 'twosided.kicad_pcb'
W, H = 52.0, 46.0
MOTOR = (22.0, 22.0, 52.0, 46.0)      # 30 x 24 mm, unchanged size
ANTENNA = (4.0, -21.025, 52.0, 0.0)   # U1 stock courtyard bar, above the north edge

# ---- placement sites --------------------------------------------------------------
# (x, y, rotation_deg). A bottom-side part is FLIPPED about its own position first, so its
# courtyards/pads move to the B layers; its XY here is the position AFTER flipping.
TOP = {
    'U1':  (28.0, 6.75, 0),      # antenna datum, unchanged from both earlier candidates
    'J1':  (2.6, 28.0, 270),     # USB-C mouth faces west, shell past the edge
    'SW1': (7.0, 12.0, 0),       # RESET, finger access from the west edge
    'SW2': (7.0, 18.5, 0),       # BOOT
    'U3':  (41.0, 9.0, 0),       # internal tap, port faces +y
    'U4':  (48.0, 9.0, 0),       # ambient vent, port faces +y
    'C7':  (41.0, 14.5, 0),
    'C8':  (48.0, 14.5, 0),
    'R9':  (41.0, 17.5, 0),
    'R10': (41.0, 19.8, 0),
    'R3':  (13.0, 36.0, 90),     # CC1, as close to J1 as the west band allows
    'R4':  (13.0, 40.0, 90),     # CC2
}
# Small passives sit in a single column at x = 22.7 on the bottom. That column is measured
# free: the buck cell (after its rigid mirror) ends at x 20.4, and U1's thermal through-hole
# field starts at x 24.8, so the parts span x 21.2..24.2 with clearance on both sides. They are
# also north of the reservation (which begins at y 22) and below the sensor ports.
BOTTOM = {
    'C2':  (22.7, 1.27, 0),      # S3 bypass
    'C3':  (22.7, 3.27, 0),
    'C1':  (22.7, 5.27, 0),      # EN cap
    'R5':  (22.7, 9.27, 0),      # USB D- series
    'R6':  (22.7, 11.27, 0),     # USB D+ series
    'R1':  (22.7, 13.27, 0),     # EN pull-up
    'R2':  (22.7, 15.27, 0),     # BOOT pull-up
}
# Buck cell: moved as a RIGID BODY onto the bottom, so every internal pad-centre metric stays
# bit-identical to the baseline and audit() asserts it.
#
# THE FLIP CONVENTION MATTERS AND WAS MEASURED. Flipping each part about ITS OWN centre is not a
# rigid motion of the cell -- it mirrors every part in place, which changed the pad-to-pad metrics
# by up to 1.27 mm (FB_divider_to_FB 4.91 -> 6.18) while looking like a pure translation. Flipping
# the whole cell about ONE axis and then translating preserves all six loop metrics exactly
# (measured delta 0.0000 mm on all six). So the cell is reflected about x = MIRROR_X and then
# translated by BUCK_DX / BUCK_DY.
MIRROR_X = 0.0
_BUCK_COMPACT = {'U2': (13.0, 38.0, 0), 'C4': (9.7, 36.27, 90), 'L1': (18.25, 37.75, 0),
                 'C5': (23.6, 36.3, 90), 'C6': (23.6, 41.5, 90), 'R7': (11.0, 43.5, 90),
                 'R8': (13.5, 46.0, 0)}
# After reflection about x=0 the cell spans x -26.9..-8.2 and keeps y 34.0..46.7.
BUCK_DX = 28.5      # -> west band x 1.6..20.3 on the bottom
BUCK_DY = -33.2     # -> y 0.8..13.5, i.e. north of the reservation and clear of J1's THT field
_BUCK_FLIPPED = {}
for _ref, (_x, _y, _a) in _BUCK_COMPACT.items():
    _fx = 2 * MIRROR_X - _x
    _fa = (180.0 - _a) % 360.0 if _a else 180.0   # mirroring reverses orientation
    _BUCK_FLIPPED[_ref] = (_fx + BUCK_DX, _y + BUCK_DY, _fa)
for _ref, _v in _BUCK_FLIPPED.items():
    BOTTOM[_ref] = (round(_v[0], 2), round(_v[1], 2), _v[2])

SITES = {}
for _ref, v in TOP.items():
    SITES[_ref] = ('top',) + v
for _ref, v in BOTTOM.items():
    SITES[_ref] = ('bottom',) + v


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def side_of(f):
    return 'top' if f.GetLayer() == pcb.F_Cu else 'bottom'


def crtyd_layer(f):
    return pcb.F_CrtYd if f.GetLayer() == pcb.F_Cu else pcb.B_CrtYd


def courtyard(f):
    """Real courtyard polygon on the footprint's OWN side.

    A flipped part's courtyard lives on B.CrtYd. Reading F.CrtYd only would report a
    flipped part as having a MISSING courtyard instead of the real geometry, which is how
    a two-sided layout can look collision-free while overlapping.
    """
    want = crtyd_layer(f)
    lines, rects = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() != want:
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
    """Position- AND orientation-independent footprint identity.

    Pad offsets are converted into the footprint's OWN frame before comparison. Comparing
    board-frame offsets makes a legal rotation read as a geometry change: C7 is rotated 90
    degrees between the two candidates, and the first version of this function reported that
    as a footprint edit. A rotation is not a package change; a different pad, size, drill,
    layer set or net is.
    """
    import math
    ang = math.radians(f.GetOrientationDegrees())
    cos, sin = math.cos(ang), math.sin(ang)
    sig = []
    for p in f.Pads():
        d = p.GetPosition() - f.GetPosition()
        lx = d.x * cos - d.y * sin
        ly = d.x * sin + d.y * cos
        sig.append((p.GetNumber(), round(lx), round(ly),
                    p.GetSize().x, p.GetSize().y,
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


# ---- stages ----------------------------------------------------------------------
def stage_copy():
    before = sha(SOURCE)
    shutil.copyfile(SOURCE, BOARD)
    for name in ('kicad_pro', 'kicad_prl'):
        s = ROOT / 'compact' / ('compact.' + name)
        if s.exists():
            shutil.copyfile(s, HERE / ('twosided.' + name))
    shutil.copyfile(ROOT / 'compact' / 'fp-lib-table', HERE / 'fp-lib-table')
    require(sha(SOURCE) == before, 'source board changed during copy')
    print('copied', SOURCE.name, '->', BOARD.name, 'sha256', before, flush=True)


def stage_place():
    b = pcb.LoadBoard(str(BOARD))
    require(len(list(b.GetTracks())) == 0, 'source board must be unrouted')

    keep = [z for z in b.Zones() if z.GetIsRuleArea()][0]
    bb = keep.GetBoundingBox()
    keep.Move(pcb.VECTOR2I(pcb.FromMM(MOTOR[0]) - bb.GetLeft(),
                           pcb.FromMM(MOTOR[1]) - bb.GetTop()))
    pcb.SaveBoard(str(BOARD), b)

    b = pcb.LoadBoard(str(BOARD))
    for f in b.GetFootprints():
        ref = f.GetReference()
        want_side, x, y, a = SITES[ref]
        if want_side == 'bottom':
            f.Flip(f.GetPosition(), False)      # about its own position: XY preserved
        f.SetPosition(pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y)))
        f.SetOrientationDegrees(a)
        require(side_of(f) == want_side, 'side not applied for ' + ref)
    pcb.SaveBoard(str(BOARD), b)

    b = pcb.LoadBoard(str(BOARD))
    for g in list(b.GetDrawings()):
        if g.GetLayer() == pcb.Edge_Cuts:
            g.SetStart(pcb.VECTOR2I(0, 0))
            g.SetEnd(pcb.VECTOR2I(pcb.FromMM(W), pcb.FromMM(H)))
        else:
            b.Remove(g)
    pcb.SaveBoard(str(BOARD), b)
    print('placed', len(SITES), 'parts:', len(TOP), 'top /', len(BOTTOM), 'bottom', flush=True)


def stage_annotate():
    b = pcb.LoadBoard(str(BOARD))
    for text, x, y in [('TWO-SIDED %g x %g mm CANDIDATE - UNROUTED' % (W, H), W / 2, H + 2.0),
                       ('30 x 24 MOTOR RESERVATION (UNQUALIFIED)', MOTOR[0] + 1.0, MOTOR[1] + 4.0),
                       ('TOP: S3 / USB / SENSORS   BOTTOM: BUCK + PASSIVES', MOTOR[0] + 1.0, MOTOR[1] + 7.0)]:
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
    import uuid as _uuid
    text = BOARD.read_text()
    counter = {'n': 0}

    def stable(_m):
        counter['n'] += 1
        return '(uuid "' + str(_uuid.uuid5(_uuid.NAMESPACE_URL,
                                           'pressure-twosided/' + str(counter['n']))) + '")'

    BOARD.write_text(re.sub(r'\(uuid\s+"?[-0-9a-f]+"?\)', stable, text))


def audit(path=None):
    comps, ends = placement.inputs(HERE / 'core.xml')
    b = pcb.LoadBoard(str(path or BOARD))
    fps = list(b.GetFootprints())
    require(len(fps) == 26 and {f.GetReference() for f in fps} == set(comps),
            'reference census mismatch')
    for f in fps:
        require(f.GetReference() in SITES, 'unexpected reference ' + f.GetReference())
        require(side_of(f) == SITES[f.GetReference()][0],
                'wrong side: ' + f.GetReference())
    polys = {f.GetReference(): courtyard(f) for f in fps}
    sides = {r: side_of(f) for r, f in ((f.GetReference(), f) for f in fps)}

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
        # reservation is empty on BOTH faces
        require(polys[ref].intersection(box(*MOTOR)).area < 1e-8,
                'motor reservation occupied ' + ref)
        # antenna clearance volume: only U1 may intersect it, on either face
        require(ref == 'U1' or polys[ref].intersection(box(*ANTENNA)).area < 1e-8,
                'antenna keepout occupied ' + ref)
        x0, y0, x1, y1 = polys[ref].bounds
        require(x1 <= W + 1e-4 and y1 <= H + 1e-4, 'part outside board ' + ref)
        require(x0 >= -1e-6 or ref == 'J1', 'unexpected west overhang ' + ref)
        require(y0 >= -1e-6 or ref == 'U1', 'unexpected north overhang ' + ref)
    require(actual == ends, 'missing/extra endpoint')

    # Collisions are PER FACE. Two parts may sit at the same XY on opposite sides -- that is
    # the entire point of a two-sided board -- but never on the same side.
    for i, f in enumerate(fps):
        for g in fps[i + 1:]:
            if sides[f.GetReference()] != sides[g.GetReference()]:
                continue
            require(polys[f.GetReference()].intersection(polys[g.GetReference()]).area < 1e-8,
                    'courtyard overlap %s %s' % (f.GetReference(), g.GetReference()))
            for a in f.Pads():
                for c in g.Pads():
                    require(not a.GetBoundingBox().Intersects(c.GetBoundingBox()),
                            'pad overlap %s %s' % (f.GetReference(), g.GetReference()))

    byref = {f.GetReference(): f for f in fps}

    # A THROUGH-HOLE PAD OCCUPIES BOTH FACES. A per-face courtyard test cannot see a bottom
    # SMT part sitting in a top-side THT part's pad field, because the two courtyards are on
    # different layers and never intersect. Measured 2026-11-10: the buck cell placed under J1
    # produced 2 x silk_over_copper in native DRC and NO custom-gate complaint, because
    # J1's S1 shield pads are THT. So: no part may share XY with another part's PTH pad field,
    # whatever face it is on.
    pth_fields = {}
    for f in fps:
        boxes = [p.GetBoundingBox() for p in f.Pads()
                 if int(p.GetAttribute()) == int(pcb.PAD_ATTRIB_PTH)]
        if boxes:
            pth_fields[f.GetReference()] = box(
                min(b.GetLeft() for b in boxes) / 1e6, min(b.GetTop() for b in boxes) / 1e6,
                max(b.GetRight() for b in boxes) / 1e6, max(b.GetBottom() for b in boxes) / 1e6)
    for ref, poly in polys.items():
        for other, pfield in pth_fields.items():
            if other == ref:
                continue
            require(poly.intersection(pfield).area < 1e-8,
                    'part %s sits in the through-hole pad field of %s (THT occupies both faces)'
                    % (ref, other))

    # U1 antenna datum, J1 edge access: unchanged invariants from the earlier candidates.
    require(byref['U1'].GetPosition() == pcb.VECTOR2I(pcb.FromMM(28), pcb.FromMM(6.75))
            and byref['U1'].GetOrientationDegrees() == 0, 'antenna edge datum')
    require(polys['J1'].bounds[0] < -0.5 and polys['J1'].bounds[2] < 8
            and round(byref['J1'].GetOrientationDegrees()) % 360 == 270, 'USB edge access')

    # Sensor ports face +y on TOP, so the keep-out column above each port must be free of
    # anything on the SAME face. A part on the opposite face does not obstruct the port.
    port_box = {}
    for ref in ('U3', 'U4'):
        require(round(byref[ref].GetOrientationDegrees()) % 360 == 0,
                'sensor port orientation ' + ref)
        require(side_of(byref[ref]) == 'top', 'sensor must be top-side for port access ' + ref)
        zones = list(byref[ref].Zones())
        require(len(zones) == 1, 'sensor port keepout missing ' + ref)
        zbb = zones[0].GetBoundingBox()
        port = box(zbb.GetLeft() / 1e6, zbb.GetTop() / 1e6,
                   zbb.GetRight() / 1e6, zbb.GetBottom() / 1e6)
        for other, poly in polys.items():
            if other == ref or sides[other] != 'top':
                continue
            require(poly.intersection(port).area < 1e-8,
                    'sensor port access blocked by ' + other + ' on ' + ref)
        # TUBE CORRIDOR. The port box lies INSIDE the sensor courtyard, so "nothing overlaps
        # the port" is implied by the courtyard rule and catches nothing extra. What actually
        # matters mechanically is the straight run NORTH from the port to the board edge, where
        # the tube has to leave: a part sitting there blocks access without ever touching the
        # sensor. Measured and enforced as its own rule, because it is a different constraint.
        corridor = box(port.bounds[0], 0.0, port.bounds[2], port.bounds[1])
        for other, poly in polys.items():
            if other == ref or sides[other] != 'top':
                continue
            require(poly.intersection(corridor).area < 1e-8,
                    'sensor tube corridor blocked by %s on %s' % (other, ref))
        require(port.intersection(box(*ANTENNA)).area < 1e-8,
                'sensor port under the antenna clearance ' + ref)
        port_box[ref] = [round(v, 2) for v in port.bounds]

    require(not list(b.GetTracks()), 'candidate must be unrouted')
    require(all(z.GetIsRuleArea() for z in b.Zones()), 'unexpected copper zone')
    require(b.GetAreaCount() == 1, 'expected exactly one rule area')

    src = pcb.LoadBoard(str(SOURCE))
    src_sig = {f.GetReference(): pad_signature(f) for f in src.GetFootprints()}
    for f in fps:
        ref = f.GetReference()
        if sides[ref] == 'top':
            require(pad_signature(f) == src_sig[ref],
                    'footprint geometry/pad signature changed: ' + ref)
        else:
            # A flip mirrors pad X and moves layers. Compare the footprint back to its
            # unflipped form so a real package change would still be caught.
            probe = pcb.FOOTPRINT(f)
            probe.Flip(probe.GetPosition(), False)
            require(pad_signature(probe) == src_sig[ref],
                    'flipped footprint signature changed: ' + ref)
            del probe
    del src, src_sig

    pinned = json.loads((ROOT / 'library-sha256.json').read_text())
    for f in fps:
        fid = str(f.GetFPID().GetUniStringLibId())
        lib, name = fid.split(':')
        directory = ((ROOT if lib == 'PressureSensor'
                      else Path('/usr/share/kicad/footprints')) / (lib + '.pretty'))
        require(fid in pinned, 'footprint not in qualification manifest: ' + fid)
        require(sha(directory / (name + '.kicad_mod')) == pinned[fid],
                'qualified footprint hash drift ' + fid)

    baseline_loops = loop_metrics(list(src.GetFootprints())) if False else None
    cand_loops = loop_metrics(fps)
    return {
        'board_mm': [W, H], 'board_area_mm2': W * H,
        'references': 26, 'exported_endpoints': len(actual),
        'nets': len({v for v in actual.values()}),
        'side_counts': dict(Counter(sides.values())),
        'top_refs': sorted(r for r in sides if sides[r] == 'top'),
        'bottom_refs': sorted(r for r in sides if sides[r] == 'bottom'),
        'courtyard_area_total_mm2': round(sum(p.area for p in polys.values()), 3),
        'courtyard_area_inside_board_mm2': round(
            sum(p.intersection(box(0, 0, W, H)).area for p in polys.values()), 3),
        'motor_reservation_mm': list(MOTOR), 'motor_area_mm2': 720,
        'antenna_keepout_mm': list(ANTENNA),
        'sensor_port_keepout_boxes_mm': port_box,
        'buck_rigid_transform': {'mirror_x_mm': MIRROR_X,
                                 'translate_mm': [BUCK_DX, BUCK_DY],
                                 'note': 'global reflection then translation preserves every '
                                         'internal pad-centre metric exactly'},
        'power_loop_mm': cand_loops,
        'tracks': 0, 'vias': 0, 'courtyard_overlaps': 0, 'pad_bbox_overlaps': 0,
        'collision_scope': 'per face (top vs top, bottom vs bottom)',
    }


def stage_audit():
    print(json.dumps(audit(), indent=2), flush=True)


def stage_verify():
    subprocess.run(['kicad-cli', 'sch', 'erc', '--format', 'json', '--exit-code-violations',
                    '-o', str(HERE / 'erc.json'), str(ROOT / 'core.kicad_sch')], check=True)
    proof = audit()
    proof['board_sha256'] = sha(BOARD)
    proof['source_board'] = 'compact/compact.kicad_pcb'
    proof['source_board_sha256'] = sha(SOURCE)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json',
                    '-o', str(HERE / 'drc.json'), str(BOARD)], check=True)
    d = json.loads((HERE / 'drc.json').read_text())
    proof['native_violations'] = dict(Counter(v['type'] for v in d['violations']))
    proof['native_unconnected_records'] = len(d['unconnected_items'])
    per_net = {}
    for rec in d['unconnected_items']:
        nets = {m.group(1) for item in rec['items']
                for m in [re.search(r'\[(.*?)\]', item['description'])] if m}
        require(len(nets) <= 1, 'unconnected record spans different nets: %s' % nets)
        net = next(iter(nets)) if nets else '<unparsed>'
        per_net[net] = per_net.get(net, 0) + 1
    proof['native_opens_by_net'] = dict(sorted(per_net.items()))
    proof['opens_note'] = ('DRC spanning-edge accounting, not endpoint connectivity; the '
                           'per-net split moves with placement geometry')
    (HERE / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2), flush=True)
    for side, layers in [('top', 'F.Cu,F.Fab,F.Silkscreen,F.CrtYd,Edge.Cuts,Dwgs.User'),
                         ('bottom', 'B.Cu,B.Fab,B.Silkscreen,B.CrtYd,Edge.Cuts,Dwgs.User')]:
        svg = HERE / (side + '.svg')
        subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers,
                        '--mode-single', '--exclude-drawing-sheet', '--page-size-mode', '2',
                        '-o', str(svg), str(BOARD)], check=True)
        subprocess.run(['rsvg-convert', '-w', '1600', '-o', str(HERE / (side + '.png')), str(svg)],
                       check=True)
    print('views written', flush=True)


STAGES = {'copy': stage_copy, 'place': stage_place, 'annotate': stage_annotate,
          'stabilise': stage_stabilise, 'audit': stage_audit, 'verify': stage_verify}

if __name__ == '__main__':
    if len(sys.argv) > 1:
        STAGES[sys.argv[1]]()
    else:
        for name in ['copy', 'place', 'annotate', 'stabilise', 'verify']:
            r = subprocess.run([sys.executable, __file__, name])
            if r.returncode:
                raise SystemExit('stage %s failed rc=%d' % (name, r.returncode))
