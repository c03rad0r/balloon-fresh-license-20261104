#!/usr/bin/env python3
"""Stitch v3 -- OFFSET stitching vias with a stub, for pads with no room at centre.

WHY v3 EXISTS (measured 2026-10-14)
-----------------------------------
v2 asked "does a 0.60 mm via fit AT THE PAD CENTRE?" and correctly REJECTED 63 pads
where it does not. That was the right safety call, but it left 4 pads unconnected --
pads on C_MON, J_W1, J_W3 and C_HF that the router had already given a short GND
stub track, and which the v2 check would not stitch.

The correct fix is not to shrink the via (a sub-0.60 mm via would violate the frozen
rule set) and not to accept the open. It is to put the SAME 0.60 mm via SOMEWHERE
THAT FITS and join it to the pad with a short GND track. A GND stub plus an offset
via is a normal, manufacturable plane tap.

WHAT v3 DOES
  For every GND pad not already stitched:
    1. search outward on a 0.25 mm ring (r = 0.6 .. 4.0 mm) around the pad centre for
       a via position that clears every FOREIGN net by (via_d/2 + clearance)
    2. if found, drop the via there AND add a GND track from the pad to the via
    3. if no position on any ring qualifies, report the pad as UNRESOLVABLE rather
       than silently leaving it (so the remaining count is honest)

  It never moves a part, never deletes, and never shrinks the via. It is idempotent:
  a pad within 1.0 mm of an existing GND via is left alone.

Run:
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb>            # v2 behaviour
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb> --offset   # v3
"""
import math
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

VIA_D = 0.6
VIA_DRILL = 0.3
CLEARANCE = 0.2
BOARD_EDGE = 0.5      # jlcpcb-s1-frozen.kicad_dru: copper-to-edge minimum
TRACK_W = 0.2
RING_STEP = 0.25
R_MAX = 4.0


# Centre taps put a via INSIDE an SMD pad. Off by default: JLCPCB does not fill/cap vias, so an
# uncapped barrel in a pad wicks solder during reflow. Keep the flag so the old behaviour is
# reproducible for comparison, but never enable it for a flight candidate.
_CENTER_TAPS = os.environ.get("STITCH_CENTER_TAPS", "0") == "1"


def mm(v):
    return pcbnew.ToMM(v)


def bbox_of(item):
    bb = item.GetBoundingBox()
    return (mm(bb.GetX()), mm(bb.GetY()),
            mm(bb.GetX() + bb.GetWidth()), mm(bb.GetY() + bb.GetHeight()))


