#!/usr/bin/env python3
"""render_board_cost.py -- cost per board vs order quantity, with the 5 costliest parts
resolved INDEPENDENTLY in the legend.

Operator's ask, verbatim: *"plot how the cost per board scales as the number of boards
produced increases with the cost of the 5 costliest parts resolved independently in that plot
with a legend so that we can see which part contributes to the board cost how much as a
function of the number of boards ordered."*

So the top-5 parts are drawn as their OWN bands, not lumped into "components". The other 9 are
summed into a single residual band. That is what makes the answer readable: two parts are
~95 % of the silicon cost and both are flat per board, while the fees are what fall.

Builds on the established pattern in this repo (model module + render module):
  model_board_cost.py    the numbers, single source of truth, LCSC prices fetched+cached
  render_board_cost.py   this file -- drawing only, no numbers invented here

Run: python3 docs/analysis/bulk-route-20261107/render_board_cost.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import model_board_cost as M

import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
OUT = _os.path.join(HERE, "assets", "board-cost-scaling.png")

QS = np.array([1, 2, 3, 5, 10, 15, 20, 30, 50, 75, 100])

px = M.prices()
missing = [c for c, v in px.items() if v is None]
if missing:
    raise SystemExit(f"refusing to draw with missing prices: {missing}")

# per-board component cost, sorted, top 5 get their own band
lines = []
for line, des, qty, code in M.BOM:
    lines.append(dict(line=line, code=code, qty=qty, unit=px[code],
                      per_board=px[code] * qty))
lines.sort(key=lambda r: -r["per_board"])
TOP = lines[:5]
REST = lines[5:]
rest_per_board = sum(r["per_board"] for r in REST)

joints = M.JOINTS_PER_BOARD * M.JOINT_FEE
eng = M.ENGINEERING_FEE
ext = len(M.EXTENDED) * M.EXTENDED_FEE

rows = []
for q in QS:
    bare = M.bare_pcb(q)
    fixed = eng + ext + joints * q          # per ORDER
    per_board = (sum(r["per_board"] for r in TOP) + rest_per_board) + bare / q + fixed / q
    rows.append(dict(q=q, per_board=per_board, bare=bare / q, fixed=fixed / q))

fig = plt.figure(figsize=(15.5, 10.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1.12, 1.0], hspace=0.62, wspace=0.24)
ax = fig.add_subplot(gs[0, :])
ax2 = fig.add_subplot(gs[1, 0])
ax3 = fig.add_subplot(gs[1, 1])

# --- panel A: stacked bands, top-5 resolved independently
palette = ["#1f4e79", "#2e75b6", "#e07b39", "#2e8b57", "#8e44ad"]
bottom = np.zeros(len(QS))
for i, r in enumerate(TOP):
    vals = np.full(len(QS), r["per_board"])
    ax.bar(QS, vals, bottom=bottom, width=[q * 0.055 + 0.7 for q in QS],
           color=palette[i], edgecolor="white", linewidth=0.6,
           label=f"{r['line']}  (${r['per_board']:.3f}/board)")
    bottom += vals

rest_vals = np.full(len(QS), rest_per_board)
ax.bar(QS, rest_vals, bottom=bottom, color="#b0b0b0", edgecolor="white", linewidth=0.6,
       label=f"other 9 parts  (${rest_per_board:.3f}/board)")
bottom += rest_vals

fee_vals = np.array([r["fixed"] for r in rows])
ax.bar(QS, fee_vals, bottom=bottom, color="#f4b6a6", edgecolor="#8c4a3a",
       linewidth=0.9, hatch="//",
       label="fees + bare PCB, amortised  (falls with qty)")
bottom += fee_vals

ax.set_xlabel("boards ordered")
ax.set_ylabel("cost per board (USD)")
ax.set_title("A  Cost per board -- the 5 costliest parts resolved separately\n"
             "component cost is FLAT per board; only the amortised fees fall")
ax.legend(loc="upper right", fontsize=7.6, framealpha=0.95)
ax.set_xticks(QS)
ax.grid(axis="y", alpha=0.25)
ax.set_ylim(0, max(bottom) * 1.18)

# annotate the collapse
ax.annotate(f"${rows[0]['per_board']:.2f}", (QS[0], rows[0]["per_board"]),
            textcoords="offset points", xytext=(6, 10), fontsize=9, fontweight="bold")
ax.annotate(f"${rows[-1]['per_board']:.2f}", (QS[-1], rows[-1]["per_board"]),
            textcoords="offset points", xytext=(-24, 10), fontsize=9, fontweight="bold")

# --- panel B: contribution share as a function of quantity
total_comp = sum(r["per_board"] for r in TOP) + rest_per_board
share_fee = [x["fixed"] / x["per_board"] * 100 for x in rows]

for i, r in enumerate(TOP):
    # v1 BUG: this plotted a CONSTANT (r["per_board"]/rows[-1]["per_board"]) on an axis
    # labelled "% of per-board cost". A fixed dollar amount must become a LARGER share as the
    # denominator falls, so the lines have to RISE. vision_analyze caught the contradiction.
    ax2.plot(QS, [r["per_board"] / x["per_board"] * 100 for x in rows],
             marker="o", ms=4, color=palette[i], linewidth=1.8,
             label=f"{r['line'][:26]}  ${r['per_board']:.3f}")
ax2.plot(QS, [(x["fixed"] + x["bare"]) / x["per_board"] * 100 for x in rows],
         marker="s", ms=5, color="#c0392b", linewidth=2.4,
         label="fees + bare PCB (share)")

ax2.set_xlabel("boards ordered")
ax2.set_ylabel("% of per-board cost")
ax2.set_title("B  Who contributes what, as quantity changes\n"
              "the fee share collapses; the two big parts take over")
ax2.set_xscale("log")
ax2.set_xticks(QS)
ax2.set_xticklabels([str(q) for q in QS])
ax2.legend(fontsize=6.6, loc="upper center", bbox_to_anchor=(0.5, -0.20),
           ncol=2, framealpha=1.0, borderaxespad=0.0,
           title="share of per-board cost", title_fontsize=6.8)
ax2.set_ylim(0, 100)

# --- panel C: component cost ALONE, its own linear scale.
# This exists because panel A cannot show a part worth $0.026 next to a $49 one-board bar.
BAR_Q = [1, 10, 100]
labels = [r["line"][:20] for r in TOP] + ["other 9"]
xx = np.arange(len(labels))
w = 0.26
for j, q in enumerate(BAR_Q):
    vals = [r["per_board"] for r in TOP] + [rest_per_board]
    ax3.bar(xx + (j - 1) * w, vals, width=w, label=f"qty {q}",
            color=["#4a6fa5", "#7fa8d0", "#c3d9ec"][j], edgecolor="white")
ax3.set_xticks(xx)
ax3.set_xticklabels(labels, rotation=30, ha="right", fontsize=7.2)
ax3.set_ylabel("USD per board")
ax3.set_title("C   Component cost alone — identical at every quantity\n"
              "so the five parts are readable on their own scale", fontsize=10)
ax3.legend(fontsize=8, title="order size", title_fontsize=8)
ax3.grid(axis="y", alpha=0.25)
for i_, r_ in enumerate(TOP + [dict(line="other 9", per_board=rest_per_board)]):
    ax3.annotate(f"${r_['per_board']:.3f}", (i_, r_["per_board"]),
                 textcoords="offset points", xytext=(0, 4),
                 ha="center", fontsize=6.8, color="#1f4e79")

fig.suptitle("Balloon hub v10 -- per-board cost vs order quantity (JLC components + assembly "
             "+ 4-layer PCB)", fontsize=11)
# gridspec handles spacing; tight_layout conflicts with add_gridspec

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print(f"wrote {OUT}")

print("\ncomponent cost per board (measured LCSC prices):")
for i, r in enumerate(TOP):
    print(f"  #{i+1} ${r['per_board']:7.4f}  {r['line']:32s} {r['code']}")
print(f"      ${rest_per_board:7.4f}  other {len(REST)} parts")
print(f"      ${sum(r['per_board'] for r in TOP) + rest_per_board:7.4f}  TOTAL components")

print("\ncost per board:")
for r in rows:
    print(f"  qty {r['q']:3d}  ${r['per_board']:7.2f}   (fees+bare ${r['bare'] + r['fixed']:5.2f})")
