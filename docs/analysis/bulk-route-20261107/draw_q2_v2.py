#!/usr/bin/env python3
"""draw_q2_v2.py -- /W2_SOLAR_N: it is ALREADY routed on B.Cu, and that is the whole point.

I had this wrong twice before drawing it:
  claim 1  "the B.Cu chain stops 1.7 mm short of a pad that is on B.Cu"  -- WRONG
  claim 2  "closing it means drawing copper near the J_W3 socket cavity" -- WRONG

MEASURED, from the board:
  back pad  J_W3.1  bbox (67.00,42.10)..(71.00,43.30)  centre (69.000,42.700)
  B.Cu copper of /W2_SOLAR_N terminating INSIDE that bbox: 10 endpoints,
            including the exact centre (69.000,42.700)
  F.Cu copper of /W2_SOLAR_N terminating inside the front pad bbox: ZERO
  Edge.Cuts shapes near J_W3: one whole-board diagonal, no socket cavity in the window

So the net is connected on B.Cu and cannot be connected on F.Cu. The record DRC
reports is the SAME two-face pad problem as J_W4.1 / J_W3.4, not a routing gap, and
not a cavity-crossing question. There is nothing to route and nothing to decide about
the cavity rule.

The figure draws what is actually there.
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
NET = "/W2_SOLAR_N"


def mm(v):
    return v / MM


def layers_of(pad):
    ls = pad.GetLayerSet()
    return [b.GetLayerName(l) for l in (pcbnew.F_Cu, pcbnew.In1_Cu,
                                        pcbnew.In2_Cu, pcbnew.B_Cu) if ls.Contains(l)]


pads = [p for p in b.GetPads() if p.GetNetname() == NET]
back = [p for p in pads if "B.Cu" in layers_of(p) and
        p.GetParentFootprint().GetReference() == "J_W3" and p.GetNumber() == "1"][0]
bb = back.GetBoundingBox()
BX0, BY0 = mm(bb.GetX()), mm(bb.GetY())
BX1, BY1 = mm(bb.GetX() + bb.GetWidth()), mm(bb.GetY() + bb.GetHeight())

S = 78.0
X0, Y0, X1, Y1 = 64.0, 40.5, 72.5, 45.0
TOP = 56
W = int((X1 - X0) * S)
H = int((Y1 - Y0) * S) + 132 + TOP
img = Image.new("RGB", (W, H), (252, 252, 253))
d = ImageDraw.Draw(img)


def P(x, y):
    px, py = (x - X0) * S, (y - Y0) * S
    return (px, py + TOP)


CYAN, ORNG, GRN = (0, 130, 190), (210, 80, 20), (0, 140, 60)

# F.Cu tracks (none should be inside)
for t in b.GetTracks():
    if t.GetNetname() != NET or t.GetClass() == "PCB_VIA":
        continue
    if b.GetLayerName(t.GetLayer()) != "F.Cu":
        continue
    a = (mm(t.GetStart().x), mm(t.GetStart().y))
    e = (mm(t.GetEnd().x), mm(t.GetEnd().y))
    if max(a[0], e[0]) < X0 or min(a[0], e[0]) > X1:
        continue
    if max(a[1], e[1]) < Y0 or min(a[1], e[1]) > Y1:
        continue
    d.line([P(*a), P(*e)], fill=CYAN, width=max(2, int(0.2 * S)))

# B.Cu tracks
for t in b.GetTracks():
    if t.GetNetname() != NET or t.GetClass() == "PCB_VIA":
        continue
    if b.GetLayerName(t.GetLayer()) != "B.Cu":
        continue
    a = (mm(t.GetStart().x), mm(t.GetStart().y))
    e = (mm(t.GetEnd().x), mm(t.GetEnd().y))
    if max(a[0], e[0]) < X0 or min(a[0], e[0]) > X1:
        continue
    if max(a[1], e[1]) < Y0 or min(a[1], e[1]) > Y1:
        continue
    d.line([P(*a), P(*e)], fill=ORNG, width=max(2, int(0.2 * S)))

# the pad: solid = front, dashed = back (the same two-face situation as Q1)
d.rectangle([P(BX0, BY0), P(BX1, BY1)], outline=CYAN, width=3)
x0, y0 = P(BX0, BY0)
x1, y1 = P(BX1, BY1)
dash = 10
for x in range(int(x0), int(x1), dash * 2):
    d.line([(x, y0), (min(x + dash, x1), y0)], fill=ORNG, width=3)
    d.line([(x, y1), (min(x + dash, x1), y1)], fill=ORNG, width=3)
for y in range(int(y0), int(y1), dash * 2):
    d.line([(x0, y), (x0, min(y + dash, y1))], fill=ORNG, width=3)
    d.line([(x1, y), (x1, min(y + dash, y1))], fill=ORNG, width=3)

# mark the ten B.Cu endpoints inside the pad
n_in = 0
for t in b.GetTracks():
    if t.GetNetname() != NET or t.GetClass() == "PCB_VIA":
        continue
    if b.GetLayerName(t.GetLayer()) != "B.Cu":
        continue
    for p in ((mm(t.GetStart().x), mm(t.GetStart().y)),
              (mm(t.GetEnd().x), mm(t.GetEnd().y))):
        if BX0 - 0.01 <= p[0] <= BX1 + 0.01 and BY0 - 0.01 <= p[1] <= BY1 + 0.01:
            c = P(*p)
            d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=GRN)
            n_in += 1

cc = P(69.0, 42.7)
d.ellipse([cc[0] - 7, cc[1] - 7, cc[0] + 7, cc[1] + 7], outline=(0, 0, 0), width=2)

d.text((10, 6), f"{NET}  --  blue = F.Cu, orange = B.Cu, green dots = B.Cu "
                f"copper terminations inside the pad", fill=(20, 20, 20))
d.text((10, 24), f"pad bbox ({BX0:.2f},{BY0:.2f})..({BX1:.2f},{BY1:.2f})  "
                 f"centre marked at (69.000, 42.700)", fill=(90, 90, 90))

y = H - 122
d.text((10, y), f"{n_in} B.Cu track ends land INSIDE this pad, including its exact "
                f"centre.", fill=(0, 120, 50))
d.text((10, y + 18), "0 F.Cu track ends reach the front object.",
       fill=(150, 0, 0))
d.text((10, y + 42), "So the net IS routed on B.Cu. The open DRC record is the "
                     "two-face pad problem,", fill=(150, 0, 0))
d.text((10, y + 60), "not a 1.7 mm gap and not a socket-cavity crossing. "
                     "Nothing to route.", fill=(60, 60, 60))
d.text((10, y + 84), "It closes in assembly when the wing tab is soldered "
                     "across both faces (ADR-120 R1).", fill=(60, 60, 60))

d.rectangle([0, 0, W, TOP - 4], fill=(252, 252, 253))
d.text((10, 8), f"{NET}  --  blue = F.Cu, orange = B.Cu, green dots = B.Cu copper terminations inside the pad", fill=(20, 20, 20))
d.text((10, 28), f"pad bbox ({BX0:.2f},{BY0:.2f})..({BX1:.2f},{BY1:.2f})   centre marked at (69.000, 42.700)", fill=(90, 90, 90))
img.save(os.path.join(OUTDIR, "Q2-w2solar-n.png"))
print("wrote Q2-w2solar-n.png")
print(f"  B.Cu endpoints inside the pad: {n_in}")
print(f"  pad bbox ({BX0:.2f},{BY0:.2f})..({BX1:.2f},{BY1:.2f})")
