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
missing = [c for c, v in px.items() if not v]
if missing:
    raise SystemExit(f"refusing to draw with missing price LADDERS: {missing}")


def split_at(q):
    """Per-board component lines at order size q, using the real LCSC ladder."""
    lines = []
    for line, des, qty, code in M.BOM:
        unit = M.unit_price(px[code], qty * q)
        lines.append(dict(line=line, code=code, qty=qty, unit=unit, per_board=unit * qty))
    lines.sort(key=lambda r: -r["per_board"])
    return lines


# Top-5 is defined at the SMALLEST quantity (worst case) so the legend does not reorder between
# points; the bands then move as the ladders drop.
TOP_NAMES = [r["line"] for r in split_at(1)[:5]]

joints = M.JOINTS_PER_BOARD * M.JOINT_FEE
eng = M.ENGINEERING_FEE
ext = len(M.EXTENDED) * M.EXTENDED_FEE

rows = []
for q in QS:
    all_lines = split_at(q)
    top = {r["line"]: r["per_board"] for r in all_lines if r["line"] in TOP_NAMES}
    rest_per_board = sum(r["per_board"] for r in all_lines if r["line"] not in TOP_NAMES)
    comp = sum(r["per_board"] for r in all_lines)
    bare = M.bare_pcb(q)
    fixed = eng + ext + joints * q          # per ORDER
    rows.append(dict(q=q, top=top, rest=rest_per_board, comp=comp,
                     bare=bare / q, fixed=fixed / q,
                     per_board=comp + bare / q + fixed / q))

fig = plt.figure(figsize=(15.5, 10.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1.12, 1.0], hspace=0.62, wspace=0.24)
ax = fig.add_subplot(gs[0, :])
ax2 = fig.add_subplot(gs[1, 0])
ax3 = fig.add_subplot(gs[1, 1])

# --- panel A: stacked bands, top-5 resolved independently
palette = ["#1f4e79", "#2e75b6", "#e07b39", "#2e8b57", "#8e44ad"]
bottom = np.zeros(len(QS))
widths = [q * 0.052 + 0.72 for q in QS]
for i, name in enumerate(TOP_NAMES):
    vals = np.array([r["top"].get(name, 0.0) for r in rows])
    ax.bar(QS, vals, bottom=bottom, width=widths,
           color=palette[i], edgecolor="white", linewidth=0.6,
           label=f"{name[:30]}  (${vals[0]:.3f} -> ${vals[-1]:.3f}/board)")
    bottom += vals

rest_vals = np.array([r["rest"] for r in rows])
ax.bar(QS, rest_vals, bottom=bottom, color="#b0b0b0", edgecolor="white", linewidth=0.6,
       label=f"other {len(M.BOM) - 5} parts  (${rest_vals[0]:.3f}/board)")
bottom += rest_vals

fee_vals = np.array([r["fixed"] + r["bare"] for r in rows])
ax.bar(QS, fee_vals, bottom=bottom, color="#f4b6a6", edgecolor="#8c4a3a",
       linewidth=0.9, hatch="//",
       label="fees + bare PCB, amortised  (falls with qty)")
bottom += fee_vals

ax.set_xlabel("boards ordered")
ax.set_ylabel("cost per board (USD)")
ax.set_title("A  Cost per board -- the 5 costliest parts resolved separately\n"
             "components now fall too: LCSC's real quantity breaks are used, "
             "not one scraped price")
ax.legend(loc="upper right", fontsize=7.2, framealpha=0.95)
ax.set_xticks(QS)
ax.grid(axis="y", alpha=0.25)
ax.set_ylim(0, max(bottom) * 1.22)

# annotate the collapse
ax.annotate(f"${rows[0]['per_board']:.2f}", (QS[0], rows[0]["per_board"]),
            textcoords="offset points", xytext=(8, 10), fontsize=9.5, fontweight="bold")
ax.annotate(f"${rows[-1]['per_board']:.2f}", (QS[-1], rows[-1]["per_board"]),
            textcoords="offset points", xytext=(-30, 10), fontsize=9.5, fontweight="bold")

# --- panel B: contribution share as a function of quantity
for i, name in enumerate(TOP_NAMES):
    # A part's SHARE rises whenever its dollars fall more slowly than the per-board total. Plotting
    # a constant here was v1's bug (vision_analyze caught the contradiction with the axis label).
    ax2.plot(QS, [x["top"].get(name, 0.0) / x["per_board"] * 100 for x in rows],
             marker="o", ms=4, color=palette[i], linewidth=1.8,
             label=f"{name[:24]}")
