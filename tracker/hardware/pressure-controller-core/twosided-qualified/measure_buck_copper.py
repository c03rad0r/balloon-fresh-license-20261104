#!/usr/bin/env python3
"""Measured copper-width requirement for the buck nets on the BOTTOM side.

TI SLVSAM2E section 11.1 gives no numbers ("as close as possible", "wide and short"), so the
width cannot be quoted from the datasheet. It is COMPUTED here from the current and the
copper thickness actually on order, and the result is reported as a requirement for ROUTING,
which has not been done.

Physics used (IPC-2221 external-layer chart, the standard prototype approximation):
    I = k * dT^0.44 * A^0.725          A in mil^2, k = 0.048 for external layers
    A = W_mil * t_mil
This is an ADVISORY sizing figure for an unrouted candidate. It is NOT a thermal simulation
and makes no claim about validated performance.

Also reports the physical clearance actually available for those traces, so the width is
checked against the geometry rather than assumed feasible.
"""
import json
import math
import sys
from pathlib import Path

import pcbnew as pcb
from shapely.geometry import LineString, box
from shapely.ops import polygonize, unary_union

HERE = Path(__file__).resolve().parent
BOARD = HERE / 'twosided-qualified.kicad_pcb'

# Design inputs, all measured on this board or taken from the committed BOM/schematic.
VIN_NOM = 5.0          # /USB5V from the USB-C connector
VOUT = 3.3             # /+3V3
I_LOAD = 1.0           # TPS62160DSGR rated 1 A; the datasheet's headline current
F_SW = 2.25e6          # TPS6216x nominal switching frequency (2.25 MHz)
CU_THICK_OZ = 1.0      # JLCPCB 2-layer 1.6 mm prototype default: 1 oz (35 um) outer copper
CU_UM = CU_THICK_OZ * 35.0
DT_C = 10.0            # allowed temperature rise


def ipc2221_width_mm(current_a, dt_c, cu_um, external=True):
    """Minimum trace width in mm for `current_a` at `dt_c` rise (IPC-2221 chart)."""
    k = 0.048 if external else 0.024
    t_mil = cu_um / 25.4
    # solve A = (I / (k * dT^0.44))^(1/0.725)
    a_mil2 = (current_a / (k * dt_c ** 0.44)) ** (1.0 / 0.725)
    w_mil = a_mil2 / t_mil
    return w_mil * 0.0254


def crt(f):
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
    return unary_union(rects + list(polygonize(lines)))


