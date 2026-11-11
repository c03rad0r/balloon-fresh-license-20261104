#!/usr/bin/env python3
"""Deterministic hole-clearance gate (ADR-125).

Checks every H*/HW* footprint (NPTH tether/string holes) on a KiCad board against:

    hole <-> every pad        (both sides)   gap >= 1.0 mm  edge-to-edge
    hole <-> every track seg  ("lanes")      gap >= 0.5 mm  centre-dist minus half-widths
    hole <-> every via                       gap >= 0.5 mm
    hole <-> zone fill        (per layer)    gap >= 0.25 mm hole-edge to DIFFERENT-NET fill
    hole <-> board edge                      >= 2.0 mm
    hole <-> other hole                      >= 4.0 mm centre-to-centre

Exit 0 = clean. Exit 1 = every violation printed. No LLM, no eyeballs: this is the
gate that catches what a courtyard-bbox check cannot (containment), born from the
2026-10-21 U3 incident (holes 0.41 mm from pads passed bbox-overlap).

The zone check measures the ACTUAL filled copper polygon per layer, not the zone's
bounding box. It used to test the bbox, which on a board whose pours cover the whole
outline meant every hole "intersected" every pour by construction: 8 holes x 5 zones =
40 permanent violations that no one could act on. See the ZONE CHECK notes below.

Run:
    ~/venvs/kicad/bin/python tracker/hardware/check_hole_clearance.py \
        --board tracker/hardware/hub_board_v10.kicad_pcb

    # reproduce the historical false positive (bounding-box zone test):
    ... --board ... --zone-check bbox
"""
import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0     # internal units (nm) per mm
PAD_GAP = 1.0        # mm, hole-edge to pad-edge
LANE_GAP = 0.5       # mm, hole-edge to track-edge
EDGE_GAP = 2.0       # mm, hole-edge to board edge
HOLE2HOLE = 4.0      # mm, centre-to-centre

# hole-edge -> pour-fill edge, in mm. This is the board's own design floor: hub_board_v10.kicad_pro
# sets min_hole_clearance = 0.25. JLCPCB's NPTH-to-copper fabrication floor is 0.20 mm, so this is
# deliberately stricter than the fab needs -- it enforces what the design declares, not what the
# house can barely make.
ZONE_GAP = 0.25
# Quantisation slop only, in mm. The fill boundary lands on the nm grid (v10 measures 0.250499 mm
# against a 0.250 floor -- 499 nm of margin), so an exact float compare would turn grid rounding
# into a red light. 1 um absorbs grid effects; it cannot hide a defect, because the smallest
# regression anyone cares about here is 10+ um and the fab floor is 200 um away.
ZONE_TOL = 0.001

ZONE_GAP_IU = int(round(ZONE_GAP * UM))
ZONE_TOL_IU = int(round(ZONE_TOL * UM))


def seg_point_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def hole_net(fp):
    """Net name the hole belongs to, or '' for an unconnected (NPTH) hole."""
    for pd in fp.Pads():
        n = pd.GetNetname()
        if n:
            return n
    return ""


def zone_fill(z, layer):
    """SHAPE_POLY_SET of the actual filled copper for `layer`, or None if there is none.

    GetFilledPolysList() throws (std::out_of_range) for a layer the zone is not on, so it may only
    be called after IsOnLayer().
    """
    if not z.IsOnLayer(layer):
        return None
    poly = z.GetFilledPolysList(layer)
    if poly is None or poly.IsEmpty() or poly.OutlineCount() == 0:
        return None
    return poly


def zone_check_fill(poly, cx_iu, cy_iu, hr_iu):
    """Gap in IU from the hole EDGE to the nearest filled copper on `layer`.

    SHAPE_POLY_SET.Distance(point) is 0 for a point inside the polygon and otherwise the distance
    to the nearest polygon edge -- so this returns a negative gap for a hole that overlaps or is
    swallowed by copper, and needs no rim sampling: the hole is a circle of known radius, so
    (distance from centre) - radius is exact.
    """
    return poly.Distance(pcbnew.VECTOR2I(cx_iu, cy_iu)) - hr_iu