ax2.plot(QS, [x["rest"] / x["per_board"] * 100 for x in rows],
         marker="^", ms=4, color="#7f8c8d", linewidth=1.5, linestyle="--",
         label=f"other {len(M.BOM) - 5}")
ax2.plot(QS, [(x["fixed"] + x["bare"]) / x["per_board"] * 100 for x in rows],
         marker="s", ms=5, color="#c0392b", linewidth=2.4,
         label="fees + bare PCB (share)")

ax2.set_xlabel("boards ordered (log)")
ax2.set_ylabel("% of per-board cost")
ax2.set_title("B  Who contributes what, as quantity changes\n"
              "the fee share collapses; the MCU takes over")
ax2.set_xscale("log")
ax2.set_xticks(QS)
ax2.set_xticklabels([str(q) for q in QS], fontsize=7.6)
ax2.legend(fontsize=6.6, loc="upper center", bbox_to_anchor=(0.5, -0.20),
           ncol=2, framealpha=1.0, borderaxespad=0.0,
           title="share of per-board cost", title_fontsize=6.8)
ax2.set_ylim(0, 100)

# --- panel C: the top-5 parts on their own linear scale, at three order sizes.
# Kept because panel A cannot show a part worth $0.02 next to a $7 bar. The point NOW is the
# quantity response: the same five bars at qty 1 / 10 / 100. The old caption claimed "identical at
# every quantity", which the real ladders disprove.
BAR_Q = [1, 10, 100]
labels = [n[:20] for n in TOP_NAMES] + [f"other {len(M.BOM) - 5}"]
xx = np.arange(len(labels))
w = 0.26
for j, q in enumerate(BAR_Q):
    all_lines = split_at(q)
    vals = [next((r["per_board"] for r in all_lines if r["line"] == n), 0.0)
            for n in TOP_NAMES]
    vals.append(sum(r["per_board"] for r in all_lines if r["line"] not in TOP_NAMES))
    ax3.bar(xx + (j - 1) * w, vals, width=w, label=f"qty {q}",
            color=["#4a6fa5", "#7fa8d0", "#c3d9ec"][j], edgecolor="white")
ax3.set_xticks(xx)
ax3.set_xticklabels(labels, rotation=30, ha="right", fontsize=7.2)
ax3.set_ylabel("USD per board")
ax3.set_title("C   The same five parts at three order sizes\n"
              "the bands in A are these bars sinking as the ladder steps down", fontsize=10)
ax3.legend(fontsize=8, title="order size", title_fontsize=8)
ax3.grid(axis="y", alpha=0.25)

fig.suptitle("Balloon hub v10 -- per-board cost vs order quantity (JLC components from live LCSC "
             "ladders + assembly + 4-layer PCB)", fontsize=11)
# gridspec handles spacing; tight_layout conflicts with add_gridspec

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print(f"wrote {OUT}")

print("\n=== the 5 costliest parts, at order size 1 ===")
for i, r in enumerate(split_at(1)[:5]):
    print(f"  #{i+1} ${r['per_board']:7.4f}  {r['line']:34s} "
          f"{r['qty']}x @ ${r['unit']:.4f}  {r['code']}")

print("\n=== cost per board ===")
print(f"  {'qty':>4}  {'total':>7}  {'components':>10}  {'fees+bare':>9}")
for r in rows:
    print(f"  {r['q']:4d}  ${r['per_board']:6.2f}  ${r['comp']:9.3f}  "
          f"${r['bare'] + r['fixed']:8.2f}")

print("\n=== hand-fit, EXCLUDED from the JLC total above ===")
hf = sum(q * est for _, _, q, _, est in M.HAND_FIT)
for line, des, q, note, est in M.HAND_FIT:
    print(f"  ${est * q:7.2f}  {line:24s} {q}x  {note}")
print(f"  ${hf:7.2f}  per board (APPROX where priced -- replace with vendor quotes)")
print(f"\n  full board cost at qty 1: ${rows[0]['per_board'] + hf:.2f} "
      f"(JLC ${rows[0]['per_board']:.2f} + hand-fit ${hf:.2f})")
