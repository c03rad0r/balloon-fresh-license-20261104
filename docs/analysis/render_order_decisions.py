#!/usr/bin/env python3
"""render_order_decisions.py -- the two decisions the operator must make, drawn from real board
coordinates rather than described in prose.

DECISION 1  U_C (the second LoRa2021 site): populate or omit?
DECISION 2  The two bodge wires: all 10 boards, 4 of 10, or none?

Every coordinate comes from pcbnew on the board of record, so the pictures cannot drift from the
artefact. The GPIO budget is enumerated from the board, not quoted.

LAYOUT NOTE: the three panels are sized from the MEASURED bounding boxes, and the explanatory notes
sit in regions that the measured boxes leave empty. An earlier version placed a note box on top of
both radio modules because the axes limits were guessed rather than derived; vision review caught
it. If a footprint moves, re-run this and re-check -- do not hand-tune the limits.

Run: python3 docs/analysis/render_order_decisions.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pcbnew
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "bulk-route-20261107", "latest.kicad_pcb")
OUT = os.path.join(HERE, "bulk-route-20261107", "assets", "ORDER-DECISIONS.png")

b = pcbnew.LoadBoard(BOARD)


def mm(v):
    return pcbnew.ToMM(v)


fp_ref = {fp.GetReference(): fp for fp in b.GetFootprints()}
u1, u_c, u3, jp = fp_ref["U1"], fp_ref["U_C"], fp_ref["U3"], fp_ref["J_PROG"]


def box(fp):
    bb = fp.GetBoundingBox()
    return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetWidth()), mm(bb.GetHeight())


def ctrl_pads(fp):
    out = {}
    for p in fp.Pads():
        if p.GetNumber() in ("6", "7", "14", "15"):
            pos = p.GetPosition()
            out[p.GetNumber()] = (mm(pos.x), mm(pos.y), p.GetNetname())
    return out


uc_ctrl, u3_ctrl = ctrl_pads(u_c), ctrl_pads(u3)

u1pads = [(p.GetNumber(), mm(p.GetPosition().x), mm(p.GetPosition().y), p.GetNetname())
          for p in u1.Pads()]
free_pads = [n for n, _, _, net in u1pads if not net and n]
UNUSABLE = {"16", "26", "28", "29", "30"}   # input-only / octal PSRAM
usable = [n for n in free_pads if n not in UNUSABLE]

# ---- derive the axes limit from the measured boxes, not from a guess ----
boxes = {r: box(fp_ref[r]) for r in ("U3", "U_C", "U1")}
y_min = min(v[1] for v in boxes.values())
y_max = max(v[1] + v[3] for v in boxes.values())
x_max = max(v[0] + v[2] for v in boxes.values())

fig = plt.figure(figsize=(18.0, 13.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1.10, 0.90], hspace=0.26, wspace=0.16)

# ======================= DECISION 1 : U_C ==================================
ax1 = fig.add_subplot(gs[0, :])
ax1.set_xlim(-2, x_max + 44)
ax1.set_ylim(y_max + 4, y_min - 4)   # inverted: board coordinates, y down
ax1.set_aspect("equal")
ax1.axis("off")
ax1.set_title("DECISION 1 — U_C (the second LoRa2021): fit it, or leave it out?\n"
              "Both modules sit on the same SPI1 bus. U3's four control lines reach the ESP32 — "
              "U_C's four reach nothing at all.",
              fontsize=12.5, fontweight="bold", pad=12)

for ref, col, lbl in (("U3", "#1e8449", "U3\nLoRa2021\nWIRED"),
                      ("U_C", "#b03a2e", "U_C\nLoRa2021\nDEAD"),
                      ("U1", "#1f4e79", "U1\nESP32-S3\nWROOM-1U")):
    x, y, w, h = boxes[ref]
    ax1.add_patch(Rectangle((x, y), w, h, facecolor=col, alpha=0.12,
                             edgecolor=col, linewidth=2.2, zorder=1))
    # Name at the BOTTOM of the box: pad labels sit on the side edges, so a centred label
    # collided with "14 RESET_N" (vision flagged it twice).
    ax1.text(x + w / 2, y + h - 1.6, lbl, ha="center", va="bottom", fontsize=9.4,
             fontweight="bold", color=col, zorder=3, linespacing=1.45)

# control pads, labelled to the OUTSIDE so they cannot collide with each other
# U3's pads sit on the module EDGE, so a label drawn outward runs into the neighbouring module.
# Always draw the label INWARD (toward the module centre) so it cannot cross the boundary.
u3cx = boxes["U3"][0] + boxes["U3"][2] / 2
for num, (x, y, net) in sorted(u3_ctrl.items()):
    ax1.add_patch(Circle((x, y), 1.0, facecolor="#1e8449", edgecolor="white", lw=1.4, zorder=5))
    inward = 2.2 if x < u3cx else -2.2
    ax1.text(x + inward, y, f"{num} {net.replace('/U3_', '')}", fontsize=7.4, color="#1e8449",
             ha="left" if inward > 0 else "right", va="center", fontweight="bold", zorder=6)

uc_cx = boxes["U_C"][0] + boxes["U_C"][2] / 2
for num, (x, y, net) in sorted(uc_ctrl.items()):
    ax1.add_patch(Circle((x, y), 1.0, facecolor="#b03a2e", edgecolor="white", lw=1.4, zorder=5))
    inward = 2.2 if x < uc_cx else -2.2
    ax1.text(x + inward, y, f"{num} {net.replace('/U_C_', '')}", fontsize=7.4, color="#b03a2e",
             ha="left" if inward > 0 else "right", va="center", fontweight="bold", zorder=6)
    # dotted stub ending in a cross = goes nowhere
    ax1.plot([x, x], [y, y + 5.0], linestyle=":", color="#b03a2e", lw=1.4, zorder=2)
    ax1.plot(x, y + 5.0, marker="X", ms=8, color="#b03a2e", zorder=6, markeredgecolor="white")

# Note placed STRICTLY right of every measured module box. U_C's right edge is 54.6 and U1's is
# 29.6, so x >= 56 is guaranteed empty. An earlier placement at x=34 sat inside U_C and vision
# caught it -- the lesson is to derive the position from the boxes, not eyeball it.
NOTE_X = x_max + 2.0
ax1.text(NOTE_X, y_min + 1.5,
         "GPIO BUDGET  (enumerated from this board)\n"
         f"  free U1 pads : {', '.join(free_pads)}\n"
         "  unusable     : 16 & 26 input-only,\n"
         "                 28/29/30 octal-PSRAM (N8R8)\n"
         f"  USABLE       : {', '.join(usable)}   →  {len(usable)} pins\n"
         "  U_C needs    : 4 signals\n"
         "\n"
         f"⇒ {len(usable)} < 4.  U_C cannot be fully wired on\n"
         "   this revision without giving up a signal.",
         fontsize=9.0, color="#4d5656", va="top",
         bbox=dict(fc="#fef9e7", ec="#b7950b", lw=1.3, pad=7), zorder=9)

# ======================= DECISION 2 : the wires ============================
ax2 = fig.add_subplot(gs[1, 0])
x1b, y1b, w1b, h1b = box(u1)
x2b, y2b, w2b, h2b = box(jp)
ax2.set_xlim(min(x1b, x2b) - 6, max(x1b + w1b, x2b + w2b) + 6)
ax2.set_ylim(max(y1b + h1b, y2b + h2b) + 12, min(y1b, y2b) - 4)
ax2.set_aspect("equal")
ax2.axis("off")
ax2.set_title("DECISION 2 — the two bodge wires, at true coordinates\n"
              "USB D+/D− already reach the header. EN and IO0 do not.",
              fontsize=11.5, fontweight="bold", pad=10)

for ref, col, lbl in (("U1", "#1f4e79", "U1\nESP32-S3"), ("J_PROG", "#7d3c98", "J_PROG\n1×6  2.54 mm")):
    x, y, w, h = box(fp_ref[ref])
    ax2.add_patch(Rectangle((x, y), w, h, facecolor=col, alpha=0.10, edgecolor=col, lw=2.0, zorder=1))
    # Anchor the module label at the TOP of its box, clear of the dashed wire paths that cross
    # the middle (vision flagged the EN wire crossing "ESP32-S3").
    ax2.text(x + w / 2, y + 2.6, lbl, ha="center", va="top", fontsize=8.8,
             fontweight="bold", color=col, zorder=3, linespacing=1.4)

pads = {}
for p in u1.Pads():
    if p.GetNumber() in ("3", "13", "14", "27"):
        pos = p.GetPosition()
        pads[("U1", p.GetNumber())] = (mm(pos.x), mm(pos.y), p.GetNetname())
for p in jp.Pads():
    pos = p.GetPosition()
    pads[("J_PROG", p.GetNumber())] = (mm(pos.x), mm(pos.y), p.GetNetname())

WIRED = {"13", "14"}
for num in ("13", "14", "3", "27"):
    x, y, net = pads[("U1", num)]
    ok = num in WIRED
    ax2.add_patch(Circle((x, y), 1.3, facecolor="#1e8449" if ok else "#b03a2e",
                         edgecolor="white", lw=1.3, zorder=5))
    ax2.text(x - 2.0, y, net, fontsize=7.6, ha="right", va="center",
             color="#1e8449" if ok else "#b03a2e", fontweight="bold", zorder=6)

# Wire labels go at the U1 END of each dash, left-aligned OUTSIDE the U1 box, so they cannot land
# on the J_PROG label or cross each other's dashes (vision flagged both).
for a, c, label, dy in ((("U1", "3"), ("J_PROG", "3"), "A — EN", -2.0),
                        (("U1", "27"), ("J_PROG", "6"), "B — IO0", 2.0)):
    xa, ya, _ = pads[a]
    xc, yc, _ = pads[c]
    ax2.add_patch(FancyArrowPatch((xa, ya), (xc, yc), arrowstyle="-", lw=2.2,
                                   color="#b03a2e", linestyle=(0, (5, 3)), zorder=4))
    ax2.text(xa + 2.0, ya + dy, label, fontsize=8.0, color="#b03a2e",
             fontweight="bold", style="italic", ha="left", va="center", zorder=6)

ax2.text(min(x1b, x2b) - 4, max(y1b + h1b, y2b + h2b) + 9,
         "green = copper exists (19 and 46 tracks)\nred dashed = the two wires a human adds",
         fontsize=8.2, color="#4d5656", va="top",
         bbox=dict(fc="white", ec="#bdc3c7", lw=1.0, pad=4), zorder=8)

# ======================= option table ======================================
ax3 = fig.add_subplot(gs[1, 1])
ax3.axis("off")
ax3.set_xlim(0, 1)
ax3.set_ylim(0, 1)

hdr = ["", "U_C", "boards with\nboth wires", "what you can do"]
for j, h in enumerate(hdr):
    ax3.text(0.02 + j * 0.25, 1.00, h, fontsize=8.2, fontweight="bold", color="#555",
             va="top", transform=ax3.transAxes)

# U_C is omitted in EVERY option -- Decision 1 proves it cannot be commanded on v10 (2 usable
# GPIOs for 4 signals). Offering "U_C fitted" as a purchasable choice contradicted that, so the
# only real variable is how many boards get the two programming wires.
rows = [
    ("1  all ten wired", "omitted", "10/10", "flash + reflash, no bench work"),
    ("2  wire four only", "omitted", "4/10", "4 certain, 6 need a wire to reflash"),
    ("3  no wires", "omitted", "0/10", "first flash only; reflash = bench"),
]
for i, r in enumerate(rows):
    y = 0.91 - i * 0.095
    for j, cell in enumerate(r):
        ax3.text(0.02 + j * 0.25, y, cell, fontsize=8.3, va="top",
                 color="#b03a2e" if j == 0 else "#1c2833", transform=ax3.transAxes,
                 fontweight="bold" if j == 0 else "normal")

ax3.text(0.02, 0.62,
         "RECOMMENDED — option 1, all ten wired.\n"
         "U_C is omitted in every option: it cannot be commanded\n"
         "on this revision (2 usable GPIOs, 4 signals needed).\n\n"
         "You asked for boards ready to fly. A wire on a 2.54 mm\n"
         "through-hole pad takes ~20 s, so ten boards is under ten\n"
         "minutes total. It removes the only remaining case where a\n"
         "board must come off the airframe to be reflashed.\n\n"
         "2 earns its keep only if you expect heavy reflashing during\n"
         "bring-up — then 4 sacrificial boards protect the 6 clean\n"
         "ones. 3 saves nothing now and costs the most later.",
         fontsize=8.7, color="#1c2833", va="top", transform=ax3.transAxes,
         bbox=dict(fc="#eafaf1", ec="#1e8449", lw=1.4, pad=8))

fig.suptitle("Two decisions before the JLCPCB order — drawn from board b90bf629", fontsize=13.5)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print("wrote", OUT)
print("\nU_C control pads:", {k: v[2] for k, v in sorted(uc_ctrl.items())})
print("free U1 pads   :", free_pads)
print("usable GPIOs   :", usable, f"({len(usable)}) for 4 needed")
print("measured boxes :", {k: tuple(round(x, 1) for x in v) for k, v in boxes.items()})
