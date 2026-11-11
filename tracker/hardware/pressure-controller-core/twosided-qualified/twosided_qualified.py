#!/usr/bin/env python3
"""Two-sided 52 x 46 mm placement candidate for the pressure-controller core.

STATUS: DESIGN CANDIDATE - NOT ROUTED - NOT FAB READY - PENDING OPERATOR PLACEMENT SIGN-OFF.

Derived from the actual 26-part / 125-endpoint schematic export and the committed
80 x 60 placement checkpoint on master (04219c23). The source board is NEVER written.

WHY THIS FILE EXISTS (vs. the uncommitted 2026-11-10 probe)
  The probe measured 52 x 46 = 2392 mm2 and showed a second side really buys area. But it
  took two placement liberties that no gate on the probe could see, because the probe's own
  audit skips exactly those pairs:

  (1) It moved U1's OWN decoupling capacitors (C1/C2/C3) and the buck input capacitor C4 to
      B.Cu directly under the module body, inside the 6 mm band behind the antenna.
      Measured intrusion into that band: 19.405 mm2 over 4 parts (compact candidate: 0.000).
      Espressif's ESP32-S3 Hardware Design Guidelines state, for the 2-layer stack-up this
      board actually is: "Layer 2 (BOTTOM): Do not place any components on this layer".
      AGENTS.md 1b point 2 independently forbids moving decoupling capacitors away from their
      IC without a harmlessness proof. Both are violated by the probe.
  (2) Its audit's cross-side rule (`if sides differ: continue`) cannot see (1) either, so the
      probe reported 0 courtyard overlaps while 19.4 mm2 of bottom copper sat under the module.

  This generator restores a module-body + antenna keepout as a RULE AREA on B.Cu, re-packs
  inside it, and reports the measured size cost of doing so.

WHY 52 x 46 IS THE FLOOR, MEASURED RATHER THAN GUESSED
  * U1 (ESP32-S3-WROOM-1, PCB-antenna variant) carries a courtyard/keep-out bar 48.0 mm wide
    (x 4..52 at its datum) that must hang over the north edge. No outline narrower than that
    bar lets the module keep its antenna clearance, so the WIDTH floor is 52 mm.
  * The motor reservation is 30 x 24 mm = 720 mm2 and is kept at full size (its real part is
    still undefined, so shrinking it would be an unqualified change). It cannot sit beside
    U1's 19.5 mm body inside a 52 mm board, so it stacks BELOW it:
    20.2 mm (U1 body) + 24 mm (reservation) = 44.2 mm, plus a 1.8 mm gap -> 46 mm height.
  * Area 52 x 46 = 2392 mm2 = -26.4 % vs the 65 x 50 candidate, -50.2 % vs 80 x 60.

SIDE ASSIGNMENT (and why it differs from the probe: 19 top / 7 bottom, not 12 / 14)
  TOP    U1, J1, the two switches, both sensors + their local parts, the USB/EN/BOOT passives
         and U1's decoupling capacitors. U1's decoupling MUST stay beside the module because
         a via loop in a 3V3 bypass path is exactly what AGENTS.md 1b point 2 forbids moving
         without proof; the probe has no such proof.
  BOTTOM the buck cell ONLY (U2, L1, C4, C5, C6, R7, R8). It is moved as a RIGID BODY so its
         TI SLVSAM2E section 11.1 loop metrics are provably unchanged, and it is the one block
         whose internal adjacency survives a side move intact.

Both sides are used for COMPONENTS, which is what the operator asked for.

Every stage runs in its own process: pcbnew invalidates SWIG handles after a collection
mutation, and a chained script has been measured to segfault.

Run: /usr/bin/python3 twosided_qualified.py [copy|strip|place|annotate|stabilise|verify|audit]
"""
import hashlib
import json
import math
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

