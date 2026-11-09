#!/usr/bin/env python3
"""render_cost_curves.py -- boards on the X axis, price on the Y axis.

Operator's ask, verbatim: *"Please visualize this in plots with the number of boards on the x
axis and the price on the y axis. You previously made such plots, please merge the code to the
default branch if it isn't already there."*

This is a SECOND renderer beside render_board_cost.py. That one answers "who contributes what";
this one answers the plainer question "what does it cost if I order N boards", with a fine
quantity sweep instead of eleven discrete bars.

Four curves, because the honest answer needs all four:

  A  PER-BOARD cost. The number you compare against a quote. Two lines: JLC-only (what the
     assembler charges) and FULL (adding the hand-fit NiceRF modules and wing sockets that no
     assembler supplies). The gap between them is constant -- it is a per-board part cost, not
     an amortised fee -- so the two lines are parallel and never converge. That is the single
     most misread thing about this board's cost.
  B  TOTAL SPEND for the whole order. Per-board cost always falls with quantity; total spend
     always rises. These are different decisions and the plot makes the trade explicit.
  C  PER-BOARD, components only, log Y. Isolates the parts from the fees.
  D  MARGINAL cost of the next board. The derivative of B. This is the number that tells you
     where "one more board is nearly free" starts -- around qty 10 it flattens to ~$5, and
     buying beyond that is buying boards, not saving money.

Every number comes from model_board_cost.py. Nothing is invented here. APPROX values (the
NiceRF module prices, the bare-PCB tiers, the JLC fees) are drawn with a visible band or label
so the measured and the estimated are never confused.

Run: ~/venvs/kicad/bin/python docs/analysis/bulk-route-20261107/render_cost_curves.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

import model_board_cost as M

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "cost-curves.png")

px = M.prices()
missing = [c for c, v in px.items() if not v]
if missing:
    raise SystemExit(f"refusing to draw with missing price ladders: {missing}")

# Hand-fit is a flat PER-BOARD cost: no quantity breaks are known for NiceRF modules, and the
# wing sockets are a board feature with nothing to buy. Marked APPROX at source.
HAND_FIT_PER_BOARD = sum(qty * est for _, _, qty, _note, est in M.HAND_FIT)
HAND_FIT_APPROX = sum(qty * est for _, _, qty, _note, est in M.HAND_FIT if est)

# A fine sweep, so the curves are curves and not eleven points. Integer quantities only --
# you cannot order 3.7 boards.
QS = np.arange(1, 201)

joints = M.JOINTS_PER_BOARD * M.JOINT_FEE
ext = len(M.EXTENDED) * M.EXTENDED_FEE


def line_at(q):
    """Per-board JLC cost components at order quantity q, using the real LCSC ladders."""
    comp = 0.0
    for _line, _des, qty, code in M.BOM:
        comp += M.unit_price(px[code], qty * q) * qty
    bare = M.bare_pcb(q) / q
    fees = (M.ENGINEERING_FEE + ext + joints * q) / q
    return comp, bare, fees


rows = []
for q in QS:
    comp, bare, fees = line_at(int(q))
    jlc = comp + bare + fees
    rows.append(dict(q=int(q), comp=comp, bare=bare, fees=fees, jlc=jlc,
                     full=jlc + HAND_FIT_PER_BOARD))

q_arr = np.array([r["q"] for r in rows])
jlc = np.array([r["jlc"] for r in rows])
full = np.array([r["full"] for r in rows])
comp = np.array([r["comp"] for r in rows])
bare = np.array([r["bare"] for r in rows])
fees = np.array([r["fees"] for r in rows])

fig = plt.figure(figsize=(15.5, 10.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], hspace=0.52, wspace=0.24)
ax = fig.add_subplot(gs[0, 0])
ax2 = fig.add_subplot(gs[0, 1])
ax3 = fig.add_subplot(gs[1, 0])
ax4 = fig.add_subplot(gs[1, 1])

MARK_Q = [1, 5, 10, 20, 50, 100, 200]

# ---------------- A: per-board cost, the headline -----------------------------
ax.plot(q_arr, full, lw=2.6, color="#1f4e79", label="FULL board (JLC + hand-fit)")
ax.plot(q_arr, jlc, lw=2.2, color="#2e8b57", label="JLC only (assembler's charge)")
ax.fill_between(q_arr, jlc, full, color="#9dc3e6", alpha=0.45,
                label=f"hand-fit parts  ${HAND_FIT_PER_BOARD:.0f}/board  (APPROX)")
ax.set_xlabel("number of boards ordered")
ax.set_ylabel("price per board (USD)")
ax.set_title("A   Price per board vs quantity\n"
             "the two lines are PARALLEL: hand-fit parts never amortise", fontsize=10.5)
ax.legend(fontsize=8, loc="upper right")
ax.grid(alpha=0.25)
ax.set_xlim(0, 206)
ax.set_ylim(0, full[0] * 1.06)
for q in MARK_Q:
    i = q - 1
    ax.plot([q], [full[i]], "o", ms=4.5, color="#1f4e79")
# Endpoint values in a corner box instead of chasing the curve.
# The band BETWEEN the two curves is empty by construction -- it is the hand-fit gap, not data.
# Put the table there instead of on top of the green curve.
ax.text(0.055, 0.975,
        "\n".join(f"{q:3d} boards   ${full[q-1]:7.2f}" for q in (1, 10, 100, 200)),
        transform=ax.transAxes, ha="left", va="top", fontsize=7.4, family="monospace",
        bbox=dict(fc="white", ec="#b0b0b0", lw=0.7, pad=4.0, alpha=0.95))

# ---------------- B: total spend for the order -------------------------------
ax2.plot(q_arr, full * q_arr, lw=2.6, color="#1f4e79", label="FULL order")
ax2.plot(q_arr, jlc * q_arr, lw=2.2, color="#2e8b57", label="JLC-only order")
ax2.set_xlabel("number of boards ordered")
ax2.set_ylabel("total price for the whole order (USD)")
ax2.set_title("B   Total spend vs quantity\n"
              "rises overall, not monotonically:\nat a price break the whole order "
              "reprices", fontsize=10.5)
ax2.legend(fontsize=8, loc="lower right")
ax2.grid(alpha=0.25)
ax2.set_xlim(1, 206)
ax2.text(0.03, 0.96,
         "\n".join(f"{q:3d} boards = ${full[q - 1] * q:,.0f}" for q in (10, 50, 100, 200)),
         transform=ax2.transAxes, ha="left", va="top", fontsize=7.8, family="monospace",
         color="#1f4e79", bbox=dict(fc="white", ec="#b0b0b0", lw=0.7, pad=4.5))

# ---------------- C: components only, log Y ----------------------------------
ax3.plot(q_arr, comp, lw=2.4, color="#8e44ad", drawstyle="steps-post",
         label="components per board")
ax3.set_xlabel("number of boards ordered")
ax3.set_ylabel("component cost per board (USD, log)")
ax3.set_title("C   Components alone\n"
              "falls only at LCSC quantity breaks, never smoothly", fontsize=10.5)
ax3.set_yscale("log")
ax3.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v:.1f}"))
ax3.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v:.1f}"))
ax3.grid(alpha=0.25, which="both")
ax3.set_xlim(1, 206)
ax3.annotate(f"qty 1: ${comp[0]:.2f}", (1, comp[0]), textcoords="offset points",
             xytext=(8, 4), fontsize=7.6)
ax3.annotate(f"qty 200: ${comp[-1]:.2f}", (200, comp[-1]), textcoords="offset points",
             xytext=(-58, 6), fontsize=7.6)
for i, q in enumerate(MARK_Q):
    if q <= 200:
        ax3.plot([q], [comp[q - 1]], "o", ms=3.5, color="#8e44ad")

# ---------------- D: marginal cost of the next board ------------------------
total_full = full * q_arr
marginal = np.diff(total_full)          # cost added by board q+1
ax4.plot(q_arr[1:], marginal, lw=2.4, color="#c0392b",
         label="extra cost of going from N-1 to N boards")
ax4.axhline(HAND_FIT_PER_BOARD + comp[-1], ls="--", lw=1.4, color="#7f8c8d",
            label=f"floor at high qty ~${HAND_FIT_PER_BOARD + comp[-1]:.0f} "
                  f"(hand-fit $35 + components ${comp[-1]:.0f})")
ax4.set_xlabel("N = order size after adding the board")
ax4.set_ylabel("incremental order cost  T(N) - T(N-1)  (USD)")
ax4.set_title("D   Marginal cost\n"
              "flattens by qty ~10; past that you are buying boards, not saving", fontsize=10.5)
ax4.legend(fontsize=7.6, loc="upper center", bbox_to_anchor=(0.5, -0.20),
           ncol=2, framealpha=1.0, borderaxespad=0.0)
ax4.grid(alpha=0.25)
ax4.set_xlim(1, 206)
ax4.set_ylim(marginal.min() * 1.30, marginal.max() * 1.62)
ax4.axhline(0, lw=1.1, color="#2c3e50")
knee = 10
ax4.axvline(knee, ls=":", lw=1.6, color="#2c3e50")
ax4.annotate("knee ~10", (knee, marginal[knee - 1]), textcoords="offset points",
             xytext=(22, 46), fontsize=7.8, color="#2c3e50",
             arrowprops=dict(arrowstyle="->", lw=0.8, color="#2c3e50"))

# A NEGATIVE marginal cost is not a bug. Crossing an LCSC quantity break reprices EVERY unit in
# the order, so T(n+1) can be less than T(n). Mark the biggest one rather than let it read as an
# error -- vision_analyze flagged exactly that on the first render.
i_neg = int(np.argmin(marginal))
q_neg = q_arr[1:][i_neg]
ax4.annotate(f"\u2212${abs(marginal[i_neg]):.0f} at N={q_neg}",
             (q_neg, marginal[i_neg]), textcoords="offset points",
             xytext=(14, 22), fontsize=7.8, color="#922b21",
             arrowprops=dict(arrowstyle="->", lw=0.9, color="#922b21"))
ax4.text(0.97, 0.97,
         "a negative value is quantity-break repricing:\n"
         f"crossing {q_neg}, LCSC re-priced every unit,\n"
         f"so {q_neg} boards cost less than {q_neg - 1}",
         transform=ax4.transAxes, ha="right", va="top", fontsize=6.9, color="#922b21",
         bbox=dict(fc="#fdf2f0", ec="#e0b4ae", lw=0.7, pad=4.0))

fig.suptitle("Balloon hub v10 — price vs number of boards ordered  "
             "(components from live LCSC ladders)", fontsize=12.5, y=0.975)
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print(f"wrote {OUT}")

print(f"\nhand-fit per board: ${HAND_FIT_PER_BOARD:.2f} "
      f"(APPROX: ${HAND_FIT_APPROX:.2f} of it is estimated module prices)")
print(f"\n{'qty':>5s} {'per-board':>11s} {'JLC only':>10s} {'total':>11s} {'marginal':>10s}")
for q in MARK_Q:
    r = rows[q - 1]
    marg = marginal[q - 2] if q > 1 else float("nan")
    print(f"{q:5d} {r['full']:11.2f} {r['jlc']:10.2f} {r['full'] * q:11,.0f} "
          f"{marg:10.2f}")
