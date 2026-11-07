"""Render the ACTUAL current opens on the live board -- one image, no stale targeting.

The repo's render_routing_status.py takes a hardcoded --net default, so it draws whichever
nets it was written for rather than what is open now. That is misleading in a status
report. This reads the current DRC report and draws exactly the nets that are still
unconnected, with the board as-is.

Layers: F.Cu orange, B.Cu cyan, via/pads neutral. Open nets get a white circle on each
endpoint and a thin leader line, so WHAT REMAINS is unambiguous.

Usage:
  render_open_status.py OUT.png --board B.kicad_pcb --drc D.json
"""
import argparse
import json
import os
import sys
import math

import pcbnew
from PIL import Image, ImageDraw, ImageFont

UM = 1_000_000.0
C_BG = (14, 16, 22)
C_F = (235, 140, 40)
C_B = (0, 175, 205)
C_PAD = (120, 130, 145)
C_EDGE = (150, 160, 175)
C_MARK = (255, 70, 110)
C_TEXT = (235, 240, 248)


def load_opens(drc_path):
    with open(drc_path) as fh:
        d = json.load(fh)
    items = []
    for u in d.get('unconnected_items', []):
        for it in u.get('items', []):
            pos = it.get('pos') or {}
            x = pos.get('x')
            y = pos.get('y')
            desc = it.get('description', '')
            if x is None or y is None:
                continue
            net = ''
            if '[' in desc and ']' in desc:
                net = desc[desc.index('[') + 1:desc.index(']')]
            items.append({'x': float(x), 'y': float(y), 'net': net, 'desc': desc})
    return items, len(d.get('unconnected_items', []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--board', required=True)
    ap.add_argument('--drc', required=True,
                    help='kicad-cli DRC JSON for the SAME board. Generate it first with: '
                         'kicad-cli pcb drc --format json --severity-all --units mm '
                         '--output DRC.json <board>. Without this the render has no opens to draw.')
    ap.add_argument('--scale', type=float, default=10.0)
    ap.add_argument('--pad', type=int, default=14)
    a = ap.parse_args()

    b = pcbnew.LoadBoard(a.board)
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetX() / UM, bb.GetY() / UM
    w, h = bb.GetWidth() / UM, bb.GetHeight() / UM
    S = a.scale
    P = a.pad
    W = int(w * S) + 2 * P
    H = int(h * S) + 2 * P
    im = Image.new('RGB', (W, H), C_BG)
    dr = ImageDraw.Draw(im)
    try:
        fnt = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
        fnt2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
    except Exception:
        fnt = fnt2 = ImageFont.load_default()

    def px(x, y):
        return (P + (x - x0) * S, P + (y - y0) * S)

    # board outline
    op = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(op)
    for i in range(op.OutlineCount()):
        pts = [px(v.x / UM, v.y / UM) for v in op.COutline(i).CPoints()]
        if len(pts) > 2:
            dr.line(pts + [pts[0]], fill=C_EDGE, width=2)

    # copper
    for t in b.GetTracks():
        s, e = t.GetStart(), t.GetEnd()
        p1, p2 = px(s.x / UM, s.y / UM), px(e.x / UM, e.y / UM)
        if isinstance(t, pcbnew.PCB_VIA):
            r = max(2, int((t.GetWidth() / UM) * S / 2))
            dr.ellipse([p1[0] - r, p1[1] - r, p1[0] + r, p1[1] + r],
                       outline=(200, 210, 225), width=1)
            continue
        lay = t.GetLayer()
        col = C_F if lay == pcbnew.F_Cu else (C_B if lay == pcbnew.B_Cu else None)
        if col is None:
            continue
        wpx = max(1, int((t.GetWidth() / UM) * S))
        dr.line([p1, p2], fill=col, width=wpx)

    # pads
    for f in b.GetFootprints():
        for q in f.Pads():
            c = q.GetPosition()
            cx, cy = px(c.x / UM, c.y / UM)
            sz = q.GetSize()
            r = max(2, int((min(sz.x, sz.y) / UM) * S / 2))
            onF = q.IsOnLayer(pcbnew.F_Cu)
            onB = q.IsOnLayer(pcbnew.B_Cu)
            col = C_F if (onF and not onB) else (C_B if (onB and not onF) else C_PAD)
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=1)

    # header FIRST so the marker/label pass paints over it, never under it
    dr.rectangle([0, 0, W, 46], fill=(20, 24, 33))
    dr.text((12, 6), 'CURRENT OPENS: --', font=fnt, fill=C_TEXT)

    # CURRENT opens
    items, n_opens = load_opens(a.drc)
    drawn = set()
    for it in items:
        cx, cy = px(it['x'], it['y'])
        dr.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=C_MARK, width=2)
        key = (round(it['x'], 2), round(it['y'], 2), it['net'])
        if key in drawn:
            continue
        drawn.add(key)
        lbl = it['net'] or '?'
        tw = dr.textlength(lbl, font=fnt2)
        # place the label to the right of the marker, but flip it to the LEFT and/or clamp
        # vertically when it would run off the image. The board is 72 x 80 mm and several
        # opens sit hard against the right edge, so a right-only label gets clipped.
        bx = cx + 10
        if bx + 4 + tw > W - 2:
            bx = cx - 14 - tw
        bx = max(2, min(bx, W - 6 - tw))
        by = cy - 8
        by = max(56, min(by, H - 20))
        dr.rectangle([bx - 2, by - 1, bx + 2 + tw, by + 16], fill=(40, 16, 24))
        dr.text((bx, by), lbl, font=fnt2, fill=(255, 170, 190))

    # header text (drawn last so the count is truthful; the band itself is drawn earlier)
    dr.text((12, 6), 'CURRENT OPENS: %d unconnected items' % n_opens, font=fnt, fill=C_TEXT)
    dr.text((12, 27), 'F.Cu orange   B.Cu cyan   red ring = open endpoint   '
                      'board %s' % os.path.basename(a.board), font=fnt2, fill=(170, 180, 195))

    im.save(a.out)
    print('saved %s  %dx%d  opens=%d endpoints=%d' % (a.out, W, H, n_opens, len(items)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