SOURCE = ROOT / 'placement' / 'core-placement.kicad_pcb'
BOARD = HERE / 'twosided-qualified.kicad_pcb'
W, H = 52.0, 46.0
MOTOR = (22.0, 22.0, 52.0, 46.0)          # 30 x 24 mm, unchanged size
# U1's stock courtyard is a T, not a rectangle: an antenna bar 48 mm wide hanging 21 mm above
# the north edge, plus a 19.5 x 20.2 mm body. The flanks beside the body are OUTSIDE the
# polygon, which is why the probe's "inside U1's courtyard" framing is wrong for U3/U4/C7/C8/
# R9/R10 - those sit in the flanks, exactly as the adopted compact candidate did.
ANTENNA_BAR = (4.0, -21.0, 52.0, 0.0)
MODULE_BODY = (18.25, 0.0, 37.75, 20.2)
# The keepout restored by this candidate: the module body plus the antenna bar, on B.Cu.
# The antenna bar half lies off-board (y<0) and is included so the rule area is one honest
# polygon rather than a body-only box that would silently allow copper under the antenna.
MODULE_KEEPOUT = (18.25, -21.0, 37.75, 20.2)

# ---- placement sites --------------------------------------------------------------
# (x, y, rotation_deg). A bottom-side part is FLIPPED about its own position first, so its
# courtyards/pads move to the B layers; its XY here is the position AFTER flipping.
TOP = {
    'U1':  (28.0, 6.75, 0),      # antenna datum, unchanged from both earlier candidates
    'J1':  (2.6, 28.0, 270),     # USB-C mouth faces west, shell past the edge
    'SW1': (7.0, 12.0, 0),       # RESET, finger access from the west edge
    'SW2': (7.0, 18.5, 0),       # BOOT
    # U1 decoupling + pull-ups: kept BESIDE the module in the west flank, on the SAME side as
    # U1, exactly as the adopted compact candidate had them. The probe moved these to B.Cu
    # under the module body; measured band intrusion 19.405 mm2. See MODULE_KEEPOUT.
    'C1':  (16.0, 6.0, 0),       # EN cap
    'C2':  (16.0, 2.0, 0),       # S3 bypass
    'C3':  (16.0, 4.0, 0),       # S3 bypass
    # R1 sits in the same column, NOT at (13,6): U2's drilled thermal-via field lands at
    # x 12.7..13.3 y 4.0..5.6 on the bottom, and a plated through-hole is drilled through, so
    # a top-side part there would sit in the hole field. Measured and refused by audit().
    'R1':  (16.0, 8.0, 0),       # EN pull-up
    'R5':  (16.0, 16.0, 0),      # USB D- series
    'R6':  (16.0, 18.0, 0),      # USB D+ series
    'U3':  (41.0, 9.0, 0),       # internal tap, port faces +y
    'U4':  (48.0, 9.0, 0),       # ambient vent, port faces +y
    'C7':  (41.0, 14.5, 0),
    'C8':  (48.0, 14.5, 0),
    'R9':  (41.0, 17.5, 0),
    'R10': (41.0, 19.8, 0),
    'R2':  (44.5, 18.0, 0),      # BOOT pull-up, east flank (was under the module in the probe)
    'R3':  (13.0, 36.0, 90),     # CC1
    'R4':  (13.0, 40.0, 90),     # CC2
}
# Buck cell: moved as a RIGID BODY onto the bottom, so every internal pad-centre metric stays
# bit-identical to the baseline and audit() asserts it.
#
# THE FLIP CONVENTION MATTERS AND WAS MEASURED. Flipping each part about ITS OWN centre is not
# a rigid motion of the cell -- it mirrors every part in place, which changed the pad-to-pad
# metrics by up to 1.27 mm (FB_divider_to_FB 4.91 -> 6.18) while looking like a pure
# translation. Flipping the whole cell about ONE axis and then translating preserves all six
# loop metrics exactly. So the cell is reflected about x = MIRROR_X and then translated.
MIRROR_X = 0.0
_BUCK_COMPACT = {'U2': (13.0, 43.0, 0), 'C4': (9.7, 41.27, 90), 'L1': (18.25, 42.75, 0),
                 'C5': (23.6, 41.3, 90), 'C6': (23.6, 46.5, 90), 'R7': (11.0, 48.5, 90),
                 'R8': (13.5, 51.0, 0)}
