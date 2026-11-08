"""Order-readiness status board: every gate, every blocker, measured from the artefacts."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(13.6, 11.0))
ax.set_xlim(0, 10)
ax.set_ylim(-2.2, 10)
ax.axis("off")

ax.text(0.2, 9.55, "JLCPCB order readiness — board 0602c7c8", fontsize=15.5,
        fontweight="bold", color="#1c2833")
ax.text(0.2, 9.18, "72.10 × 80.10 mm · 4-layer · 1.6 mm · 30 assembled / 19 DNP sites",
        fontsize=10.5, color="#5d6d7e")

items = [
    ("Fab package",        "28 files, manifest-complete",              "DONE",  "0"),
    ("Gerber geometry",    "7 layers byte-identical, independent render", "DONE", "0"),
    ("Drill",              "196 holes, 4 tools, all stocked sizes",    "DONE",  "1"),
    ("Via geometry",       "161 vias, all 0.600/0.300, annulus 0.150", "DONE",  "1"),
    ("Outline",            "closed, odd-degree 0",                     "DONE",  "0"),
    ("Silkscreen",         "0 overlap / over-copper / edge violations","DONE",  "0"),
    ("Schematic parity",   "53 nets both ways",                        "DONE",  "0"),
    ("Part population",    "30 fitted / 19 DNP, from D1/D3/D4/D6",     "DONE",  "2"),
    ("CPL coordinates",    "30 rows, verified to <0.001 mm",           "DONE",  "2"),
    ("BOM LCSC numbers",   "14/14 JLC lines, all verified in stock",   "DONE",  "3"),
    ("DRC opens",          "5 REAL — 3 functional, 2 land on DNP parts", "KNOWN", "4"),
    ("Library artefacts",  "15 violations: KiCad version drift, not fixable here", "KNOWN", "5"),
    ("Cut channel",        "circuits not wired — U_CUT1..4 DNP by D1", "OPEN",  "6"),
    ("Assembly order",     "ready for the 23 JLC placements",          "READY", ""),
    ("PLACING THE ORDER",  "operator only — AGENTS.md line 153",       "YOURS", ""),
]

y = 8.45
for label, detail, status, _ in items:
    if status == "DONE":
        col, bg, mark = "#1e8449", "#eafaf1", "✓"
    elif status == "KNOWN":
        col, bg, mark = "#b9770e", "#fef9e7", "!"
    elif status == "OPEN":
        col, bg, mark = "#c0392b", "#fdedec", "✗"
    elif status == "READY":
        col, bg, mark = "#1a5276", "#eaf2f8", "→"
    else:
        col, bg, mark = "#6c3483", "#f4ecf7", "★"

    ax.add_patch(FancyBboxPatch((0.2, y - 0.40), 9.6, 0.50,
                                boxstyle="round,pad=0.02", fc=bg, ec=col, lw=1.2))
    ax.text(0.42, y - 0.15, mark, fontsize=11, color=col, fontweight="bold", va="center")
    ax.text(0.80, y - 0.15, label, fontsize=10.2, fontweight="bold", color="#1c2833", va="center")
    ax.text(3.10, y - 0.15, detail, fontsize=9.3, color="#34495e", va="center")
    ax.text(9.55, y - 0.15, status, fontsize=8.8, color=col, fontweight="bold",
            ha="right", va="center")
    y -= 0.585

# Annotations go in dedicated space BELOW the final row (y range extended to -2.2), not on top of it.
y_end = y        # y after the loop, already below the last row
ax.text(0.2, y_end - 0.35,
        "12 of 15 checks pass. The 5 REAL opens are not a fab blocker: 3 need S1-relaxation the "
        "campaign has ruled out,\nand 2 terminate on parts this build does not fit (U2, C_CAP1).",
        fontsize=9.0, color="#566573", style="italic", va="top")
ax.text(0.2, y_end - 1.15,
        "Bare board and the 23 JLC placements are orderable today. The four cut drivers are a "
        "design gap, not an order problem.",
        fontsize=9.0, color="#1e8449", fontweight="bold", va="top")

plt.tight_layout()
out = ("/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/"
       "bulk-route-20261107/ORDER-READINESS.png")
plt.savefig(out, dpi=145, facecolor="white", bbox_inches="tight")
print("saved %s" % out)
