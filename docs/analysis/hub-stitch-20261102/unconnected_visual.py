#!/usr/bin/env python3
"""Self-calibrating overlay: find the board's rendered extent, then map mm->px.

The first version assumed a fixed margin and drew markers outside the board -- a
visual consultant caught it. This version calibrates: it detects the board's
bounding box in the rendered PNG (non-background pixels), and additionally
renders Edge.Cuts alone to get the exact outline extent, so every marker is
placed from measured geometry, not an assumed margin.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pcbnew as k
from PIL import Image, ImageDraw

SRC = pathlib.Path('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
                   'hub-repair-20261102/output/after')
OUT = pathlib.Path('/home/c08r4d0r/reports/hub-current-visuals/unconnected')
STEM = 'hub_board_v10_lora1280_7of9'


def render(svg, png, width=1600):
    subprocess.run(['rsvg-convert', '-w', str(width), '-b', 'white',
                    '-o', str(png), str(svg)], capture_output=True, text=True)


def content_bbox(png):
    """Pixel bbox of non-white content."""
    im = Image.open(png).convert('RGB')
    W, H = im.size
    px = im.load()
    minx, miny, maxx, maxy = W, H, -1, -1
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            if not (r > 245 and g > 245 and b > 245):
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    return minx, miny, maxx, maxy


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in SRC.glob(STEM + '.kicad_*'):
        shutil.copy(f, OUT / f.name)
    pcb = OUT / (STEM + '.kicad_pcb')

    b = k.LoadBoard(str(pcb))
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)

    drc = OUT / 'drc.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', str(drc),
                    '--severity-all', str(pcb)], capture_output=True, text=True)
    d = json.loads(drc.read_text())

    marks = []
    for rec in d['unconnected_items']:
        descs = [i['description'] for i in rec.get('items', [])]
        joined = ' || '.join(descs)
        if re.search(r'of J_W\d', joined) and 'D_BP' in joined:
            cls = 'real_solar'
        elif 'Zone' in joined:
            cls = 'zone'
        else:
            cls = 'pad'
        for it in rec.get('items', []):
            if 'pos' in it:
                marks.append(dict(x=it['pos']['x'], y=it['pos']['y'],
                                  cls=cls, desc=joined[:140]))
    counts = {}
    for m in marks:
        counts[m['cls']] = counts.get(m['cls'], 0) + 1

    # calibrate from the Edge.Cuts-only render: its content bbox IS the board
    edge_svg = OUT / 'edge_only.svg'
    edge_png = OUT / 'edge_only.png'
    subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', 'Edge.Cuts',
                    '--page-size-mode', '2', '--exclude-drawing-sheet',
                    '-o', str(edge_svg), str(pcb)], capture_output=True, text=True)
    vb = re.search(r'viewBox="([^"]*)"', edge_svg.read_text())
    vx, vy, vw, vh = [float(t) for t in vb.group(1).split()] if vb else (0, 0, 0, 0)
    render(edge_svg, edge_png)
    ex0, ey0, ex1, ey1 = content_bbox(edge_png)

    bb = b.GetBoardEdgesBoundingBox()
    bx0, by0 = bb.GetLeft() / 1e6, bb.GetTop() / 1e6
    bw, bh = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
    print(f'board bbox mm: x{bx0:.3f} y{by0:.3f} w{bw:.3f} h{bh:.3f}')
    print(f'edge png extent px: ({ex0},{ey0})-({ex1},{ey1}) of {Image.open(edge_png).size}')

    def to_px(x, y):
        # X is linear across the extracted extent; Y uses the SVG viewBox mapping
        px = ex0 + (x - vx) / vw * (ex1 - ex0)
        py = ey0 + (y - vy) / vh * (ey1 - ey0)
        return px, py

    colours = {'real_solar': (220, 20, 20), 'zone': (255, 150, 0), 'pad': (30, 80, 230)}
    for layer, tag in (('F.Cu', 'front'), ('In1.Cu', 'in1'),
                       ('In2.Cu', 'in2'), ('B.Cu', 'back')):
        svg = OUT / f'{tag}.svg'
        subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers',
                        f'{layer},Edge.Cuts', '--page-size-mode', '2',
                        '--exclude-drawing-sheet', '-o', str(svg), str(pcb)],
                       capture_output=True, text=True)
        plain = OUT / f'{tag}_plain.png'
        render(svg, plain)
        im = Image.open(plain).convert('RGB')
        W, H = im.size
        # scale the edge-render extent to this image's size (same width setting)
        sx = W / Image.open(edge_png).size[0]
        sy = H / Image.open(edge_png).size[1]
        dr = ImageDraw.Draw(im)
        for m in marks:
            px, py = to_px(m['x'], m['y'])
            px, py = px * sx, py * sy
            r = 22
            dr.ellipse([px - r, py - r, px + r, py + r],
                       outline=colours[m['cls']], width=5)
        dr.rectangle([0, 0, W, 34], fill=(255, 255, 255))
        dr.text((10, 8), f'{layer} | unconnected {len(marks)}: '
                         f'red real-solar {counts.get("real_solar",0)}  '
                         f'amber zone {counts.get("zone",0)}  '
                         f'blue pad {counts.get("pad",0)}', fill=(0, 0, 0))
        im.save(OUT / f'{tag}_marked.png')
        print('wrote', OUT / f'{tag}_marked.png')

    (OUT / 'markers.json').write_text(json.dumps(
        dict(counts=counts, total=len(marks), marks=marks), indent=1))
    print('counts', counts)


if __name__ == '__main__':
    main()