# After reflection about x=0 the cell spans x -26.9..-8.2 and keeps y 39.0..51.7.
# BUCK_DX = 26.0 puts the cell at x 0.8..17.9, i.e. 0.35 mm clear of the restored module
# keepout's west edge at x = 18.25. The probe used 28.5 (= 20.3), which put C4 2.15 mm inside
# the module body. BUCK_DY = -38.2 -> y 0.8..13.5, north of the motor reservation and clear
# of J1's through-hole field.
BUCK_DX = 26.0
BUCK_DY = -38.2
_BUCK_FLIPPED = {}
for _ref, (_x, _y, _a) in _BUCK_COMPACT.items():
    _fx = 2 * MIRROR_X - _x
    _fa = (180.0 - _a) % 360.0 if _a else 180.0   # mirroring reverses orientation
    _BUCK_FLIPPED[_ref] = (_fx + BUCK_DX, _y + BUCK_DY, _fa)

BOTTOM = {r: (round(v[0], 2), round(v[1], 2), v[2]) for r, v in _BUCK_FLIPPED.items()}

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
        if not hasattr(g, 'GetShapeStr'):
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
    """Position- AND orientation-independent footprint identity."""
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


def pth_fields(fps):
    """Bounding box of every footprint's plated through-hole pad field.

    A THROUGH-HOLE PAD OCCUPIES BOTH FACES. A per-face courtyard test cannot see a bottom
    SMT part sitting in a top-side THT part's pad field, because the two courtyards are on
    different layers and never intersect. Measured 2026-11-10: the buck cell placed under J1
    produced silk_over_copper in native DRC and NO custom-gate complaint, because J1's S1
    shield pads are THT.
    """
    out = {}
    for f in fps:
        boxes = [p.GetBoundingBox() for p in f.Pads()
                 if int(p.GetAttribute()) == int(pcb.PAD_ATTRIB_PTH)]
        if boxes:
            out[f.GetReference()] = box(
                min(b.GetLeft() for b in boxes) / 1e6, min(b.GetTop() for b in boxes) / 1e6,
                max(b.GetRight() for b in boxes) / 1e6, max(b.GetBottom() for b in boxes) / 1e6)
    return out


# ---- stages ----------------------------------------------------------------------
def stage_copy():
    before = sha(SOURCE)
    shutil.copyfile(SOURCE, BOARD)
    for name in ('kicad_pro', 'kicad_prl'):
        s = ROOT / 'placement' / ('core-placement.' + name)
        if s.exists():
            shutil.copyfile(s, HERE / ('twosided-qualified.' + name))
    shutil.copyfile(ROOT / 'placement' / 'fp-lib-table', HERE / 'fp-lib-table')
    require(sha(SOURCE) == before, 'source board changed during copy')
    print('copied', SOURCE.name, '->', BOARD.name, 'sha256', before, flush=True)


def stage_strip_zones():
    b = pcb.LoadBoard(str(BOARD))
    removals = [z for z in list(b.Zones()) if not z.GetIsRuleArea()]
    require(len(removals) > 0, 'no copper zones to remove')
    n = len(removals)
    for z in removals:
        b.Remove(z)
    pcb.SaveBoard(str(BOARD), b)
    print('removed copper zones:', n, flush=True)


def stage_strip_tracks():
    b = pcb.LoadBoard(str(BOARD))
    removals = list(b.GetTracks())
    n = len(removals)
    for t in removals:
        b.Remove(t)
    pcb.SaveBoard(str(BOARD), b)
    print('removed tracks/vias:', n, flush=True)


