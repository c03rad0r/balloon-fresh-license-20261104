#!/usr/bin/env python3
"""render_board_cost_lines.py -- boards on the X axis, price on the Y axis, the 5 costliest parts
drawn as INDEPENDENT LINES (not stacked bands).

Why this exists alongside render_board_cost.py: the stacked bar chart answers "what is a board
worth" but not "how much does each part contribute, and how does that contribution move as I order
more". Lines answer that directly.

THREE PANELS, because one axis cannot show a $5.84 part and a $0.0012 part at once:
  A  per-board cost, all series            -- the shape of the answer
  B  total order cost, linear axes         -- what you actually pay
  C  the cheaper parts, own y-scale        -- their ladders, invisible in A

Price breaks are drawn with drawstyle="steps-post". A piecewise-constant price is a STAIR; drawing
it as a diagonal implies a linear discount LCSC does not give.

Same single source of truth: model_board_cost.py. No numbers invented here.

Run: python3 docs/analysis/bulk-route-20261107/render_board_cost_lines.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import model_board_cost as M

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "board-cost-lines.png")

QS = np.array([1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100])

px = M.prices()
missing = [c for c, v in px.items() if not v]
if missing:
    raise SystemExit(f"refusing to draw with missing ladders: {missing}")


def lines_at(q):
    """Per-board component lines at order size q, from the real ladder."""
    out = []
    for line, des, qty, code in M.BOM:
        unit = M.unit_price(px[code], qty * q)
        out.append(dict(line=line, code=code, qty=qty, unit=unit, per_board=unit * qty))
    out.sort(key=lambda r: -r["per_board"])
    return out


# Top-5 fixed at the 1-board case so the legend does not reorder between points.
TOP = [r["line"] for r in lines_at(1)[:5]]
CHEAP = TOP[2:]          # beyond U1 and U7 everything is under a dollar; panel C gives them room

per_board = {n: [] for n in TOP}
total_boards = {n: [] for n in TOP}
fee_per_board, total_per_board = [], []

for q in QS:
    all_lines = lines_at(q)
    for n in TOP:
        r = next((x for x in all_lines if x["line"] == n), None)
        pb = r["per_board"] if r else 0.0
        per_board[n].append(pb)
        total_boards[n].append(pb * q)
    comp = sum(x["per_board"] for x in all_lines)
    fee_per_board.append(M.bare_pcb(q) / q
                         + (M.ENGINEERING_FEE + len(M.EXTENDED) * M.EXTENDED_FEE
                            + M.JOINTS_PER_BOARD * M.JOINT_FEE * q) / q)
    total_per_board.append(comp * q + M.bare_pcb(q) + M.ENGINEERING_FEE
                           + len(M.EXTENDED) * M.EXTENDED_FEE
                           + M.JOINTS_PER_BOARD * M.JOINT_FEE * q)

palette = {"U1 ESP32-S3-WROOM-1U-N8R8": "#1f4e79",
           "U7 TPS7A0233DBVR": "#2e75b6",
           "100uF 1206 10V": "#e07b39",
           "SS24": "#2e8b57",
           "10uF 0402": "#8e44ad"}

fig = plt.figure(figsize=(17.0, 11.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.92], hspace=0.62, wspace=0.22)
ax1 = fig.add_subplot(gs[0, :])
ax2 = fig.add_subplot(gs[1, 0])
ax3 = fig.add_subplot(gs[1, 1])

# ---------- A: per-board cost, each part its own line ----------
for n in TOP:
    ax1.plot(QS, per_board[n], marker="o", ms=5, linewidth=2.3, drawstyle="steps-post",
             color=palette.get(n, "#555"), label=f"{n[:30]}")
ax1.plot(QS, fee_per_board, marker="s", ms=5, linewidth=2.6, linestyle=":",
         color="#c0392b", label="fees + bare PCB, amortised")

ax1.set_xlabel("boards ordered")
ax1.set_ylabel("cost per board (USD)")
ax1.set_title("A   Per-board cost vs quantity — the 5 costliest parts as separate lines\n"
              "steps, not slopes: LCSC discounts at exact quantities, so each part is flat "
              "between breaks and drops at one", fontsize=11.5, fontweight="bold")
ax1.set_xscale("log")
ax1.set_xticks(QS)
ax1.set_xticklabels([str(q) for q in QS], fontsize=8.8)
ax1.set_xlim(0.85, 135)
ax1.set_ylim(0, max(fee_per_board) * 1.16)
ax1.grid(alpha=0.28)
ax1.legend(fontsize=8.6, loc="upper right", framealpha=0.97)

ax1.annotate("the three cheaper parts sit\ndown here — see panel C",
             xy=(40, 0.30), xytext=(6.0, 13.0), fontsize=8.6, color="#5d6d7e", style="italic",
             arrowprops=dict(arrowstyle="->", color="#95a5a6", lw=1.1))
# The 100-board label must sit INSIDE the axes: with xlim 0.85..135 an offset to the right of the
# last point runs off the plot (vision flagged it). ha="right" pulls it back over its own point.
ax1.annotate(f"${total_per_board[0] / 1:.2f}/board", (1, fee_per_board[0]),
             textcoords="offset points", xytext=(11, 15), fontsize=9.6,
             fontweight="bold", color="#1c2833", ha="left")
ax1.annotate(f"${total_per_board[-1] / QS[-1]:.2f}/board", (QS[-1], fee_per_board[-1]),
             textcoords="offset points", xytext=(-11, 15), fontsize=9.6,
             fontweight="bold", color="#1c2833", ha="right")

# ---------- B: TOTAL order cost, linear axes, JLC only ----------
ax2.plot(QS, total_per_board, marker="D", ms=6, linewidth=2.9, color="#111111",
         label="TOTAL JLC order cost")
for n in TOP:
    # NO steps here. total_boards[n] = per_board(n) * n, so it grows with every extra board; a step
    # would draw a flat segment implying the total stops growing between price breaks.
    ax2.plot(QS, total_boards[n], marker="o", ms=4, linewidth=2.0,
             color=palette.get(n, "#555"), label=f"{n[:26]}")

ax2.set_xlabel("boards ordered")
ax2.set_ylabel("total order cost (USD)")
ax2.set_title("B   What the order actually costs\n"
              "linear axes — each part's slope is its marginal cost per board",
              fontsize=11, fontweight="bold")
ax2.set_xlim(0, 104)
ax2.set_ylim(0, max(total_per_board) * 1.16)
ax2.grid(alpha=0.28)
ax2.legend(fontsize=8.0, loc="upper left", framealpha=0.97)

hf = sum(q * est for _, _, q, _, est in M.HAND_FIT)
i5 = list(QS).index(5)
# BELOW the axes, not inside them. Two placements inside the plot each covered a different line
# (U1 at 0.30, the cheap traces at 0.03) -- with five series plus a total, panel B has no empty
# region large enough for a 3-line box. Outside the axes is the only honest placement.
ax2.text(0.5, -0.30,
         f"JLC only. Add ~${hf:.0f}/board for hand-fit parts (2x LoRa2021, 1x LoRa1280, "
         f"NiceRF, APPROX).\n"
         f"At 5 boards: ${total_per_board[i5]:.0f} + ${hf * 5:.0f} = "
         f"${total_per_board[i5] + hf * 5:.0f}",
         transform=ax2.transAxes, ha="center", va="top", fontsize=8.4,
         color="#4d5656", bbox=dict(fc="#fef9e7", ec="#b7950b", lw=1.1, pad=5))

# ---------- C: the cheaper parts on their own scale ----------
for n in CHEAP:
    ax3.plot(QS, per_board[n], marker="o", ms=5, linewidth=2.3, drawstyle="steps-post",
             color=palette.get(n, "#555"), label=f"{n[:24]}")
other = [sum(x["per_board"] for x in lines_at(q) if x["line"] not in TOP) for q in QS]
ax3.plot(QS, other, marker="^", ms=4, linewidth=1.8, linestyle="--", drawstyle="steps-post",
         color="#7f8c8d", label=f"other {len(M.BOM) - 5} parts")

ax3.set_xlabel("boards ordered")
ax3.set_ylabel("cost per board (USD)")
ax3.set_title("C   The cheaper three, on their own scale\n"
              "unreadable in A — but their ladders are real and step too",
              fontsize=11, fontweight="bold")
ax3.set_xscale("log")
ax3.set_xticks(QS)
ax3.set_xticklabels([str(q) for q in QS], fontsize=8.4)
ax3.set_xlim(0.85, 135)
ax3.set_ylim(0, max(max(per_board[n]) for n in CHEAP) * 1.32)
ax3.grid(alpha=0.28)
ax3.legend(fontsize=8.2, loc="upper right", framealpha=0.97)

fig.suptitle("Balloon hub v10 — board cost vs quantity ordered "
             "(LCSC real price ladders + JLC assembly + 4-layer PCB)", fontsize=13.5)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print("wrote %s" % OUT)

print("\n=== per-board cost (USD) ===")
print("%5s %10s   %s" % ("qty", "per board", "  ".join(n[:12] for n in TOP)))
for i, q in enumerate(QS):
    print("%5d %10.2f   %s" % (q, total_per_board[i] / q,
                               "  ".join("%12.4f" % per_board[n][i] for n in TOP)))

print("\n=== total order cost (USD) ===")
print("%5s %12s %12s" % ("qty", "JLC total", "+ hand-fit"))
for i, q in enumerate(QS):
    print("%5d %12.2f %12.2f" % (q, total_per_board[i], total_per_board[i] + hf * q))
