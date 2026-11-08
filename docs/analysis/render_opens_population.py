"""Visual: the 5 REAL opens against the population decision, and the corrected width arithmetic."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

fig = plt.figure(figsize=(15.5, 8.6))
gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1], wspace=0.22)

# ---- LEFT: the 5 opens vs population ----
ax = fig.add_subplot(gs[0, 0])
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")
ax.set_title("The 5 REAL copper opens, against what this build actually fits",
             fontsize=12.5, fontweight="bold", loc="left", pad=12)

rows = [
    ("/EN",         "U1.3 → J_PROG.3",            True,  "both parts fitted"),
    ("/SPI2_SCK",   "U1.4 → U2.12",               False, "U2 is DNP — net has only these 2 pads"),
    ("/F33_VSENSE", "U1.21 → B.Cu track",         True,  "U1 fitted"),
    ("/VSCAP",      "zone → C_CAP1.1 PTH",        False, "C_CAP1 is DNP (supercap, D4)"),
    ("/W2_SOLAR_N", "B.Cu track → F.Cu track",    None,  "already EXCLUDED: two-face, completes in assembly"),
]

y = 8.6
for net, endpoints, functional, note in rows:
    if functional is None:          # neither matters nor cannot-matter: it is not an open
        colour, bg, badge = "#7d6608", "#fef9e7", "excluded"
    elif functional:
        colour, bg, badge = "#1e8449", "#eafaf1", "matters"
    else:
        colour, bg, badge = "#c0392b", "#fdedec", "cannot\nmatter"
    ax.add_patch(FancyBboxPatch((0.15, y - 1.22), 9.7, 1.16,
                                boxstyle="round,pad=0.04", fc=bg, ec=colour, lw=1.6))
    ax.text(0.42, y - 0.30, net, fontsize=10.6, fontweight="bold", color="#1c2833",
            family="monospace")
    ax.text(0.42, y - 0.70, endpoints, fontsize=9.0, color="#34495e", family="monospace")
    ax.text(0.42, y - 1.05, note, fontsize=8.5, color=colour, style="italic")
    ax.text(9.45, y - 0.55, badge,
            fontsize=8.8, color=colour, fontweight="bold", ha="right", va="center")
    y -= 1.42

ax.text(0.3, 0.55,
        "The gate still reports REAL 5 and must — this column is a different question:\n"
        "does the open join two things this build actually fits?",
        fontsize=9.0, color="#566573", style="italic")

# ---- RIGHT: corrected width arithmetic ----
ax2 = fig.add_subplot(gs[0, 1])
ax2.set_title("How wide a track fits in the gap\n(W ≤ G − 2C, not G − C)", fontsize=12.5,
              fontweight="bold", loc="left", pad=12)
ax2.axis("off")

data = [("/EN  vs /SPI2_MISO", 0.350, -0.050),
        ("/EN  vs +3V3", 0.720, 0.320),
        ("/SPI2_SCK vs /SPI2_MOSI", 0.200, -0.200),
        ("/F33_VSENSE vs /U3_CS_N", 0.250, -0.150),
        ("/VSCAP vs /SCAP_MID", 0.282, -0.118)]

x0, w = 0.06, 0.50
ytop = 0.86
ax2.text(x0, ytop + 0.10, "gap", fontsize=8.8, fontweight="bold")
ax2.text(x0 + w + 0.02, ytop + 0.10, "max width at S1", fontsize=8.8, fontweight="bold")

y = ytop
for label, gap, maxw in data:
    ok = maxw >= 0.200
    ax2.text(x0, y, label, fontsize=8.6, family="monospace", color="#1c2833")
    # bar scaled: gap in mm, 0.9 mm full width
    ax2.add_patch(Rectangle((x0, y - 0.075), w * (gap / 0.9), 0.050,
                            fc="#d5dbdb", ec="none"))
    ax2.text(x0 + w * (gap / 0.9) + 0.012, y - 0.045, "%.3f" % gap, fontsize=8.2, color="#5d6d7e")
    col = "#1e8449" if ok else "#c0392b"
    ax2.text(x0 + w + 0.02, y, "%+.3f %s" % (maxw, "FITS" if ok else "no"), fontsize=8.8,
             color=col, fontweight="bold", family="monospace")
    y -= 0.115

ax2.text(0.06, 0.20,
         "Two clearances, not one.\n"
         "G ≥ C + W + C\n"
         "S1:  W ≤ G − 0.400     fab: W ≤ G − 0.180",
         fontsize=9.4, color="#1c2833", family="monospace",
         bbox=dict(fc="#fef9e7", ec="#b7950b", lw=1.3, pad=7))
ax2.text(0.06, 0.04,
         "I used G − C and G − (C + W) before.\nBoth understate by exactly one C.",
         fontsize=8.4, color="#7b241c", style="italic")

plt.tight_layout()
out = ("/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/"
       "bulk-route-20261107/OPENS-vs-POPULATION.png")
plt.savefig(out, dpi=140, facecolor="white", bbox_inches="tight")
print("saved %s" % out)