def stage_strip():
    """Remove inherited candidate copper from the COPY only, one class per process."""
    b = pcb.LoadBoard(str(BOARD))
    keep = [z for z in b.Zones() if z.GetIsRuleArea()]
    require(len(keep) == 1, 'expected one board-level rule area, got %d' % len(keep))
    before = {'tracks_and_vias': len(list(b.GetTracks())),
              'copper_zones': sum(1 for z in b.Zones() if not z.GetIsRuleArea())}
    del keep, b
    for stage in ('strip_zones', 'strip_tracks'):
        r = subprocess.run([sys.executable, __file__, stage])
        if r.returncode:
            raise SystemExit('%s failed rc=%d' % (stage, r.returncode))
    b = pcb.LoadBoard(str(BOARD))
    after = {'tracks_and_vias': len(list(b.GetTracks())),
             'copper_zones': sum(1 for z in b.Zones() if not z.GetIsRuleArea())}
    require(after == {'tracks_and_vias': 0, 'copper_zones': 0},
            'copper survived the strip: %s' % after)
    (HERE / 'stripped.json').write_text(json.dumps(
        {'removed_in_copy_only': before, 'remaining': after,
         'source_sha256': sha(SOURCE)}, indent=2) + '\n')
    print('stripped', before, '->', after, flush=True)


def _add_rule_area(b, rect, layers, name):
    """Board-level rule area forbidding ROUTED copper in `rect` on `layers`.

    Scope is deliberate and was measured, not assumed. Setting DoNotAllowPads /
    DoNotAllowFootprints here produced 12 `items_not_allowed` ERRORs -- all twelve were
    "PTH pad 41 [/GND] of U1", i.e. the module's OWN thermal-via array, which necessarily
    sits inside its own body region. KiCad 9 rule-area zones have no per-footprint exemption
    scope (there is no SetRuleAreaFootprintFilter; the only setters are the five
    DoNotAllow* booleans and SetZoneName), so a pads-forbidding zone cannot express
    "no pads except U1's". The component constraint is therefore enforced by the audit's
    geometric test, which measures real courtyard extents and exempts U1 explicitly --
    while the ZONE still gives the router a hard, native-DRC-enforced obstacle for tracks,
    vias and pours, which is the part a router would otherwise ignore.
    """
    z = pcb.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcb.LSET()
    for lay in layers:
        ls.AddLayer(lay)
    z.SetLayerSet(ls)
    x0, y0, x1, y1 = rect
    poly = z.Outline()
    poly.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        poly.Append(pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y)))
    b.Add(z)
    return z


def stage_place():
    b = pcb.LoadBoard(str(BOARD))
    require(len(list(b.GetTracks())) == 0, 'source board must be unrouted')

    # Move the inherited motor reservation to its new rectangle.
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

    # Restore the module-body + antenna keepout on B.Cu as a REAL rule area. This is the
    # measured response to the probe's 19.405 mm2 of bottom copper under the module.
    b = pcb.LoadBoard(str(BOARD))
    _add_rule_area(b, MODULE_KEEPOUT, [pcb.B_Cu], 'module-under-body')
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
    for text, x, y in [('TWO-SIDED %g x %g mm CANDIDATE - UNROUTED - NOT FAB READY' % (W, H),
                        W / 2, H + 2.0),
                       ('30 x 24 MOTOR RESERVATION (UNQUALIFIED)', MOTOR[0] + 1.0, MOTOR[1] + 4.0),
                       ('BOTTOM: BUCK CELL ONLY   TOP: S3 / USB / SENSORS / DECOUPLING',
                        MOTOR[0] + 1.0, MOTOR[1] + 7.0)]:
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
                                           'pressure-twosided-qualified/' + str(counter['n']))) + '")'

    BOARD.write_text(re.sub(r'\(uuid\s+"?[-0-9a-f]+"?\)', stable, text))


