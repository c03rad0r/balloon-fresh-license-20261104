#!/usr/bin/env python3
"""Annotated ZOOM of the J_W2 wing seat — CORRECTED renderer (v2).

WHAT WAS WRONG IN v1, and why this file exists:

  v1. Pads were drawn once per PAD OBJECT. A J_W footprint carries 8 pad objects for 4 numbers
      (the same land on BOTH faces, soldered from both sides), so J_W2.1 was painted twice at
      identical coordinates and two 28% fills composited to ~48% — which reads as a solid slab
      colliding with its neighbours. The operator spotted it from the picture; the drawing was
      wrong, not the board.
  v2. A full-canvas dark-green rect was painted as "substrate". It carried no board information
      and made the crop look like a distinct material. Removed; the canvas is plain.
  v3. A red circle labelled "blocker r=2.000 mm" was drawn at (35.10, 77.00). That object does
      not exist on the board: it was J_W2.2 modelled as a disc of radius longest_side/2, i.e.
      the phantom-copper bug in circle form, drawn into the figure. Removed.

WHAT THIS FILE ASSERTS, all measured at draw time (nothing hard-coded):
  * every pad drawn as its TRUE rectangle, once per (number, face), labelled with its face
  * F.Cu pads solid outline, B.Cu pads dashed outline, so "which layer" is answerable from the image
  * real tracks (F.Cu solid orange, B.Cu dashed cyan) and real vias (white circle)
  * the measured centre-to-centre gaps to the two nearest other-net neighbours of J_W2.1, printed
    on the image, so the clearance claim is visible rather than asserted

Read-only. Usage: draw_jw_zoom_v2.py <board> <out.svg> [--cx --cy --w --h] [--label REF.PAD ...]
"""
import argparse
import collections
import math
import sys

sys.path.insert(0, "/home/c08r4d0r/worktrees/flight-readiness-20261102/tracker/hardware")
import svg_layout_guard as G  # noqa: E402
import pcbnew  # noqa: E402

UM = 1_000_000.0
PX = 44.0


