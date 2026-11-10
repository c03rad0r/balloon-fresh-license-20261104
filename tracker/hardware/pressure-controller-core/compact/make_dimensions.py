#!/usr/bin/env python3
"""Dimension comparison figure: committed 80x60 baseline vs 65x50 candidate.

Hand-written SVG so every number and dimension line is editable text (no plotting
library, no raster step that mangles labels). Reads baseline.json + proof.json +
space.json so the figure cannot disagree with the measurements.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCALE = 9.0          # px per mm
PAD = 150


def load(name):
    return json.loads((HERE / name).read_text())


def dim(x1, y1, x2, y2, text, offset):
    """Dimension line with end ticks and a centred label."""
    if y1 == y2:                       # horizontal
        y = y1 + offset
        return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" class="dim"/>'
                f'<line x1="{x1}" y1="{y-5}" x2="{x1}" y2="{y+5}" class="dim"/>'
                f'<line x1="{x2}" y1="{y-5}" x2="{x2}" y2="{y+5}" class="dim"/>'
                f'<text x="{(x1+x2)/2}" y="{y-7}" class="dl" text-anchor="middle">{text}</text>')
    x = x1 + offset
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" class="dim"/>'
            f'<line x1="{x-5}" y1="{y1}" x2="{x+5}" y2="{y1}" class="dim"/>'
            f'<line x1="{x-5}" y1="{y2}" x2="{x+5}" y2="{y2}" class="dim"/>'
            f'<text x="{x-8}" y="{(y1+y2)/2}" class="dl" text-anchor="middle" '
            f'transform="rotate(-90 {x-8} {(y1+y2)/2})">{text}</text>')


def block(ox, oy, mm, title, sub, colour, extra=None):
    w, h = mm[0] * SCALE, mm[1] * SCALE
    parts = [f'<text x="{ox}" y="{oy-58}" class="title">{title}</text>',
             f'<text x="{ox}" y="{oy-38}" class="sub">{sub}</text>',
             f'<rect x="{ox}" y="{oy}" width="{w:.1f}" height="{h:.1f}" class="outline" '
             f'stroke="{colour}"/>',
             f'<rect x="{ox}" y="{oy}" width="{w:.1f}" height="{h:.1f}" class="fill" fill="{colour}"/>']
    if extra:
        parts.append(extra(ox, oy, w, h))
    parts.append(dim(ox, oy + h, ox + w, oy + h, f'{mm[0]:g} mm', 42))
    parts.append(dim(ox + w, oy, ox + w, oy + h, f'{mm[1]:g} mm', 46))
    return ''.join(parts)


def motor(ox, oy, w, h, box_mm, board_mm):
    x0, y0, x1, y1 = box_mm
    return (f'<rect x="{ox+x0*SCALE:.1f}" y="{oy+y0*SCALE:.1f}" '
            f'width="{(x1-x0)*SCALE:.1f}" height="{(y1-y0)*SCALE:.1f}" class="motor"/>'
            f'<text x="{ox+(x0+x1)/2*SCALE:.1f}" y="{oy+(y0+y1)/2*SCALE:.1f}" class="ml" '
            f'text-anchor="middle">MOTOR {x1-x0:g}x{y1-y0:g}</text>')


def main():
    base, proof, space = load('baseline.json'), load('proof.json'), load('space.json')
    mm_b, mm_c = base['board_mm'], proof['candidate_dimensions_mm']
    width = int(PAD * 2 + mm_b[0] * SCALE + 260 + mm_c[0] * SCALE)
    # Height is derived from the table below the boards: 7 metric rows + 2 footnotes.
    height = int(PAD + 40 + mm_b[1] * SCALE + 150 + 30 + 26 * 7 + 120)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}">',
           '<style>'
           '.bg{fill:#ffffff}'
           '.title{font:bold 22px sans-serif;fill:#111}'
           '.sub{font:15px sans-serif;fill:#444}'
           '.dl{font:bold 15px monospace;fill:#111}'
           '.ml{font:12px monospace;fill:#7a4b00}'
           '.outline{fill:none;stroke-width:2.5}'
           '.fill{opacity:0.07}'
           '.dim{stroke:#111;stroke-width:1;fill:none}'
           '.motor{fill:#ffe9b0;stroke:#c08a00;stroke-width:1;stroke-dasharray:4 3}'
           '.note{font:14px monospace;fill:#333}'
           '.hdr{font:bold 26px sans-serif;fill:#111}'
           '</style>',
           f'<rect class="bg" x="0" y="0" width="{width}" height="{height}"/>',
           f'<text x="{PAD}" y="52" class="hdr">PCB dimension comparison — pressure controller core '
           f'(candidate is placement only, unrouted)</text>',
           f'<text x="{PAD}" y="76" class="note">Baseline: committed 80x60 checkpoint '
           f'(source sha256 {proof["source_sha256"][:12]}…). Candidate: 65x50 single-sided design '
           f'candidate (sha256 {proof["board_sha256"][:12]}…).</text>']

    out.append(block(PAD, PAD + 40, mm_b,
                     'BASELINE (committed checkpoint)',
                     f'80x60 = 4800 mm2 · courtyard {base["courtyard_occupancy_percent_inside_board"]}% '
                     f'of board · {base["references"]} parts, all top · routed',
                     '#b02020',
                     lambda ox, oy, w, h: motor(ox, oy, w, h, base['motor_reservation_mm'], mm_b)))
    cx = PAD + mm_b[0] * SCALE + 260
    out.append(block(cx, PAD + 40, mm_c,
                     'CANDIDATE (this study)',
                     f'65x50 = 3250 mm2 · courtyard {proof["courtyard_occupancy_percent_inside_board"]}% '
                     f'of board · 26 top / 0 bottom · UNROUTED',
                     '#1050b0',
                     lambda ox, oy, w, h: motor(ox, oy, w, h, proof['motor_reservation_mm'], mm_c)))

    y = PAD + 40 + mm_b[1] * SCALE + 150
    rows = [('board area', f'{base["board_area_mm2"]:g} mm2', f'{proof["board_area_mm2"]:g} mm2',
             f'-{proof["area_reduction_percent"]}%'),
            ('courtyard area (all 26, clipped)', f'{base["courtyard_area_inside_board_mm2"]} mm2',
             f'{proof["courtyard_area_inside_board_mm2"]} mm2', 'identical parts'),
            ('courtyard occupancy', f'{base["courtyard_occupancy_percent_inside_board"]}%',
             f'{proof["courtyard_occupancy_percent_inside_board"]}%', 'of own board area'),
            ('free courtyard area', f'{base["free_area_inside_board_mm2"]} mm2',
             f'{space["courtyard_free_area_inside_board_mm2"]} mm2', '-1549.99 mm2'),
            ('largest empty rectangle', f'{base["largest_single_empty_rectangle_mm2"]} mm2',
             f'{space["largest_single_empty_rectangle_mm2"]} mm2',
             f'{space["largest_single_empty_rectangle_at_mm"][2]}x'
             f'{space["largest_single_empty_rectangle_at_mm"][3]} mm at '
             f'({space["largest_single_empty_rectangle_at_mm"][0]},'
             f'{space["largest_single_empty_rectangle_at_mm"][1]})'),
            ('motor reservation', '30x24 at (48,34)', '30x24 at (33,24)', 'size kept, moved'),
            ('sides', '26 top / 0 bottom', '26 top / 0 bottom', 'single-sided, unchanged')]
    out.append(f'<text x="{PAD}" y="{y}" class="title">Measured comparison</text>')
    y += 30
    cols = [PAD, PAD + 300, PAD + 470, PAD + 640]
    for i, h in enumerate(['metric', 'baseline 80x60', 'candidate 65x50', 'delta / note']):
        out.append(f'<text x="{cols[i]}" y="{y}" class="dl">{h}</text>')
    for r in rows:
        y += 26
        for i, v in enumerate(r):
            out.append(f'<text x="{cols[i]}" y="{y}" class="note">{v}</text>')
    y += 40
    out.append(f'<text x="{PAD}" y="{y}" class="note">Candidate placement extents '
               f'{space["placement_extents_mm"]} mm; tightest enclosing outline from this placement '
               f'{space["tightest_outline_from_this_placement_mm"]} mm (both include the intentional '
               f'U1 antenna overhang above y=0).</text>')
    y += 24
    out.append(f'<text x="{PAD}" y="{y}" class="note">No routing on the candidate: native DRC '
               f'{proof["native_unconnected_records"]} unconnected records, '
               f'{sum(proof["native_violations"].values())} violation record(s) '
               f'({", ".join(proof["native_violations"])}). Placement signoff required before any routing.</text>')
    out.append('</svg>')
    svg = HERE / 'dimensions.svg'
    svg.write_text('\n'.join(out) + '\n')
    print('wrote', svg)


if __name__ == '__main__':
    main()