def audit(path=None):
    """Full placement gate. Re-loads the board from disk and aborts on any failure."""
    b = pcb.LoadBoard(str(path or BOARD))
    fps = list(b.GetFootprints())
    comps = {f.GetReference(): f for f in fps}
    require(len(fps) == 26, 'reference census: expected 26, got %d' % len(fps))
    for f in fps:
        require(f.GetReference() in SITES, 'unexpected reference ' + f.GetReference())
        require(side_of(f) == SITES[f.GetReference()][0],
                'wrong side: ' + f.GetReference())

    polys = {f.GetReference(): courtyard(f) for f in fps}
    sides = {r: side_of(comps[r]) for r in comps}

    # --- netlist parity against the fresh native XML export.
    # Denominators are taken from the XML, NOT from the board: the board carries 147 numbered
    # pads because U1's thermal array has 13 pads sharing number 41 and 9 paste-only apertures.
    # XML: 51 nets / 125 nodes / 26 components. Board: 51 distinct pad netnames of which 15
    # are real nets and 36 are KiCad's per-pin "unconnected-(...)" placeholders for the 36
    # unused ESP32 GPIOs. Both numbers are reported so neither is silently substituted.
    import xml.etree.ElementTree as ET
    root = ET.parse(ROOT / 'core.xml').getroot()
    xml_nets = {n.get('code'): n.get('name') for n in root.find('nets').findall('net')}
    require(len(xml_nets) == 51, 'XML net census: expected 51, got %d' % len(xml_nets))
    xml_nodes = sum(len(n.findall('node')) for n in root.find('nets').findall('net'))
    require(xml_nodes == 125, 'XML endpoint census: expected 125, got %d' % xml_nodes)
    require(len(root.find('components').findall('comp')) == 26, 'XML component census')

    # Count PADS, not distinct (ref, number) keys: U1's thermal array has 13 pads all numbered
    # 41, so a dict keyed by (ref, number) silently collapses them and reports 125 "endpoints"
    # that only COINCIDENTALLY equals the XML node count. Measured: the real numbered-pad
    # count is higher than the netlist node count, and the two are different quantities.
    pad_list = [(f.GetReference(), p.GetNumber(), p.GetNetname())
                for f in fps for p in f.Pads() if p.GetNumber()]
    ends = {(ref, num): net for ref, num, net in pad_list}
    require(len(pad_list) > 0, 'no numbered pads on the board')
    board_names = {net for _r, _n, net in pad_list}
    require(board_names == set(xml_nets.values()),
            'board pad-netname set != XML net set: missing %s extra %s'
            % (sorted(set(xml_nets.values()) - board_names),
               sorted(board_names - set(xml_nets.values()))))
    real_nets = {n for n in board_names
                 if n and not n.startswith('unconnected-') and n != ''}
    placeholders = {n for n in board_names if n.startswith('unconnected-')}

    # --- footprints unchanged (pad geometry / layers / nets)
    src = pcb.LoadBoard(str(SOURCE))
    src_sig = {f.GetReference(): pad_signature(f) for f in src.GetFootprints()}
    for f in fps:
        ref = f.GetReference()
        require(f.GetFPID().GetUniStringLibId() ==
                [x for x in src.GetFootprints() if x.GetReference() == ref][0]
                .GetFPID().GetUniStringLibId(), 'footprint id parity ' + ref)
        if sides[ref] == 'top':
            require(pad_signature(f) == src_sig[ref],
                    'footprint geometry/pad signature changed: ' + ref)
        else:
            probe = pcb.FOOTPRINT(f)
            probe.Flip(probe.GetPosition(), False)
            require(pad_signature(probe) == src_sig[ref],
                    'flipped footprint signature changed: ' + ref)
            del probe
    baseline_loops = loop_metrics(list(src.GetFootprints()))
    del src, src_sig

    # --- SAME-SIDE courtyard + pad collisions
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

    # --- (c) THT land clearance: no part may occupy another part's PTH pad field, on EITHER
    # face, because a plated through-hole is drilled through and plated on both sides.
    pth = pth_fields(fps)
    for ref, poly in polys.items():
        for other, pfield in pth.items():
            if other == ref:
                continue
            require(poly.intersection(pfield).area < 1e-8,
                    'part %s sits in the through-hole pad field of %s (THT occupies both faces)'
                    % (ref, other))

    # --- (a) MODULE KEEPOUT: nothing but U1 may put copper in the module body / antenna
    # region, on EITHER face. This is the rule the probe's cross-side skip could not see.
    keepout = box(*MODULE_KEEPOUT)
    band = box(MODULE_BODY[0], MODULE_BODY[1], MODULE_BODY[2], 6.0)   # 6 mm behind the antenna
    intrusions = {}
    band_intrusions = {}
    for ref, poly in polys.items():
        if ref == 'U1':
            continue
        ov = poly.intersection(keepout).area
        if ov > 1e-8:
            intrusions[ref] = round(ov, 3)
        ov2 = poly.intersection(band).area
        if ov2 > 1e-8:
            band_intrusions[ref] = round(ov2, 3)
    require(not intrusions,
            'module keepout occupied (courtyard): %s' % intrusions)
    require(not band_intrusions,
            'antenna-adjacent 6 mm band occupied: %s' % band_intrusions)
    # The rule area must exist and actually cover that region on B.Cu.
    module_zones = [z for z in b.Zones() if z.GetIsRuleArea()
                    and abs(z.GetBoundingBox().GetLeft() / 1e6 - MODULE_KEEPOUT[0]) < 1e-3
                    and abs(z.GetBoundingBox().GetTop() / 1e6 - MODULE_KEEPOUT[1]) < 1e-3]
    require(len(module_zones) == 1, 'module keepout rule area missing')
    require(pcb.B_Cu in set(module_zones[0].GetLayerSet().Seq()),
            'module keepout rule area is not on B.Cu')

    # --- motor reservation empty on BOTH faces
    for ref, poly in polys.items():
        require(poly.intersection(box(*MOTOR)).area < 1e-8,
                'motor reservation occupied ' + ref)

    # --- board containment (the two intentional overhangs excepted)
    for ref, poly in polys.items():
        x0, y0, x1, y1 = poly.bounds
        require(x1 <= W + 1e-4 and y1 <= H + 1e-4, 'part outside board ' + ref)
        require(x0 >= -1e-6 or ref == 'J1', 'unexpected west overhang ' + ref)
        require(y0 >= -1e-6 or ref == 'U1', 'unexpected north overhang ' + ref)

    # --- U1 antenna datum, J1 USB edge access
    require(comps['U1'].GetPosition() == pcb.VECTOR2I(pcb.FromMM(28), pcb.FromMM(6.75))
            and comps['U1'].GetOrientationDegrees() == 0, 'antenna edge datum')
    require(polys['J1'].bounds[0] < -0.5 and polys['J1'].bounds[2] < 8
            and round(comps['J1'].GetOrientationDegrees()) % 360 == 270, 'USB edge access')

    # --- sensor port access: port box and the north tube corridor must be clear on TOP
    port_box = {}
    for ref in ('U3', 'U4'):
        require(round(comps[ref].GetOrientationDegrees()) % 360 == 0,
                'sensor port orientation ' + ref)
        require(sides[ref] == 'top', 'sensor must be top-side for port access ' + ref)
        zones = list(comps[ref].Zones())
        require(len(zones) == 1, 'sensor port keepout missing ' + ref)
        zbb = zones[0].GetBoundingBox()
        port = box(zbb.GetLeft() / 1e6, zbb.GetTop() / 1e6,
                   zbb.GetRight() / 1e6, zbb.GetBottom() / 1e6)
        corridor = box(port.bounds[0], 0.0, port.bounds[2], port.bounds[1])
        for other, poly in polys.items():
            if other == ref or sides[other] != 'top':
                continue
            require(poly.intersection(port).area < 1e-8,
                    'sensor port access blocked by ' + other + ' on ' + ref)
            require(poly.intersection(corridor).area < 1e-8,
                    'sensor tube corridor blocked by %s on %s' % (other, ref))
        require(port.intersection(box(*MODULE_KEEPOUT)).area < 1e-8,
                'sensor port under the module keepout ' + ref)
        port_box[ref] = [round(v, 2) for v in port.bounds]

    require(not list(b.GetTracks()), 'candidate must be unrouted')
    require(all(z.GetIsRuleArea() for z in b.Zones()), 'unexpected copper zone')
    require(b.GetAreaCount() == 2, 'expected exactly two rule areas (motor + module)')

    # --- (b) buck cell rigid-body proof against the master baseline.
    # ONLY the six metrics INTERNAL to the cell are rigid-motion invariants. The two
    # cross-block separations (sensor_to_inductor, sensor_to_S3shield) legitimately change
    # when the cell moves to another region of the board, so they are reported, not asserted.
    BUCK_INTERNAL = ['CIN_to_VIN_mm', 'CIN_to_PGND_mm', 'SW_to_L_mm', 'L_to_COUT_mm',
                     'COUT_to_VOS_mm', 'FB_divider_to_FB_mm']
    cand_loops = loop_metrics(fps)
    deltas = {k: round(cand_loops[k] - baseline_loops[k], 4) for k in cand_loops}
    internal_deltas = {k: deltas[k] for k in BUCK_INTERNAL}
    require(all(abs(v) < 1e-9 for v in internal_deltas.values()),
            'buck cell is not a rigid body move: %s' % internal_deltas)

    outline = box(0, 0, W, H)
    def clipped(side):
        return sum(polys[r].intersection(outline).area for r in polys if sides[r] == side)
    clipped_top, clipped_bot = clipped('top'), clipped('bottom')

    return {
        'board_mm': [W, H], 'board_area_mm2': W * H,
        'references': 26, 'exported_endpoints': xml_nodes, 'nets': len(xml_nets),
        'board_numbered_pads': len(pad_list),
        'board_unique_pad_keys': len(ends),
        'board_real_nets': len(real_nets),
        'board_unconnected_placeholders': len(placeholders),
        'endpoint_denominator_note': 'nets/endpoints are the XML netlist (51 nets / 125 nodes / '
                                     '26 components). The board carries %d NUMBERED PADS but '
                                     'only %d distinct (ref,pad-number) keys, because U1 has 13 '
                                     'pads sharing number 41; 36 unused GPIOs also carry '
                                     'per-pin "unconnected-(...)" placeholder nets. Board pads '
                                     'and netlist nodes are different quantities and are '
                                     'reported separately rather than equated.'
                                     % (len(pad_list), len(ends)),
        'side_counts': dict(Counter(sides.values())),
        'top_refs': sorted(r for r in sides if sides[r] == 'top'),
        'bottom_refs': sorted(r for r in sides if sides[r] == 'bottom'),
        'courtyard_area_total_mm2': round(sum(p.area for p in polys.values()), 3),
        'courtyard_area_top_mm2': round(sum(polys[r].area for r in polys if sides[r] == 'top'), 3),
        'courtyard_area_bottom_mm2': round(sum(polys[r].area for r in polys if sides[r] == 'bottom'), 3),
        'courtyard_area_top_clipped_mm2': round(clipped_top, 3),
        'courtyard_area_bottom_clipped_mm2': round(clipped_bot, 3),
        'occupancy_top_percent': round(clipped_top / (W * H) * 100, 2),
        'occupancy_bottom_percent': round(clipped_bot / (W * H) * 100, 2),
        'occupancy_denominator': 'each side uses its own %g x %g = %g mm2 outline; '
                                 'courtyards clipped to the outline' % (W, H, W * H),
        'motor_reservation_mm': list(MOTOR), 'motor_area_mm2': 720,
        'module_keepout_mm': list(MODULE_KEEPOUT),
        'module_keepout_area_on_board_mm2': round(
            box(*MODULE_KEEPOUT).intersection(outline).area, 3),
        'antenna_bar_mm': list(ANTENNA_BAR),
        'module_keepout_intrusions': intrusions,
        'antenna_band_6mm_intrusions': band_intrusions,
        'pth_land_field_clear': True,
        'pth_parts': sorted(pth),
        'sensor_port_keepout_boxes_mm': port_box,
        'buck_rigid_transform': {'mirror_x_mm': MIRROR_X,
                                 'translate_mm': [BUCK_DX, BUCK_DY],
                                 'note': 'global reflection then translation preserves every '
                                         'internal pad-centre metric exactly'},
        'power_loop_mm': cand_loops,
        'power_loop_mm_baseline': baseline_loops,
        'power_loop_internal_deltas_mm': internal_deltas,
        'power_loop_cross_block_deltas_mm': {k: deltas[k] for k in deltas
                                            if k not in BUCK_INTERNAL},
        'power_loop_scoping': 'the six INTERNAL cell metrics are rigid-motion invariants and '
                              'are asserted at 0.0; the two cross-block separations move by '
                              'design when the cell relocates and are reported only',
        'tracks': 0, 'vias': 0, 'courtyard_overlaps': 0, 'pad_bbox_overlaps': 0,
        'collision_scope': 'per face (top vs top, bottom vs bottom) PLUS the module keepout and '
                           'PTH land fields, which bind BOTH faces',
    }


