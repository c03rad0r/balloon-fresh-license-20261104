#!/usr/bin/env python3
"""Render copper TRACKS only (no zones) for a visual route review.

Why: a normal layer plot drowns the traces in zone fill -- a vision pass on
`candidate-layers.png` reported "blue fill dominates, some blue-layer traces have little
contrast against it", which is true and makes the image useless for judging routes. This draws
what a reviewer actually needs to see: every track, via and pad, with zones omitted.

Front = warm, back = cool, other-net pads = grey. New solar copper is drawn LAST so it sits on top.

Usage: render_tracks.py <board> <out.svg> [--width MM] [--height MM]
"""
import argparse
import sys

import pcbnew

UM = 1_000_000.0
C = {
    "bg": "#101418",
    "edge": "#8a93a0",
    "fcu": "#d9534f",
    "bcu": "#2f7fd1",
    "bcub": "#7fb8ea",
    "pad": "#c9a227",
    "via": "#e8e8e8",
    "hole": "#101418",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("out")
    ap.add_argument("--width", type=float, default=72.1)
    ap.add_argument("--height", type=float, default=80.1)
    ap.add_argument("--highlight", default="SOLAR",
                    help="substring of net names to draw last/on top (default SOLAR)")
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)

    S = 12.0  # px per mm
    W, H = int(a.width * S) + 40, int(a.height * S) + 40
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>',
         f'<g transform="translate(20,20) scale({S})">']
    o.append(f'<rect x="0" y="0" width="{a.width}" height="{a.height}" fill="none" '
             f'stroke="{C["edge"]}" stroke-width="0.15"/>')

    # board outline as light path
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            pts = [(d.GetStart().x / UM, d.GetStart().y / UM),
                   (d.GetEnd().x / UM, d.GetEnd().y / UM)]
            o.append(f'<line x1="{pts[0][0]}" y1="{pts[0][1]}" x2="{pts[1][0]}" '
                     f'y2="{pts[1][1]}" stroke="{C["edge"]}" stroke-width="0.12"/>')

    def draw_track(t, color, extra=""):
        s, e = t.GetStart(), t.GetEnd()
        o.append(f'<line x1="{s.x/UM:.3f}" y1="{s.y/UM:.3f}" x2="{e.x/UM:.3f}" '
                 f'y2="{e.y/UM:.3f}" stroke="{color}" stroke-width="{t.GetWidth()/UM:.3f}" '
                 f'stroke-linecap="round"{extra}/>')

    # pads (context)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            ls = p.GetLayerSet().Seq()
            if pcbnew.B_Cu not in ls and pcbnew.F_Cu not in ls:
                continue
            bb = p.GetBoundingBox()
            x, y = bb.GetLeft() / UM, bb.GetTop() / UM
            w, h = bb.GetWidth() / UM, bb.GetHeight() / UM
            o.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" '
                     f'fill="{C["pad"]}" fill-opacity="0.55" stroke="none"/>')

    trk = list(b.GetTracks())
    plain = [t for t in trk if a.highlight.upper() not in t.GetNetname().upper()]
    hl = [t for t in trk if a.highlight.upper() in t.GetNetname().upper()]

    for t in plain:
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            r = t.GetWidth() / UM / 2
            o.append(f'<circle cx="{p.x/UM:.3f}" cy="{p.y/UM:.3f}" r="{r:.3f}" '
                     f'fill="{C["via"]}"/>')
            continue
        if t.GetLayer() == pcbnew.F_Cu:
            draw_track(t, C["fcu"])
        elif t.GetLayer() == pcbnew.B_Cu:
            draw_track(t, C["bcu"])

    # highlighted net last, thicker halo so it reads at Signal scale
    for t in hl:
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            r = t.GetWidth() / UM / 2
            o.append(f'<circle cx="{p.x/UM:.3f}" cy="{p.y/UM:.3f}" r="{r*2.2:.3f}" '
                     f'fill="#ffd166" fill-opacity="0.30"/>')
            o.append(f'<circle cx="{p.x/UM:.3f}" cy="{p.y/UM:.3f}" r="{r:.3f}" '
                     f'fill="{C["via"]}"/>')
            continue
        if t.GetLayer() == pcbnew.B_Cu:
            draw_track(t, "#ffd166", ' stroke-opacity="0.35"')
    for t in hl:
        if t.Type() != pcbnew.PCB_VIA_T and t.GetLayer() == pcbnew.B_Cu:
            draw_track(t, "#9fe870")

    o.append("</g></svg>")
    open(a.out, "w").write("\n".join(o))
    nf = sum(1 for t in trk if t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)
             and t.Type() != pcbnew.PCB_VIA_T and a.highlight.upper() not in t.GetNetname().upper())
    print(f"tracks={len(trk)} plain={nf} highlighted={len(hl)} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