def zone_check_bbox(z, cx_iu, cy_iu, hr_iu):
    """Legacy conservative test: does the hole's bounding circle overlap the zone's bounding box?

    Kept for two reasons, both load-bearing:
      1. fallback when a zone has no fill data for a layer (never silently pass a zone we cannot
         measure -- assume its outline is copper and stay conservative);
      2. `--zone-check bbox` reproduces the historical false positive exactly, which is how the
         test suite proves the new check is strictly more precise rather than merely looser.
    """
    zb = z.GetBoundingBox()
    zx0, zy0 = zb.GetX(), zb.GetY()
    zx1, zy1 = zx0 + zb.GetWidth(), zy0 + zb.GetHeight()
    return (zx0 - hr_iu < cx_iu + hr_iu and zx1 + hr_iu > cx_iu - hr_iu
            and zy0 - hr_iu < cy_iu + hr_iu and zy1 + hr_iu > cy_iu - hr_iu)


def copper_layers_of(z):
    """Copper layers this zone is drawn on. Rule areas lay down no copper and are skipped."""
    if getattr(z, "GetIsRuleArea", lambda: False)():
        return []
    out = []
    for layer in z.GetLayerSet().Seq():
        if pcbnew.IsCopperLayer(layer):
            out.append(layer)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--zone-check", choices=("fill", "bbox"), default="fill",
                    help="'fill' (default) measures the real filled copper polygon per layer; "
                         "'bbox' is the legacy bounding-box test, kept to reproduce the false "
                         "positive this gate used to report on a clean board.")
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)
    if not b:
        print("REFUSED: board did not load")
        return 3

    holes = [fp for fp in b.GetFootprints()
             if fp.GetReference().startswith(("H", "HW"))
             and ("TETHER" in (fp.GetValue() or "").upper() or "STRING" in (fp.GetValue() or "").upper())]
    if not holes:
        print("no holes found (refs H*/HW* with TETHER/STRING values)")
        return 0

    bad = []
    bb = b.GetBoardEdgesBoundingBox()
    W, H = bb.GetWidth() / UM, bb.GetHeight() / UM
    x0, y0 = bb.GetX() / UM, bb.GetY() / UM

    # (ref, x_mm, y_mm, r_mm, x_iu, y_iu, r_iu, net)
    centers = []
    for h in holes:
        p = h.GetPosition()
        hr_iu = 1_250_000                     # 1.25 mm = D2.5/2, overridden from the pad drill below
        for pd in h.Pads():
            d = pd.GetDrillSize()
            if d.x:
                hr_iu = d.x // 2
        centers.append((h.GetReference(), p.x / UM, p.y / UM, hr_iu / UM,
                        p.x, p.y, hr_iu, hole_net(h)))

    # hole <-> pad
    others = [fp for fp in b.GetFootprints() if not fp.GetReference().startswith(("H", "HW"))]
    for ref, cx, cy, hr, cx_iu, cy_iu, hr_iu, _net in centers:
        for fp in others:
            for pd in fp.Pads():
                q = pd.GetPosition()
                pr = math.hypot(pd.GetSizeX() / UM, pd.GetSizeY() / UM) / 2
                gap = math.hypot(q.x / UM - cx, q.y / UM - cy) - hr - pr
                if gap < PAD_GAP:
                    bad.append(f"{ref} <-> PAD {fp.GetReference()}.{pd.GetNumber()}: gap {gap:.2f} < {PAD_GAP}")
    # hole <-> lanes (tracks)
    for ref, cx, cy, hr, cx_iu, cy_iu, hr_iu, _net in centers:
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                q = t.GetPosition()
                gap = math.hypot(q.x / UM - cx, q.y / UM - cy) - hr - t.GetWidth() / 2 / UM
                if gap < LANE_GAP:
                    bad.append(f"{ref} <-> VIA: gap {gap:.2f} < {LANE_GAP}")
            else:
                s, e = t.GetStart(), t.GetEnd()
                d = seg_point_dist(cx, cy, s.x / UM, s.y / UM, e.x / UM, e.y / UM)
                gap = d - hr - t.GetWidth() / 2 / UM
                if gap < LANE_GAP:
                    bad.append(f"{ref} <-> LANE {t.GetNetname() or '(no net)'}: gap {gap:.2f} < {LANE_GAP}")

    # ---- ZONE CHECK -------------------------------------------------------------------------
    # Test the copper the pour actually lays down, not the box that contains the pour.
    #
    # The bbox test could never pass on a board whose pours cover the outline: v10's five zones
    # all have bounding boxes spanning the full 71.1 x 79.1 mm board, so every one of the 8
    # mounting holes "intersected" every one of them by construction -- 40 violations, each
    # annotated "verify keep-out", on a board whose real minimum hole-to-foreign-copper gap is
    # 0.250 mm against a 0.250 mm design floor. A gate that cannot pass is not a gate: it trains
    # people to ignore it, which also hides genuine pour violations of the same shape.
    #
    # SAME-NET ZONES ARE SKIPPED on purpose: a plated hole sitting inside its own net's pour is
    # intended electrical contact, not a clearance defect. On v10 this skip is currently inert --
    # all 8 tether/string holes are NPTH with no net, so no zone can match them; the cost of
    # keeping same-net strict was measured at zero violations. It matters for future boards with
    # plated, net-tied mounting holes, where a strict check would flag every one of them.
    zone_fallback = 0
    tightest_iu = None
    tightest_where = ""
    same_net_skipped = 0
    for ref, cx, cy, hr, cx_iu, cy_iu, hr_iu, hnet in centers:
        for z in b.Zones():
            zn = z.GetNetname() or ""
            if hnet and zn == hnet:
                same_net_skipped += 1
                continue
            if a.zone_check == "bbox":
                # Legacy path: one report per ZONE (not per layer), exactly as it used to emit.
                if zone_check_bbox(z, cx_iu, cy_iu, hr_iu):
                    bad.append(f"{ref} <-> ZONE {z.GetNetname()} bbox intersects (verify keep-out)")
                continue
            for layer in copper_layers_of(z):
                lname = b.GetLayerName(layer)
                poly = zone_fill(z, layer)
                if poly is None:
                    # No fill data for this layer: we cannot measure, so do NOT pass silently.
                    zone_fallback += 1
                    if zone_check_bbox(z, cx_iu, cy_iu, hr_iu):
                        bad.append(f"{ref} <-> ZONE {z.GetNetname()} ({lname}) no fill data; "
                                   f"bbox intersects (verify keep-out)")
                    continue
                gap_iu = zone_check_fill(poly, cx_iu, cy_iu, hr_iu)
                if tightest_iu is None or gap_iu < tightest_iu:
                    tightest_iu, tightest_where = gap_iu, f"{ref}/{lname}/{z.GetNetname()}"
                if gap_iu < ZONE_GAP_IU - ZONE_TOL_IU:
                    bad.append(f"{ref} <-> ZONE {z.GetNetname()} ({lname}): "
                               f"hole edge to fill {gap_iu / UM:.3f} < {ZONE_GAP} mm")

    # hole <-> edge
    for ref, cx, cy, hr, cx_iu, cy_iu, hr_iu, _net in centers:
        d = min(cx - x0, (x0 + W) - cx, cy - y0, (y0 + H) - cy) - hr
        if d < EDGE_GAP:
            bad.append(f"{ref} <-> EDGE: {d:.2f} < {EDGE_GAP}")
    # hole <-> hole
    for i, (r1, x1, y1, h1, *_rest) in enumerate(centers):
        for r2, x2, y2, h2, *_r2 in centers[i + 1:]:
            d = math.hypot(x2 - x1, y2 - y1)
            if d < HOLE2HOLE:
                bad.append(f"{r1} <-> {r2}: {d:.2f} < {HOLE2HOLE} centre-to-centre")

    print(f"holes checked: {len(centers)}  ({', '.join(r for r, *_ in centers)})")
    if a.zone_check == "fill":
        if tightest_iu is not None:
            print(f"zones: tightest hole-edge to different-net fill {tightest_iu / UM:.3f} mm "
                  f"at {tightest_where} (floor {ZONE_GAP} mm)")
        if same_net_skipped:
            print(f"zones: same-net zone/layer pairs skipped: {same_net_skipped} "
                  f"(intended contact, not a clearance defect)")
        if zone_fallback:
            print(f"zones: {zone_fallback} zone/layer pairs had no fill data -> bbox fallback")
    if bad:
        print(f"VIOLATIONS: {len(bad)}")
        for v in bad:
            print("  ", v)
        return 1
    print(f"clear: 0 violations (pads, lanes, vias, zones, edge, hole-to-hole)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
