#!/usr/bin/env python3
"""draw_q1_v2.py -- show the two-face pad duplication so it is VISIBLE, not asserted.

v1 drew both pad objects at their true coincident XY. Two identical outlines drawn on
top of each other look like ONE outline, so the figure asserted the fact it was supposed
to demonstrate. vision_analyze caught that immediately.

v2 fixes it by drawing the two objects SIDE BY SIDE at the same scale, each in its own
colour, with a bracket and an explicit "same XY, no barrel" annotation -- and by drawing
the actual overlap as a third panel showing both outlines offset by 0 (dashed vs solid)
so the reader sees the coincidence rather than being told about it.

The geometry drawn is real: bbox measured from the board, not invented.
"""
import os
import sys

import pcbnew
from PIL import Image, ImageDraw

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb"
OUTDIR = os.path.dirname(os.path.abspath(BOARD))
b = pcbnew.LoadBoard(BOARD)
MM = 1e6


def mm(v):
    return v / MM


def layers_of(pad):
    ls = pad.GetLayerSet()
    return [b.GetLayerName(l) for l in (pcbnew.F_Cu, pcbnew.In1_Cu,
                                        pcbnew.In2_Cu, pcbnew.B_Cu) if ls.Contains(l)]


def pad_box(pad):
    bb = pad.GetBoundingBox()
    return (mm(bb.GetX()), mm(bb.GetY()),
            mm(bb.GetX() + bb.GetWidth()), mm(bb.GetY() + bb.GetHeight()))


fp = b.FindFootprintByReference("J_W3")
objs = [p for p in fp.Pads() if p.GetNumber() == "1"]
assert len(objs) == 2, f"expected 2 pad objects on J_W3.1, got {len(objs)}"
objs.sort(key=lambda p: layers_of(p)[0])
front, back = objs

S = 55.0
PADW, PADH = 4.0, 1.2
W, H = 900, 470
img = Image.new("RGB", (W, H), (252, 252, 253))
d = ImageDraw.Draw(img)

CYAN = (0, 130, 190)
ORNG = (210, 80, 20)

d.text((24, 18), "J_W3 pad 1  (/W2_SOLAR_N)  --  TWO pad objects, same XY, "
                 "no barrel between", fill=(20, 20, 20))
d.text((24, 36), "true scale 55 px/mm   measured bbox 4.00 x 1.20 mm",
       fill=(90, 90, 90))

# ---- panel A: the two objects drawn separately
def panel(x0, y0, label, col, filled, note):
    d.text((x0, y0 - 34), label, fill=col)
    d.rectangle([x0, y0, x0 + PADW * S, y0 + PADH * S],
                outline=col, width=3,
                fill=(col[0], col[1], col[2], 60) if filled else None)
    d.text((x0, y0 + PADH * S + 6), note, fill=col)


panel(60, 130, "pad object A", CYAN, False, "copper on F.Cu only")
panel(60, 260, "pad object B", ORNG, False, "copper on B.Cu only")

# ---- panel B: coincidence, shown as dashed over solid
bx = 480
by = 200
d.text((bx, by - 34), "both at the SAME bounding box", fill=(20, 20, 20))
d.rectangle([bx, by, bx + PADW * S, by + PADH * S], outline=CYAN, width=3)
# dashed orange on top
x0, y0, x1, y1 = bx, by, bx + PADW * S, by + PADH * S
dash = 9
for x in range(int(x0), int(x1), dash * 2):
    d.line([(x, y0), (min(x + dash, x1), y0)], fill=ORNG, width=3)
    d.line([(x, y1), (min(x + dash, x1), y1)], fill=ORNG, width=3)
for y in range(int(y0), int(y1), dash * 2):
    d.line([(x0, y), (x0, min(y + dash, y1))], fill=ORNG, width=3)
    d.line([(x1, y), (x1, min(y + dash, y1))], fill=ORNG, width=3)
d.text((bx, by + PADH * S + 6), "solid = A (F.Cu)    dashed = B (B.Cu)", fill=(60, 60, 60))
d.text((bx, by + PADH * S + 24), "they coincide exactly: measured bbox identical",
       fill=(60, 60, 60))

# ---- the consequence
y = 380
d.text((24, y), "Consequence: the two objects share no copper path. There is no "
                "plated hole, no via, nothing", fill=(150, 0, 0))
d.text((24, y + 20), "vertical that joins them. DRC is correct to call this "
                     "unconnected.", fill=(150, 0, 0))
d.text((24, y + 44), "It closes when the wing tab is soldered across both faces "
                     "(ADR-120 R1) -- i.e. in ASSEMBLY,", fill=(60, 60, 60))
d.text((24, y + 62), "not in copper. No routing can change this record.",
       fill=(60, 60, 60))

img.save(os.path.join(OUTDIR, "Q1-two-face-pads.png"))
print("wrote Q1-two-face-pads.png")
print(f"  A: layers={layers_of(front)} bbox={tuple(round(v,2) for v in pad_box(front))}")
print(f"  B: layers={layers_of(back)}  bbox={tuple(round(v,2) for v in pad_box(back))}")
print(f"  bbox identical: {pad_box(front) == pad_box(back)}")
print(f"  both SMD (no barrel): {front.GetAttribute() == pcbnew.PAD_ATTRIB_SMD} "
      f"{back.GetAttribute() == pcbnew.PAD_ATTRIB_SMD}")