def main():
    argv = sys.argv[1:]
    offset_mode = "--offset" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    src, dst = args

    board = pcbnew.LoadBoard(src)
    if board is None:
        print(f"cannot load {src}")
        return 2

    gcode = None
    for code, net in board.GetNetInfo().NetsByNetcode().items():
        if net.GetNetname() == "GND":
            gcode = code
    if gcode is None:
        print("no GND net")
        return 2

    foreign = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                foreign.append(bbox_of(pad))
    for t in board.GetTracks():
        if t.GetNetCode() != gcode:
            foreign.append(bbox_of(t))

    r_test = VIA_D / 2.0 + CLEARANCE

    # ---------------------------------------------------------------------------------------------
    # WHY THIS PREDICATE WAS WRONG (measured 2026-10-15)
    # ---------------------------------------------------------------------------------------------
    # The original `free()` tested the candidate via centre against the AXIS-ALIGNED BOUNDING BOX of
    # every foreign item, with an inside-corner distance test. Two independent defects followed:
    #
    #   1. A bbox is not a shape. A diagonal track's bounding box is a large rectangle, so a point can
    #      clear the box corner and still sit ON the track; conversely a legitimately empty spot next
    #      to a diagonal can be rejected. Vias therefore ended up colliding with COPPER.
    #   2. Hole-to-hole spacing was NEVER tested. That is a DRILL rule, and this predicate only ever
    #      used the COPPER diameter, so two drills could be arbitrarily close.
    #
    # Measured consequence of enabling offset mode with the old predicate: errors 29 -> 56, including
    # `shorting_items` 5 (REAL SHORTS), `hole_to_hole` 34, `tracks_crossing` 2, `holes_co_located` 2.
    # It reduced "unresolvable pads" 55 -> 12 -- the metric it optimises -- while breaking the board.
    #
    # The fix uses KiCad's own geometry: every foreign item is turned into a real polygon (arcs
    # approximated), so the test is shape-accurate, and hole spacing is checked separately against the
    # same minimum the frozen ruleset enforces.
    HOLE_TO_HOLE = 0.25          # jlcpcb-s1-frozen.kicad_dru: hole-to-hole minimum
    ARC_ERR = 5000               # max error 0.005 mm when approximating arcs

    def _polys(item):
        """Real shape polygon(s) for a pad, track or via, as KiCad itself computes them.

        NOTE (measured 2026-10-15): `PAD::TransformShapeToPolygon` ASSERTS on UNDEFINED_LAYER in
        KiCad 9 -- "UNDEFINED_LAYER is no longer allowed". Passing it made _polys() throw for every
        pad, so pads were silently dropped from the copper test and "UNRESOLVABLE" fell to 0 while 71
        vias were placed. A predicate that silently tests NOTHING is worse than one that is too loose,
        because it reports success. Use a real layer: the pad's own first layer, F_Cu for tracks.
        """
        try:
            ps = pcbnew.SHAPE_POLY_SET()
            layer = pcbnew.F_Cu
            if hasattr(item, "GetLayerSet"):
                seq = [int(x) for x in item.GetLayerSet().Seq()]
                if seq:
                    layer = seq[0]
            item.TransformShapeToPolygon(ps, layer, 0, ARC_ERR, pcbnew.ERROR_INSIDE)
            return ps
        except Exception:
            return None

    def _polys_ok(item):
        """_polys() but LOUD: a pad/track we cannot convert is a hole in the safety test."""
        ps = _polys(item)
        if ps is None:
            raise SystemExit(
                "[FATAL] could not convert an item to a polygon, so the clearance test would "
                "silently ignore it. That is the exact defect this predicate was rewritten to fix. "
                "Refusing to place vias against an incomplete test."
            )
        return ps

    # Build once: (polygon, drill_circle) for every foreign item.
    # `foreign` already holds only NON-GND pads/tracks; add their drills for the hole test.
    foreign_polys = []
    foreign_holes = []            # (cx, cy, radius) of every drill/via hole

    # Real Edge.Cuts geometry (shapes, not a bounding box), for the board-edge keepout in free().
    edge_shapes = []
    for d_ in board.GetDrawings():
        if d_.GetLayer() == pcbnew.Edge_Cuts:
            try:
                ps = pcbnew.SHAPE_POLY_SET()
                d_.TransformShapeToPolygon(ps, pcbnew.Edge_Cuts, 0, ARC_ERR, pcbnew.ERROR_INSIDE)
                edge_shapes.append(ps)
            except Exception:
                pass
    for fp in board.GetFootprints():
        for gi in fp.GraphicalItems():
            if gi.GetLayer() != pcbnew.Edge_Cuts:
                continue
            try:
                ps = pcbnew.SHAPE_POLY_SET()
                gi.TransformShapeToPolygon(ps, pcbnew.Edge_Cuts, 0, ARC_ERR, pcbnew.ERROR_INSIDE)
                edge_shapes.append(ps)
            except Exception:
                pass
    # FOOTPRINT Edge.Cuts GRAPHICS ARE EDGE GEOMETRY TOO. Measured 2026-11-03: collecting only
    # board.GetDrawings() missed the four 6.0 x 0.5 mm cavity slots inside each J_W footprint, so
    # offset vias were placed on top of them and DRC raised 4 copper_edge_clearance. This is the
    # same blind spot as B48: the keep-out must be built from EVERY Edge.Cuts shape on the board,
    # not just the ones that happen to live at board level.
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            # ONLY foreign (non-GND) copper blocks a GND via. Adding the GND pad's OWN polygon made
            # every pad centre read as blocked, so 0 centre vias and 71 offsets were placed -- a
            # self-collision artifact, caught by comparing against the pre-fix "vias at pad centre: 15".
            if pad.GetNetCode() != gcode:
                foreign_polys.append((_polys_ok(pad), bbox_of(pad)))
                ds = pad.GetDrillSize()
                d_x, d_y = int(ds.x), int(ds.y)
                if d_x > 0 or d_y > 0:
                    p = pad.GetPosition()
                    foreign_holes.append((mm(p.x), mm(p.y), mm(max(d_x, d_y)) / 2.0))
    for t in board.GetTracks():
        if t.GetNetCode() != gcode:
            foreign_polys.append((_polys_ok(t), bbox_of(t)))
        if t.GetNetCode() != gcode and t.GetClass() == "PCB_VIA":
            dv = float(mm(int(t.GetDrillValue()))) if hasattr(t, "GetDrillValue") \
                else float(mm(int(t.GetViaDrill())))
            p = t.GetPosition()
            foreign_holes.append((mm(p.x), mm(p.y), dv / 2.0))

    def free(cx, cy):
        """True only if a via of VIA_D centred here clears all copper, and its drill clears all holes.

        Two gates, because they are two different fabricator rules:
          * COPPER: distance from the point to the real (non-bbox) polygon >= (VIA_D/2 + CLEARANCE)
          * HOLES : drill centre distance >= (OUR_DRILL/2 + HOLE_TO_HOLE + other_drill/2)
        Both are checked. The old code did neither correctly.
        """
        need = r_test
        # --- copper, against true geometry ---
        for ps, bb in foreign_polys:
            x0, y0, x1, y1 = bb
            # cheap reject: if the bbox is further than `need`, skip the exact test
            nx = min(max(cx, x0), x1)
            ny = min(max(cy, y0), y1)
            if (cx - nx) ** 2 + (cy - ny) ** 2 > (need + 1.0) ** 2:
                continue
            try:
                pt = pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6)))
                if ps.Distance(pt) < int(need * 1e6):
                    return False
            except Exception:
                # if the exact test is unavailable, fall back to the conservative bbox test
                if (cx - nx) ** 2 + (cy - ny) ** 2 < need ** 2:
                    return False
        # --- holes, drill to drill ---
        for hx, hy, hr in foreign_holes:
            if (cx - hx) ** 2 + (cy - hy) ** 2 < (VIA_DRILL / 2.0 + HOLE_TO_HOLE + hr) ** 2:
                return False
        # --- board edge ---
        # A THIRD rule the predicate never knew. Measured 2026-10-15: stitching took
        # copper_edge_clearance 27 -> 30, i.e. it placed three vias too near Edge.Cuts. The frozen
        # ruleset's board_edge minimum is BOARD_EDGE; the via's OWN radius counts toward it, so the
        # centre must sit at least (BOARD_EDGE + VIA_D/2) inside. Edge.Cuts geometry is used directly
        # rather than the board bounding box: the outline is not necessarily rectangular, and a bbox
        # would both miss corners and over-reject near them.
        for es in edge_shapes:
            try:
                pt = pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6)))
                if es.Distance(pt) < int(round((BOARD_EDGE + VIA_D / 2.0) * 1e6)):
                    return False
            except Exception:
                pass
        return True

    # ---------------------------------------------------------------------------------------------
    # THE STUB TRACK WAS NEVER CLEARANCE-CHECKED (the last offset-mode defect, measured 2026-10-15)
    # ---------------------------------------------------------------------------------------------
    # `free()` validates the VIA SITE. The stub track that joins the pad to that site is drawn AFTER
    # the site is chosen and was never tested against anything. Measured consequence of enabling
    # offset mode with the shape-accurate predicate: unconnected fell 10 -> 4 (good) but errors sat at
    # 46 vs a 29 baseline, with `clearance` 10 and `shorting_items` 2 that the via placement cannot
    # explain -- the via IS shape-tested. Those are the STUB.
    #
    # Sampled at STUB_SAMPLES+1 points rather than solved analytically: the stub may pass THROUGH a
    # forbidden region while both endpoints are legal, which an endpoint-only test would miss --
    # exactly the error the original bbox code made in the other direction.
    STUB_SAMPLES = 16

    def stub_ok(cx, cy, sx, sy):
        """The stub (pad centre -> via site), width TRACK_W, must clear foreign copper.

        A track carries no drill, so no hole-to-hole rule applies to the stub itself; the dominant
        missing rule was copper clearance. Required: distance >= TRACK_W/2 + CLEARANCE at every
        sampled point along the segment.
        """
        need = TRACK_W / 2.0 + CLEARANCE
        need_i = int(round(need * 1e6))
        for i in range(STUB_SAMPLES + 1):
            t = i / float(STUB_SAMPLES)
            px = cx + (sx - cx) * t
            py = cy + (sy - cy) * t
            for ps, bb in foreign_polys:
                x0, y0, x1, y1 = bb
                nx = min(max(px, x0), x1)
                ny = min(max(py, y0), y1)
                if (px - nx) ** 2 + (py - ny) ** 2 > (need + 1.0) ** 2:
                    continue
                try:
                    pt = pcbnew.VECTOR2I(int(round(px * 1e6)), int(round(py * 1e6)))
                    if ps.Distance(pt) < need_i:
                        return False
                except Exception:
                    if (px - nx) ** 2 + (py - ny) ** 2 < need ** 2:
                        return False
        return True

    def near_gnd_via(cx, cy):
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gcode:
                p = t.GetPosition()
                if (cx - mm(p.x)) ** 2 + (cy - mm(p.y)) ** 2 < 1.0 ** 2:
                    return True
        return False

    added_here = added_offset = already = unresolvable = pth_skipped = 0
    _placed = []
    bad = []

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                continue
            ls = pad.GetLayerSet()
            if not (ls.Contains(pcbnew.F_Cu) or ls.Contains(pcbnew.B_Cu)):
                continue
            # A PLATED THROUGH-HOLE PAD ALREADY CONNECTS EVERY COPPER LAYER. Adding a via on top of
            # one produces two drills at the same XY -- kicad-cli reports it as `holes_co_located`,
            # a fabrication error (measured 2026-11-03: 3 instances, each a via dropped on the barrel
            # of J_PROG.1, C_CAP2.2 and J_HUB_PV.5). A PTH pad is not an unstitched site; skip it.
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                pth_skipped += 1
                continue
            p = pad.GetPosition()
            cx, cy = mm(p.x), mm(p.y)
            # A via at the pad centre is only legal if its ANNULAR RING FITS INSIDE THE PAD.
            # Measured 2026-11-03: free() tested only foreign copper, so 43 GND vias landed at SMD
            # pad centres on pads as small as 0.54 x 0.64 mm -- narrower than the 0.60 mm via. The
            # ring then hangs off the pad: solder wicks down the barrel and the joint area shrinks.
            # kicad-cli DRC does not report this, so the check has to live here. Anything that does
            # not fit goes to the offset path instead, which is what v3 exists for.
            _bb = pad.GetBoundingBox()
            # Annular ring check. A 0.60 mm via needs 0.10 mm of pad beyond it on EVERY side, so the
            # pad must exceed the via by 0.20 mm on each axis. Measured 2026-11-03: a 1.32 x 0.60 mm
            # pad passes a naive ">= VIA_D" test but leaves ZERO ring on the 0.60 axis, which is
            # exactly the via-overhanging-pad defect. 8 such pads survived the first attempt.
            _fits = (_bb.GetWidth() / 1e6 >= VIA_D + 0.20
                     and _bb.GetHeight() / 1e6 >= VIA_D + 0.20)
            if near_gnd_via(cx, cy):
                already += 1
                continue

            # CENTRE VIAS ARE VIA-IN-PAD, AND JLCPCB DOES NOT FILL THEM. An uncapped via inside an
            # SMD pad wicks solder down the barrel during reflow: the joint loses paste and can go
            # open. Astra flagged this twice from the render ("several white vias sit directly on
            # gold pads") and measurement agreed -- 30 centres inside pads, 4 with rings thinner
            # than 0.10 mm/side. Placement is now offset-ONLY: every GND tap is a normal via beside
            # the pad joined by a short stub, which is a standard, manufacturable plane tap and is
            # what this tool's v3 mode was built for. Cost, measured: 43 centre taps become ~40
            # offset taps, a few pads report UNRESOLVABLE instead of being forced.
            if _CENTER_TAPS and _fits and free(cx, cy):
                site, off = (cx, cy), False
            elif offset_mode:
                site = None
                # START OUTSIDE THE PAD. A via inside an SMD pad is via-in-pad: JLCPCB does not
                # fill or cap it by default, so solder wicks down the barrel and the joint loses
                # paste. Measured 2026-11-03: starting the ring at VIA_D/2+CLEARANCE still landed
                # 45 vias inside pads (19 with under-sized rings on 0.7 mm-tall pads), because that
                # radius is smaller than half the pad. Start beyond the pad's own half-diagonal so
                # no ring position can sit within the pad body.
                _bb = pad.GetBoundingBox()
                _half_diag = 0.5 * math.hypot(_bb.GetWidth() / 1e6, _bb.GetHeight() / 1e6)
                ring = max(VIA_D / 2.0 + CLEARANCE, _half_diag + VIA_D / 2.0 + CLEARANCE)
                while ring <= R_MAX and site is None:
                    n = max(8, int(2 * math.pi * ring / 0.2))
                    for k in range(n):
                        a = 2 * math.pi * k / n
                        tx, ty = cx + ring * math.cos(a), cy + ring * math.sin(a)
                        # BOTH the via site AND the stub that reaches it must be legal
                        if free(tx, ty) and stub_ok(cx, cy, tx, ty):
                            site = (tx, ty)
                            break
                    ring += RING_STEP
                off = True if site else False
                if site is None:
                    unresolvable += 1
                    bad.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                    continue
            else:
                unresolvable += 1
                bad.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                continue

            sx, sy = site
            # TWO PAD OBJECTS CAN SHARE ONE XY. Each J_W tab carries every pad number twice — once
            # on F.Cu, once on B.Cu, same position and net, because the tab is soldered from both
            # sides. Iterating pads therefore visits the same location twice and, with offset-only
            # placement, drops TWO vias at the identical site. kicad-cli reports that as
            # holes_co_located (measured 2026-11-03: 5 of them, all GND, all at J_W/Wing_Tab).
            # Skip a site that already has one of our vias.
            if any(math.hypot(sx - vx, sy - vy) < 0.05 for (vx, vy) in _placed):
                already += 1
                continue
            _placed.append((sx, sy))
            # stub track from the pad to the via, when offset
            if off:
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6))))
                tr.SetEnd(pcbnew.VECTOR2I(int(round(sx * 1e6)), int(round(sy * 1e6))))
                tr.SetWidth(int(TRACK_W * 1e6))
                tr.SetLayer(pcbnew.F_Cu)
                tr.SetNetCode(gcode)
                board.Add(tr)

            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(round(sx * 1e6)), int(round(sy * 1e6))))
            v.SetWidth(int(VIA_D * 1e6))
            v.SetDrill(int(VIA_DRILL * 1e6))
            v.SetNetCode(gcode)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)

            if off:
                added_offset += 1
            else:
                added_here += 1

    pcbnew.SaveBoard(dst, board)
    print(f"vias at pad centre      : {added_here}")
    print(f"vias OFFSET + GND stub  : {added_offset}")
    print(f"pads already stitched   : {already}")
    print(f"PTH pads skipped (already all-layer): {pth_skipped}")
    print(f"UNRESOLVABLE            : {unresolvable}")
    if bad:
        print("  unresolved pads:", ", ".join(bad[:20]))
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
