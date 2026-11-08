"""Pre-order visual: via geometry before/after, and the drill table JLCPCB will see."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7.5))

# ---- left: the three vias, before vs after, to scale ----
ax1.set_title("via annulus: 0.600 land, drill before vs after\n"
              "JLCPCB minimum via annular ring = 0.130 mm", fontsize=12, fontweight="bold")

def draw_via(ax, cx, cy, land, drill, colour, label, ann_ok):
    ax.add_patch(Circle((cx, cy), land / 2, facecolor="#aed6f1" if ann_ok else "#f5b7b1",
                        edgecolor="#1f618d" if ann_ok else "#c0392b", lw=1.8, zorder=2))
    ax.add_patch(Circle((cx, cy), drill / 2, facecolor="white",
                        edgecolor="#1f618d" if ann_ok else "#c0392b", lw=1.4, zorder=3))
    ax.text(cx, cy - 0.46, label, ha="center", va="top", fontsize=8.6,
            color="#1e8449" if ann_ok else "#c0392b", fontweight="bold")

draw_via(ax1, 0.0, 0.0, 0.6, 0.36, "#f5b7b1", "0.360 drill\nannulus 0.120\nBELOW 0.13", False)
draw_via(ax1, 1.0, 0.0, 0.6, 0.30, "#aed6f1", "0.300 drill\nannulus 0.150\nOK", True)

# what a fab rounding would do
draw_via(ax1, 2.0, 0.0, 0.6, 0.40, "#f5b7b1", "0.400 (rounded)\nannulus 0.100\nWORSE", False)

ax1.annotate("", xy=(0.5, 0.0), xytext=(0.15, 0.0),
             arrowprops=dict(arrowstyle="->", color="#7f8c8d", lw=1.6, ls="--"))
ax1.text(0.5, 0.42, "fixed", ha="center", fontsize=8.5, color="#7f8c8d", style="italic")
ax1.text(2.0, 0.42, "avoided", ha="center", fontsize=8.5, color="#7f8c8d", style="italic")
ax1.set_xlim(-0.55, 2.55)
ax1.set_ylim(-0.62, 0.62)
ax1.set_aspect("equal")
ax1.axis("off")

# ---- right: drill table ----
ax2.set_title("drill table as it will reach JLCPCB\n"
              "4 tools, all stocked sizes", fontsize=12, fontweight="bold")
ax2.axis("off")

rows = [
    ("0.200 mm", "12", "U1.41 thermal pad"),
    ("0.300 mm", "161", "every via on the board"),
    ("1.000 mm", "15", "PTH component pins"),
    ("2.500 mm", "8", "mounting / large"),
    ("", "", ""),
    ("TOTAL", "196", "holes"),
]
y = 0.82
ax2.text(0.10, y + 0.10, "diameter", fontsize=9.5, fontweight="bold")
ax2.text(0.42, y + 0.10, "hits", fontsize=9.5, fontweight="bold")
ax2.text(0.55, y + 0.10, "use", fontsize=9.5, fontweight="bold")
for (d, n, use) in rows:
    if d == "":
        y -= 0.05
        continue
    bold = d == "TOTAL"
    ax2.text(0.10, y, d, fontsize=11 if bold else 10, fontweight="bold" if bold else "normal")
    ax2.text(0.42, y, n, fontsize=11 if bold else 10, fontweight="bold" if bold else "normal")
    ax2.text(0.55, y, use, fontsize=9, color="#5d6d7e")
    y -= 0.11

ax2.text(0.10, 0.16,
         "no 0.360 mm tool — removed\n"
         "all 161 vias 0.600 / 0.300, annulus 0.150\n"
         "every drill is a 0.05 mm step size",
         fontsize=9.5, color="#1e8449", fontweight="bold",
         bbox=dict(fc="#eafaf1", ec="#1e8449", lw=1.3, pad=6))

plt.tight_layout()
out = ("/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/"
       "bulk-route-20261107/PREORDER-via-and-drill.png")
plt.savefig(out, dpi=125, facecolor="white")
print("saved %s" % out)