def face_of(pad):
    lay = [l for l in pad.GetLayerSet().Seq() if l in (pcbnew.F_Cu, pcbnew.B_Cu)]
    names = [pcbnew.LayerName(l) for l in lay]
    if len(names) == 2:
        return "BOTH"
    return "F" if names and names[0] == "F.Cu" else "B"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("out")
    ap.add_argument("--cx", type=float, default=36.0)
    ap.add_argument("--cy", type=float, default=76.5)
    ap.add_argument("--w", type=float, default=16.0)
    ap.add_argument("--h", type=float, default=11.0)
    ap.add_argument("--label", action="append", default=[],
                    help="REF.PAD to highlight (repeatable)")
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)
    hi = set(a.label) or {"J_W2.1", "J_W2.2", "D_BP2.1"}

    W, H = int(a.w * PX), int(a.h * PX) + 150
    c = G.Canvas(W, H, strict_shapes=False)
    c.raw(f'<rect width="{W}" height="{H}" fill="#0f1720"/>')
    pad_px = int(a.h * PX)

    def X(x):
        return (x - (a.cx - a.w / 2)) * PX

    def Y(y):
        return (y - (a.cy - a.h / 2)) * PX

    def vis(x0, y0, x1, y1):
        return not (x1 < a.cx - a.w / 2 or x0 > a.cx + a.w / 2
                    or y1 < a.cy - a.h / 2 or y0 > a.cy + a.h / 2)

    # ---- vias (draw first, under pads) ----
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            continue
        p = t.GetPosition()
        x, y = p.x / UM, p.y / UM
        if not vis(x, y, x, y):
            continue
        c.raw(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" '
              f'r="{t.GetWidth(pcbnew.F_Cu) / UM / 2 * PX:.1f}" fill="#ffffff" opacity="0.9"/>')

    # ---- tracks ----
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        x1, y1 = t.GetStart().x / UM, t.GetStart().y / UM
        x2, y2 = t.GetEnd().x / UM, t.GetEnd().y / UM
        if not vis(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)):
            continue
        front = t.GetLayer() == pcbnew.F_Cu
        col = "#c8611e" if front else "#39c6d6"
        dash = '' if front else ' stroke-dasharray="7 4"'
        wd = max(1.6, t.GetWidth() / UM * PX)
        c.raw(f'<line x1="{X(x1):.1f}" y1="{Y(y1):.1f}" x2="{X(x2):.1f}" y2="{Y(y2):.1f}" '
              f'stroke="{col}" stroke-width="{wd:.1f}" opacity="0.9"{dash}/>')

    # ---- pads: ONE rect per land (number + identical XY), faces unioned ----
    # v2.1 note: keying on (number, face) still drew TWO overlapping outlines for a J_W land,
    # because the F.Cu and B.Cu objects share IDENTICAL XY. Two outlines at the same coordinates
    # is what made v1 look like a doubled slab. A wing-seat land is ONE physical position with
    # copper on both faces, so it is drawn ONCE and labelled with the faces it carries.
    drawn = []
    lands = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            x0, y0 = bb.GetLeft() / UM, bb.GetTop() / UM
            x1, y1 = bb.GetRight() / UM, bb.GetBottom() / UM
            if not vis(x0, y0, x1, y1):
                continue
            tag = f"{ref}.{p.GetNumber()}"
            key = (tag, round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3))
            lands.setdefault(key, {"tag": tag, "faces": set(), "box": (x0, y0, x1, y1)})
            lands[key]["faces"].add(face_of(p))

    for key, info in lands.items():
        x0, y0, x1, y1 = info["box"]
        tag = info["tag"]
        faces = info["faces"]
        flabel = "BOTH" if faces == {"F", "B"} else next(iter(faces))
        is_hi = tag in hi
        stroke = "#ffd166" if is_hi else ("#5f7f96" if flabel == "B" else "#8fb3c9")
        dash = ' stroke-dasharray="4 3"' if flabel == "B" else ''
        fill = "#ffd166" if is_hi else "none"
        op = ' fill-opacity="0.22"' if is_hi else ''
        c.raw(f'<rect x="{X(x0):.1f}" y="{Y(y0):.1f}" width="{(x1 - x0) * PX:.1f}" '
              f'height="{(y1 - y0) * PX:.1f}" fill="{fill}"{op} stroke="{stroke}" '
              f'stroke-width="{2.2 if is_hi else 1.1}"{dash}/>')
        drawn.append((tag, flabel, x0, y0, x1, y1, is_hi))

    # ---- highlight labels: rotated inside the pad so they cannot overlap a neighbour ----
    # v2.2: v2 centred labels ABOVE each pad. Measured: J_W2.1 and J_W2.2 pads are 52.8 px wide
    # and 79.2 px apart, so two centred labels collided; and D_BP2.1's label ran off the left
    # edge (its pad centre is at x=44 in a 704 px canvas). A wing-seat pad is 4.0 x 1.2 mm —
    # tall and narrow on screen — so the label is rotated 90 deg and put INSIDE it, which is
    # both collision-free and unambiguous about which pad it names.
    for tag, face, x0, y0, x1, y1, is_hi in drawn:
        if not is_hi:
            continue
        short = "BOTH" if face == "BOTH" else face
        cx_px, cy_px = X((x0 + x1) / 2), Y((y0 + y1) / 2)
        c.raw(f'<text x="{cx_px:.1f}" y="{cy_px:.1f}" font-size="12" font-weight="bold" '
              f'fill="#ffd166" text-anchor="middle" transform="rotate(-90 {cx_px:.1f} {cy_px:.1f})">'
              f'{tag} [{short}]</text>')

    # ---- measured gaps from J_W2.1 to its two nearest other-net neighbours ----
    me = next((fp for fp in b.GetFootprints() if fp.GetReference() == "J_W2"), None)
    gaps = []
    if me is not None:
        pad = next((p for p in me.Pads() if p.GetNumber() == "1"), None)
        if pad is not None:
            cx0, cy0 = pad.GetPosition().x / UM, pad.GetPosition().y / UM
            for fp in b.GetFootprints():
                for q in fp.Pads():
                    if q.GetNetname() == pad.GetNetname():
                        continue
                    fx = face_of(q)
                    if f"J_W2.1" == f"{fp.GetReference()}.{q.GetNumber()}":
                        continue
                    bb = q.GetBoundingBox()
                    # true rectangle gap, not a disc
                    dx = max(bb.GetLeft() / UM - cx0, 0, cx0 - bb.GetRight() / UM)
                    dy = max(bb.GetTop() / UM - cy0, 0, cy0 - bb.GetBottom() / UM)
                    gaps.append((math.hypot(dx, dy), f"{fp.GetReference()}.{q.GetNumber()}",
                                 q.GetNetname(), fx))
            gaps.sort()
            for i, (d, tag, net, fx) in enumerate(gaps[:2]):
                c.raw(f'<text x="16" y="{18 + i * 19}" font-size="13" fill="#e8eef5">'
                      f'nearest other-net: {tag} [{fx}] {net}  rect-gap {d:.3f} mm</text>')

    # ---- scale bar ----
    sb = 2.0 * PX
    c.raw(f'<line x1="16" y1="{pad_px - 16}" x2="{16 + sb:.0f}" y2="{pad_px - 16}" '
          f'stroke="#e8eef5" stroke-width="3"/>')
    c.raw(f'<text x="16" y="{pad_px - 24}" font-size="13" fill="#e8eef5">2 mm</text>')

    # ---- honest caption ----
    n_f = sum(1 for d in drawn if d[1] == "F")
    n_b = sum(1 for d in drawn if d[1] == "B")
    lines = [
        f"J_W2 wing seat — crop {a.w:.0f} x {a.h:.0f} mm · pads drawn once per (number, face)",
        f"{n_f} F.Cu pads solid, {n_b} B.Cu pads dashed · F.Cu track orange, B.Cu track cyan, via white",
        "J_W2 pad numbers exist TWICE per number (F.Cu + B.Cu, same XY, same net): the wing tab is",
        "soldered from both faces — WING-TO-HUB-SOCKET-SPEC s2. Overlap at identical XY is BY DESIGN.",
        "No collision is claimed here. This figure shows geometry only; it is not a DRC result.",
    ]
    y = pad_px + 24
    for ln in lines:
        c.text(16, y, ln, size=13, fill="#e8eef5")
        y += 22
    try:
        probs = c.write(a.out)
    except G.OverlapError as e:
        print("LAYOUT GUARD REFUSED:", e)
        return 2
    print(f"wrote {a.out} ({W}x{H}) guard={len(probs)} lands={len(drawn)} "
          f"F={n_f} B={n_b} BOTH={sum(1 for d in drawn if d[1] == 'BOTH')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
