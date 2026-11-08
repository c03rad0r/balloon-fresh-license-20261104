#!/usr/bin/env python3
"""decide_board.py -- WHERE the six undecided nets are, on the whole board.

Not a clearance forensics figure (three attempts at that each failed to prove their own claim,
because the blocking rule turned out to be hole/edge clearance, not neighbour copper). This is
the simple thing the question actually needs: the board, the 6 nets that need a human decision,
and the 3 options.

Colour code:
  light grey  board outline
  dark grey   every pad on the board (context)
  amber       the 6 pads whose nets need a decision
  blue ring   the far island each must eventually reach
"""
import importlib.util
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

W = R.World(os.path.join(HERE, "latest.kicad_pcb"))

# pad needing a decision  ->  the island it must reach
DECIDE = [
    ("/EN",        "U1", "3",  "J_PROG", "3"),
    ("/SPI2_SCK",  "U1", "4",  "U2", "12"),
    ("/SPI1_MISO", "U3", "3",  "U_C", "3"),
    ("/SPI1_MOSI", "U3", "4",  "U_C", "4"),
    ("/VSCAP",     "R_BAL1", "1", "C_CAP1", "1"),
    ("/F33_VSENSE","U1", "21", "R_MON1", "2"),
]

PANEL_W, PANEL_H = 1500, 1160
TOP = 150
SIDE = 470
M = 20


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


F_T, F_S, F_XS, F_N = font(30), font(19), font(16), font(13)

img = Image.new("RGB", (PANEL_W + SIDE + M * 3, TOP + PANEL_H + M), "white")
d = ImageDraw.Draw(img)

d.text((M, 18), "The 28 remaining opens: 22 need nothing from you, 6 do", font=F_T, fill="#202124")
d.text((M, 60), "Grey = all pads.   Amber = the 6 nets that cannot be routed at this placement.   "
                "Blue ring = the far island each must reach.", font=F_S, fill="#3c4043")
d.text((M, 88), "The other 22: 15 two-face assembly lands (complete in the wing-tab assembly, "
                "ADR-120 R1) + 3 GND zone-anchor records + 4 already routed.",
       font=F_XS, fill="#5f6368")
d.text((M, 110), "Board: latest.kicad_pcb  669ac850  ·  28 opens  ·  24 violations (all warning, "
                "unchanged since baseline)", font=F_XS, fill="#5f6368")

bb = W.b.GetBoardEdgesBoundingBox()
bb = (bb.GetX()/R.UM, bb.GetY()/R.UM, (bb.GetX()+bb.GetWidth())/R.UM, (bb.GetY()+bb.GetHeight())/R.UM)
bw, bh = bb[2] - bb[0], bb[3] - bb[1]
sc = min((PANEL_W - 40) / bw, (PANEL_H - 40) / bh)
ox = M + (PANEL_W - bw * sc) / 2
oy = TOP + (PANEL_H - bh * sc) / 2


def T(x, y):
    return (ox + (x - bb[0]) * sc, oy + (y - bb[1]) * sc)


d.rectangle([T(bb[0], bb[1]), T(bb[2], bb[3])], outline="#80868b", width=3)

for q in W.pads:
    a, b = T(q["rect"][0], q["rect"][1]), T(q["rect"][2], q["rect"][3])
    d.rectangle([a, b], fill="#bdc1c6")

for net, ref, num, fref, fnum in DECIDE:
    ps = [q for q in W.pads if q["ref"] == ref and q["num"] == num and q["net"] == net]
    fs = [q for q in W.pads if q["ref"] == fref and q["num"] == fnum and q["net"] == net]
    if not ps or not fs:
        continue
    p, f = ps[0], fs[0]
    pc = ((p["rect"][0] + p["rect"][2]) / 2, (p["rect"][1] + p["rect"][3]) / 2)
    fc = ((f["rect"][0] + f["rect"][2]) / 2, (f["rect"][1] + f["rect"][3]) / 2)

    # the unbuilt connection, as a dashed amber line
    n = max(2, int(math.dist(pc, fc) * sc / 9))
    for k in range(0, n, 2):
        t0, t1 = k / n, min(1.0, (k + 1) / n)
        d.line([T(pc[0] + (fc[0] - pc[0]) * t0, pc[1] + (fc[1] - pc[1]) * t0),
                T(pc[0] + (fc[0] - pc[0]) * t1, pc[1] + (fc[1] - pc[1]) * t1)],
               fill="#f9ab00", width=3)
    r = 11
    d.ellipse([T(*pc)[0] - r, T(*pc)[1] - r, T(*pc)[0] + r, T(*pc)[1] + r],
              fill="#f9ab00", outline="#b06000", width=2)
    r2 = 8
    d.ellipse([T(*fc)[0] - r2, T(*fc)[1] - r2, T(*fc)[0] + r2, T(*fc)[1] + r2],
              outline="#1a73e8", width=3)
    d.text((T(*pc)[0] + 14, T(*pc)[1] - 8), net, font=F_N, fill="#b06000")

# right-hand option panel
sx = M + PANEL_W + M
d.text((sx, TOP), "Your decision: pick ONE", font=F_S, fill="#202124")
opts = [
    ("A", "Move parts",
     "Nudge U1 / U_C / R_BAL1 to open the",
     "corridor. Closes all 6. Changes a board",
     "under Astra CHANGES_REQUESTED."),
    ("B", "Reassign pins",
     "Route these nets to different MCU pins",
     "that have an escape. Closes all 6.",
     "Changes the schematic and the netlist."),
    ("C", "Accept assembly",
     "Let them complete through the wing-tab",
     "interface like the 15 solar lands.",
     "No copper change. Needs a design call."),
]
yy = TOP + 40
for tag, name, *lines in opts:
    d.rectangle([sx, yy, sx + SIDE - 20, yy + 150], outline="#dadce0", width=2)
    d.text((sx + 14, yy + 10), f"{tag}   {name}", font=F_S, fill="#1a73e8")
    for i, ln in enumerate(lines):
        d.text((sx + 14, yy + 42 + i * 22), ln, font=F_N, fill="#3c4043")
    yy += 166

d.text((sx, yy + 6), "My recommendation: C, then A later.", font=F_N, fill="#202124")
d.text((sx, yy + 30), "C costs nothing and unblocks the", font=F_N, fill="#5f6368")
d.text((sx, yy + 52), "count now. A is the real fix but", font=F_N, fill="#5f6368")
d.text((sx, yy + 74), "belongs after Astra's review lands.", font=F_N, fill="#5f6368")

out = os.path.join(HERE, "DECISION-board.png")
img.save(out)
print("wrote", out, os.path.getsize(out), "bytes")