def stage_audit():
    print(json.dumps(audit(), indent=2), flush=True)


def stage_verify():
    subprocess.run(['kicad-cli', 'sch', 'erc', '--format', 'json', '--exit-code-violations',
                    '-o', str(HERE / 'erc.json'), str(ROOT / 'core.kicad_sch')], check=False)
    proof = audit()
    proof['board_sha256'] = sha(BOARD)
    proof['source_board'] = 'placement/core-placement.kicad_pcb (master 04219c23)'
    proof['source_board_sha256'] = sha(SOURCE)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json',
                    '-o', str(HERE / 'drc.json'), str(BOARD)], check=False)
    d = json.loads((HERE / 'drc.json').read_text())
    proof['native_violations'] = dict(
        Counter('%s/%s' % (v['type'], v.get('severity')) for v in d['violations']))
    proof['native_unconnected_records'] = len(d['unconnected_items'])
    proof['native_shorts'] = sum(1 for v in d['violations'] if v['type'] == 'shorting_items')
    proof['native_clearance'] = sum(1 for v in d['violations']
                                    if v['type'] in ('clearance', 'copper_edge_clearance'))
    per_net = {}
    for rec in d['unconnected_items']:
        found = {m.group(1) for item in rec['items']
                 for m in [re.search(r'\[(.*?)\]', item['description'])] if m}
        require(len(found) <= 1, 'unconnected record spans different nets: %s' % found)
        net = next(iter(found)) if found else '<unparsed>'
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


STAGES = {'copy': stage_copy, 'strip': stage_strip, 'strip_zones': stage_strip_zones,
          'strip_tracks': stage_strip_tracks, 'place': stage_place,
          'annotate': stage_annotate, 'stabilise': stage_stabilise,
          'audit': stage_audit, 'verify': stage_verify}

if __name__ == '__main__':
    if len(sys.argv) > 1:
        STAGES[sys.argv[1]]()
    else:
        for name in ['copy', 'strip', 'place', 'annotate', 'stabilise', 'verify']:
            r = subprocess.run([sys.executable, __file__, name])
            if r.returncode:
                raise SystemExit('stage %s failed rc=%d' % (name, r.returncode))
