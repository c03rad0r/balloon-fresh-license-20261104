#!/usr/bin/env python3
"""render_rework_note.py -- the one-page bench note for the two programming wires.

Drawn from board coordinates so the pad positions on the note match the board. Two wires:
    U1.3  (/EN)  -> J_PROG.3
    U1.27 (/IO0) -> J_PROG.6
plus the J_PROG pinout so the cable can be made correctly first time.

Run: python3 docs/analysis/render_rework_note.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pcbnew
from matplotlib.patches import Circle, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "bulk-route-20261107", "latest.kicad_pcb")
OUT = os.path.join(HERE, "bulk-route-20261107", "assets", "REWORK-two-wires.png")

b = pcbnew.LoadBoard(BOARD)
fp_ref = {fp.GetReference(): fp for fp in b.GetFootprints()}
u1, jp = fp_ref["U1"], fp_ref["J_PROG"]


def mm(v):
    return pcbnew.ToMM(v)


def box(fp):
    bb = fp.GetBoundingBox()
    return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetWidth()), mm(bb.GetHeight())


# Taller and with a wider bottom margin: the right-hand instruction box ran off the bottom of the
# canvas at 9.6 in and vision caught it cut off. Give bbox_inches room to breathe.
fig = plt.figure(figsize=(16.5, 11.4))
gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.0], wspace=0.12)

# ---------------- left: where the two wires go ----------------
ax = fig.add_subplot(gs[0, 0])
x1, y1, w1, h1 = box(u1)
x2, y2, w2, h2 = box(jp)
ax.set_xlim(min(x1, x2) - 14, max(x1 + w1, x2 + w2) + 24)
ax.set_ylim(max(y1 + h1, y2 + h2) + 16, min(y1, y2) - 6)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Where the two wires go — true board coordinates", fontsize=12, fontweight="bold")

for ref, col, lbl in (("U1", "#1f4e79", "U1\nESP32-S3-WROOM-1U"),
                      ("J_PROG", "#7d3c98", "J_PROG\n1×6  2.54 mm")):
    x, y, w, h = box(fp_ref[ref])
    ax.add_patch(Rectangle((x, y), w, h, facecolor=col, alpha=0.10, edgecolor=col, lw=2.2, zorder=1))
    # J_PROG is a narrow tall header: put its label BESIDE the box, not inside it, so the dashed
    # wire runs have nothing to collide with.
    if ref == "J_PROG":
        ax.text(x + w + 2.0, y + h / 2, lbl, ha="left", va="center", fontsize=9.0,
                fontweight="bold", color=col, zorder=3, linespacing=1.4)
    else:
        # U1's pad column runs down its LEFT edge, so a centred name sits on the markers.
        # U1's pad column is its LEFT edge and both dashed runs leave to the right, so the only
        # clear place for the name is the LEFT-CENTRE strip, above pad 3 and below the top edge.
        ax.text(x + 1.2, y + 8.0, lbl, ha="left", va="center", fontsize=9.2,
                fontweight="bold", color=col, zorder=14, linespacing=1.4,
                bbox=dict(fc="white", ec=col, lw=0.7, alpha=1.0, pad=3))

P = {}
for p in u1.Pads():
    if p.GetNumber() in ("3", "13", "14", "27"):
        pos = p.GetPosition()
        P[("U1", p.GetNumber())] = (mm(pos.x), mm(pos.y), p.GetNetname())
for p in jp.Pads():
    pos = p.GetPosition()
    P[("J_PROG", p.GetNumber())] = (mm(pos.x), mm(pos.y), p.GetNetname())

WIRED = {"13", "14"}
for num in ("13", "14", "3", "27"):
    x, y, net = P[("U1", num)]
    ok = num in WIRED
    ax.add_patch(Circle((x, y), 1.5, facecolor="#1e8449" if ok else "#b03a2e",
                        edgecolor="white", lw=1.4, zorder=5))
    ax.text(x - 3.6, y, f"pad {num}  {net}", fontsize=8.0, ha="right", va="center",
            color="#1e8449" if ok else "#b03a2e", fontweight="bold", zorder=11,
            bbox=dict(fc="white", ec="none", pad=1.2))

for num in ("3", "6"):
    x, y, net = P[("J_PROG", num)]
    ax.add_patch(Circle((x, y), 1.5, facecolor="#b03a2e", edgecolor="white", lw=1.4, zorder=5))
    ax.text(x - 2.4, y, f"pin {num}  {net}", fontsize=8.0, ha="right", va="center",
            color="#b03a2e", fontweight="bold", zorder=6)

for a, c, label in ((("U1", "3"), ("J_PROG", "3"), "WIRE 1"),
                    (("U1", "27"), ("J_PROG", "6"), "WIRE 2")):
    xa, ya, _ = P[a]
    xc, yc, _ = P[c]
    ax.plot([xa, xc], [ya, yc], lw=2.6, color="#b03a2e", linestyle=(0, (6, 3)), zorder=4)
    # Place the label 30% of the way along the run, measured FROM THE U1 END. At the midpoint the
    # label landed on the J_PROG header text (vision flagged it twice).
    lx = xa + 0.30 * (xc - xa)
    ly = ya + 0.30 * (yc - ya) - 2.2
    ax.text(lx, ly, label, fontsize=9.5, color="#b03a2e",
            fontweight="bold", ha="center", zorder=9,
            bbox=dict(fc="white", ec="#b03a2e", lw=0.9, pad=2))

ax.text(min(x1, x2) - 6, max(y1 + h1, y2 + h2) + 14,
        "orange/red discs = pads that need a wire   ·   green = already has copper",
        fontsize=8.6, color="#4d5656", va="top",
        bbox=dict(fc="white", ec="#bdc3c7", lw=1.0, pad=4), zorder=8)

# ---------------- right: J_PROG pinout for the cable ----------------
ax2 = fig.add_subplot(gs[0, 1])
ax2.axis("off")
ax2.set_xlim(0, 1)
ax2.set_ylim(0, 1)
ax2.set_title("J_PROG pinout — make the cable to this", fontsize=12, fontweight="bold")

pinout = [
    ("1", "GND", "ground", "#4d5656"),
    ("2", "+3V3", "3.3 V from the board", "#4d5656"),
    ("3", "/EN", "RESET — wire 1 lands here", "#b03a2e"),
    ("4", "/USB_DN", "USB D−  (already wired)", "#1e8449"),
    ("5", "/USB_DP", "USB D+  (already wired)", "#1e8449"),
    ("6", "/IO0", "BOOT strap — wire 2 lands here", "#b03a2e"),
]
ax2.text(0.02, 0.93, "pin", fontsize=9, fontweight="bold", color="#555", transform=ax2.transAxes)
ax2.text(0.13, 0.93, "net", fontsize=9, fontweight="bold", color="#555", transform=ax2.transAxes)
ax2.text(0.36, 0.93, "what it is", fontsize=9, fontweight="bold", color="#555", transform=ax2.transAxes)
for i, (pin, net, desc, col) in enumerate(pinout):
    y = 0.90 - i * 0.078
    ax2.text(0.02, y, pin, fontsize=10, fontweight="bold", color=col, transform=ax2.transAxes)
    ax2.text(0.13, y, net, fontsize=10, fontweight="bold", color=col, transform=ax2.transAxes,
             family="monospace")
    ax2.text(0.36, y, desc, fontsize=9, color="#1c2833", transform=ax2.transAxes)

ax2.text(0.02, 0.40,
         "HOW TO MAKE THE WIRES\n\n"
         "  Wire 1:  U1 pad 3 (EN)  →  J_PROG pin 3\n"
         "  Wire 2:  U1 pad 27 (IO0) →  J_PROG pin 6\n\n"
         "  U1 pads are castellated on the module edge — solder to the\n"
         "  pad itself, then tack the other end into the header hole.\n"
         "  Use 30 AWG wire-wrapping wire. Keep each run short and route\n"
         "  it away from the USB D+/D− pair on pads 13/14.\n\n"
         "WHY THEY ARE WIRES AND NOT COPPER\n\n"
         "  U1's pads are 1.50 mm wide on a 1.27 mm pitch, so adjacent\n"
         "  pads overlap by 0.23 mm. A track needs 0.60 mm of channel.\n"
         "  Both escape lanes are crossed by routed nets within 2 mm.\n"
         "  Measured: flood fill from U1.3 reaches only a 2.0 × 1.4 mm\n"
         "  pocket. No router setting closes this; the respin moves the\n"
         "  fan-out instead (ADR-145).\n\n"
         "  Do NOT bridge U1.3 toward U1.4 or U1.27 toward USB_DN — those\n"
         "  are the shorting paths the router produced on every attempt.",
         fontsize=8.7, color="#1c2833", va="top", transform=ax2.transAxes,
         bbox=dict(fc="#fef9e7", ec="#b7950b", lw=1.3, pad=8))

fig.suptitle("Bench rework note — two wires per board, 10 boards", fontsize=13.5, fontweight="bold")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print("wrote", OUT)
