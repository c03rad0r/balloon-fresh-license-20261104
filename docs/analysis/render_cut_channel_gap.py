"""Visual: what a cut channel has vs what the board carries."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, (axA, axB) = plt.subplots(1, 2, figsize=(18, 8))

def box(ax, x, y, w, h, label, present, note=""):
    fc = "#d5f5e3" if present else "#fadbd8"
    ec = "#1e8449" if present else "#c0392b"
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                                facecolor=fc, edgecolor=ec, lw=2.2))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=9.5, fontweight="bold", color="#1b2631")
    if note:
        ax.text(x + w / 2, y - 0.09, note, ha="center", va="top", fontsize=7.8,
                color=ec, style="italic")

def arrow(ax, a, c, present):
    ax.add_patch(FancyArrowPatch(a, c, arrowstyle="-|>", mutation_scale=15,
                                 color="#1e8449" if present else "#c0392b",
                                 lw=2.2 if present else 1.6,
                                 linestyle="-" if present else (0, (4, 3))))

# ---- A: ADR-051 requirement
axA.set_title("ADR-051 §2.5  —  what a cut channel MUST be", fontsize=12.5, fontweight="bold")
box(axA, 0.06, 0.62, 0.30, 0.16, "VSCAP\n(raw supercap)", True)
box(axA, 0.06, 0.20, 0.30, 0.16, "GND", True)
box(axA, 0.44, 0.40, 0.26, 0.18, "LATCHED\nDRIVER\n+ arming gate", True)
box(axA, 0.76, 0.62, 0.20, 0.16, "NICHROME\n(cut wire)", True)
box(axA, 0.76, 0.20, 0.20, 0.16, "CUT_SENSE", True)
box(axA, 0.44, 0.06, 0.26, 0.13, "MCU gate drive", True)
arrow(axA, (0.36, 0.70), (0.44, 0.52), True)
arrow(axA, (0.36, 0.28), (0.44, 0.44), True)
arrow(axA, (0.70, 0.52), (0.76, 0.68), True)
arrow(axA, (0.76, 0.28), (0.70, 0.42), True)
arrow(axA, (0.57, 0.19), (0.57, 0.40), True)
axA.text(0.5, 0.93, "6 requirements — one irreversible, energy-budgeted firing path",
         ha="center", fontsize=9, style="italic")

# ---- B: what the board carries
axB.set_title("board 322ade1e  —  what is actually wired", fontsize=12.5, fontweight="bold")
box(axB, 0.06, 0.62, 0.30, 0.16, "VSCAP\npad 1", True)
box(axB, 0.06, 0.20, 0.30, 0.16, "GND\npad 2", True)
box(axB, 0.44, 0.40, 0.26, 0.18, "SOT-23-6\npads 4,5,6\nNO NET", False)
box(axB, 0.76, 0.62, 0.20, 0.16, "NICHROME", False, "no net exists")
box(axB, 0.76, 0.20, 0.20, 0.16, "CUT_SENSE\npad 3", True)
box(axB, 0.44, 0.06, 0.26, 0.13, "MCU gate drive", False, "no net exists")
arrow(axB, (0.36, 0.70), (0.44, 0.52), True)
arrow(axB, (0.36, 0.28), (0.44, 0.44), True)
arrow(axB, (0.70, 0.52), (0.76, 0.68), False)
arrow(axB, (0.76, 0.28), (0.70, 0.42), True)
arrow(axB, (0.57, 0.19), (0.57, 0.40), False)
axB.text(0.5, 0.93, "3 of 6 present — the SENSE half only. Nothing here can fire a cutter.",
         ha="center", fontsize=9, style="italic", color="#c0392b", fontweight="bold")

for ax in (axA, axB):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

plt.tight_layout()
out = ("/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/"
       "bulk-route-20261107/DECISION-cut-channel-gap.png")
plt.savefig(out, dpi=125, facecolor="white")
print("saved %s" % out)