def main():
    b = pcb.LoadBoard(str(BOARD))
    ds = b.GetDesignSettings()
    fps = {f.GetReference(): f for f in b.GetFootprints()}

    # currents per buck net
    i_vin = I_LOAD * VOUT / VIN_NOM / 0.90        # assume 90 % efficiency for input current
    i_sw = I_LOAD
    i_out = I_LOAD
    i_gnd = i_vin                                 # input return dominates the loop
    nets = {
        '/USB5V': (i_vin, 'VIN input, %.2f A (1 A out at 3.3/5.0 V, 90%% eff)' % i_vin),
        '/BUCK_SW': (i_sw, 'switch node, %.2f A' % i_sw),
        '/+3V3': (i_out, 'VOUT, %.2f A' % i_out),
        '/GND': (i_gnd, 'input/PGND return, %.2f A' % i_gnd),
        '/BUCK_FB': (0.0, 'sense only, ~uA - size for noise, not current'),
    }
    widths = {}
    for n, (i, why) in nets.items():
        widths[n] = {
            'current_a': round(i, 3),
            'basis': why,
            'width_1oz_10C_mm': round(ipc2221_width_mm(i, DT_C, CU_UM), 3) if i else None,
            'width_2oz_10C_mm': round(ipc2221_width_mm(i, DT_C, 2 * CU_UM), 3) if i else None,
        }

    # Available clearance on the bottom: minimum centre-to-centre gap between pads of
    # DIFFERENT buck nets, minus the two pad half-extents.
    import itertools
    pads = []
    for ref in ('U2', 'L1', 'C4', 'C5', 'C6', 'R7', 'R8'):
        for p in fps[ref].Pads():
            if p.GetNumber():
                pads.append((ref, p.GetNumber(), p.GetPosition().x / 1e6,
                             p.GetPosition().y / 1e6, p.GetNetname(),
                             p.GetSize().x / 1e6, p.GetSize().y / 1e6))
    # EXACT edge-to-edge distance between pad POLYGONS.
    # Do NOT subtract bounding-circle radii: an earlier version used max(size.x, size.y)/2 as a
    # radius, which reports a NEGATIVE gap (-0.666 mm) for rectangular pads that DRC proves do
    # not overlap (0 shorts, 0 clearance violations on this board). A circle model of a
    # rectangle over-reports proximity by up to the half-diagonal, which is exactly the
    # "centre-to-obstacle test under-reports / over-reports by the pad's own half-dimension"
    # trap. Use each pad's own composed shape.
    def pad_poly(p):
        # GetEffectivePolygon(layer) returns the exact pad outline for that layer. Querying
        # GetEffectiveShape(B_Cu).Distance() on an SMD pad that exists only on B.Cu through a
        # flipped footprint returned None for every pair (empty result list, verdict None).
        # The polygon is unambiguous and is compared with exact shapely distance.
        from shapely.geometry import Polygon
        for layer in (pcb.B_Cu, pcb.F_Cu):
            try:
                sps = p.GetEffectivePolygon(layer)
            except Exception:
                continue
            if sps is None or sps.OutlineCount() == 0:
                continue
            pts = [(pt.x / 1e6, pt.y / 1e6) for pt in sps.Outline(0).CPoints()]
            if len(pts) >= 3:
                return Polygon(pts)
        return None

    pad_objs = []
    for ref in ('U2', 'L1', 'C4', 'C5', 'C6', 'R7', 'R8'):
        for p in fps[ref].Pads():
            if p.GetNumber():
                poly = pad_poly(p)
                if poly is not None and poly.is_valid:
                    pad_objs.append((ref, p.GetNumber(), p.GetNetname(), poly))
    require_pairs = len(pad_objs) > 10
    gaps = []
    for a, c in itertools.combinations(pad_objs, 2):
        if a[0] == c[0] or a[2] == c[2]:
            continue
        d = a[3].distance(c[3])               # exact, in mm
        gaps.append((round(d, 3), a[0] + '.' + a[1], a[2], c[0] + '.' + c[1], c[2]))
    gaps.sort()

    # courtyard-free run available for the widest needed trace
    widest = max(v['width_1oz_10C_mm'] or 0 for v in widths.values())
    out = {
        'board': BOARD.name,
        'stackup_assumption': {
            'copper_oz_outer': CU_THICK_OZ,
            'copper_um': CU_UM,
            'note': 'JLCPCB 2-layer 1.6 mm prototype default is 1 oz (35 um) outer copper; '
                    '2 oz and heavier are available at extra cost. The board file declares '
                    '2 copper layers; no stackup impedance claim is made because nothing here '
                    'is impedance-controlled.',
        },
        'sizing_method': 'IPC-2221 external-layer chart, k=0.048, dT=%g C. ADVISORY sizing for '
                         'an UNROUTED candidate, not a thermal simulation.' % DT_C,
        'nets': widths,
        'widest_required_trace_1oz_mm': round(widest, 3),
        'min_pad_edge_gap_between_different_buck_nets_mm': gaps[0][0] if gaps else None,
        'tightest_pairs': [{'edge_gap_mm': g[0], 'a': g[1], 'net_a': g[2],
                            'b': g[3], 'net_b': g[4]} for g in gaps[:8]],
        'design_min_clearance_mm': round(ds.m_MinClearance / 1e6, 3),
        'verdict': None,
    }
    # Can the widest required trace physically pass between the two tightest DIFFERENT-net
    # pads?  need = w/2 on each side + clearance.
    if not gaps:
        raise SystemExit('measurement failed: no pad pairs computed (a silent empty result '
                         'must never be reported as a clean verdict)')
    if gaps:
        tight = gaps[0][0]
        need = widest + 2 * (ds.m_MinClearance / 1e6 if ds.m_MinClearance else 0.15)
        out['tightest_channel_fits_widest_buck_trace'] = bool(tight >= need)
        out['tightest_channel_required_mm'] = round(need, 3)
        out['tightest_channel_available_mm'] = tight
        out['verdict'] = (
            'The tightest different-net pad gap in the buck cell (%.3f mm, %s/%s) %s the '
            '%.3f mm needed for the widest required buck trace (%.3f mm) plus clearance; '
            'the wide traces must therefore leave the tight pads immediately rather than '
            'run between them. This is a ROUTING constraint, reported for the routing pass.'
            % (tight, gaps[0][1], gaps[0][3],
               'accommodates' if tight >= need else 'does NOT accommodate', need, widest))
    (HERE / 'buck-copper.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
