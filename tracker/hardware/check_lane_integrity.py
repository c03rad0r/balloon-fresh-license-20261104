#!/usr/bin/env python3
"""Deterministic lane audit (ADR-126 precursor): catch the two defects the operator SAW.

1. ILLEGAL CONTACT -- a track whose copper touches a pad belonging to a DIFFERENT net
   (an accidental short; includes "two pins of the same chip" if those pins are not the
   track's own net).
2. DEAD END -- a track endpoint that touches neither a pad nor another track of its net
   (a dangling stub).

Geometry is computed from the loaded board: point-to-segment distance for endpoints,
segment-to-pad-edge distance for contact, using the pad's real shape bbox (conservative).

Exit 1 on any violation.
"""
import math
import sys

import pcbnew

import argparse, os
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
CONTACT_TOL = 0.02   # mm -- copper considered touching at this gap
ENDPOINT_TOL = 0.05  # mm -- endpoint considered connected to another track's endpoint


def seg_point_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def pad_bbox_mm(pad):
    bb = pad.GetBoundingBox()   # B10: rotation-aware
    return (bb.GetX() / UM, bb.GetY() / UM,
            (bb.GetX() + bb.GetWidth()) / UM, (bb.GetY() + bb.GetHeight()) / UM)


def point_in_bbox(px, py, bb, grow=0.0):
    return bb[0] - grow <= px <= bb[2] + grow and bb[1] - grow <= py <= bb[3] + grow


def seg_touches_bbox(x0, y0, x1, y1, bb):
    """True if the segment passes through the (grown) pad rectangle."""
    # sample-based is exact enough at 25um steps for a 0.2mm track audit
    L = math.hypot(x1 - x0, y1 - y0)
    steps = max(2, int(L / 0.025) + 2)
    for i in range(steps + 1):
        t = i / steps
        if point_in_bbox(x0 + t * (x1 - x0), y0 + t * (y1 - y0), bb):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.board)
    if not b:
        print("REFUSED: board load failed")
        return 3
    tracks = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and not "VIA" in str(type(t))]

    # FILLED ZONES, per net. CORRECTED 2026-11-11.
    #
    # The dead-end test below used to consider only pads and other track endpoints, so a track
    # that ends in a POURED ZONE of its own net was called a dead end. On the board of record
    # that produced 61 reported violations of which 58 are electrically connected -- 43 GND,
    # 11 +3V3, 4 /VSCAP all terminate in their own fill. A checker that ignores pour fill is not
    # conservative: it buries the real defects in noise. This project has already been bitten by
    # the same class twice (base-station "143 violations" = 74 stale-zone false positives).
    zones_by_net = {}
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsFilled():
            continue
        zones_by_net.setdefault(str(z.GetNetname()), []).append(z)
    COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)

    def in_own_zone(netname, x, y):
        """Is this point on filled copper of the same net? Uses KiCad's own hit-test."""
        pt = pcbnew.VECTOR2I(int(round(x * UM)), int(round(y * UM)))
        for z in zones_by_net.get(netname, ()):
            for layer in COPPER:
                if z.IsOnLayer(layer) and z.HitTestFilledArea(layer, pt):
                    return True
        return False

    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNet()
            pads.append((fp.GetReference(), p.GetNumber(), n.GetNetname() if n else "",
                         n.GetNetCode() if n else 0, p.GetLayerSet(), pad_bbox_mm(p)))

    illegal, dangling = [], []
    for t in tracks:
        n = t.GetNet()
        code = n.GetNetCode() if n else 0
        name = n.GetNetname() if n else "?"
        x0, y0 = t.GetStart().x / UM, t.GetStart().y / UM
        x1, y1 = t.GetEnd().x / UM, t.GetEnd().y / UM
        half = t.GetWidth() / UM / 2

        # 1. illegal contact: any pad of a DIFFERENT net inside the track's swept box
        for ref, num, pname, pcode, player, bb in pads:
            if pcode == code:
                continue
            if not player.Contains(t.GetLayer()):
                continue
            grown = (bb[0] - half - CONTACT_TOL, bb[1] - half - CONTACT_TOL,
                     bb[2] + half + CONTACT_TOL, bb[3] + half + CONTACT_TOL)
            if seg_touches_bbox(x0, y0, x1, y1, grown):
                illegal.append(f"SHORT: track on {name} passes through pad {ref}.{num} "
                               f"(net {pname})")

        # 2. dead ends: each endpoint must touch a pad of its own net, or another track's end
        for (ex, ey) in ((x0, y0), (x1, y1)):
            touches_pad = any(pcode == code and player.Contains(t.GetLayer())
                              and point_in_bbox(ex, ey, bb, half + 0.05)
                              for _r, _n, _pn, pcode, player, bb in pads)
            # A T-junction counts: the test used to accept only another track's ENDPOINT, so a
            # track joining the middle of another was also called a dead end. A passing track is
            # a real connection, so it is tested explicitly.
            touches_track = t_in_own_zone = in_own_zone(name, ex, ey)
            for o in tracks:
                if o is t:
                    continue
                ox0, oy0 = o.GetStart().x / UM, o.GetStart().y / UM
                ox1, oy1 = o.GetEnd().x / UM, o.GetEnd().y / UM
                if seg_point_dist(ex, ey, ox0, oy0, ox1, oy1) <= ENDPOINT_TOL + half:
                    touches_track = True
                    break
            if not (touches_pad or touches_track):
                dangling.append(f"DEAD END: track on {name} ends at ({ex:.2f},{ey:.2f}) "
                                f"with nothing under it")

    print(f"tracks audited: {len(tracks)}")
    for v in illegal:
        print("  ", v)
    for v in dangling:
        print("  ", v)
    total = len(illegal) + len(dangling)
    print(f"VIOLATIONS: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())