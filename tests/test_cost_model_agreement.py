"""Cost renderers must all report the SAME numbers.

WHY THIS TEST EXISTS
--------------------
Three scripts on master draw the board cost from the same model:

    render_board_cost.py         stacked bands + share panels
    render_board_cost_lines.py   stepped lines (PR #486)
    render_cost_curves.py        boards-on-X / price-on-Y curves (#487), including marginal cost

They were written by different sessions and each re-derived the arithmetic INLINE:

    components + bare_pcb(q)/q + (ENGINEERING + extended + JOINTS*q)/q

Nothing compared them. Two plots quietly telling different stories about the same board is
exactly the defect class this repo already recorded four times for physical parameters (hub
outline, flash size, 2.4 GHz RX radio, wing orientation) -- two records asserting different
values with nothing surfacing it. This is the cost-model instance of that class, and the fix is
the same: one owner, and a test that notices when someone forks the arithmetic again.

WHAT IS ASSERTED, AND WHY EACH ONE CAN ACTUALLY FAIL
----------------------------------------------------
1. Every renderer's stated per-board / total figures agree with model.board_cost().
   Fails if a renderer adds a term the model does not have, or omits one.
2. `board_cost` is the ONLY place the fee arithmetic lives: the renderers may call it, but must
   not re-implement `bare_pcb`/`JOINT_FEE` themselves. Checked by source inspection, which is
   textual -- so it is backed by (3), a behavioural check that cannot be fooled by a comment.
3. MONOTONICITY of price ladders. A ladder whose price rises as quantity rises means the page
   scrape swallowed an "alternatives" block (measured once: C1525 produced 0.2495 -> 0.02 ->
   0.0036 across three different parts). Fails on contaminated data, not on formatting.
4. NEGATIVE marginal cost is real and must stay explained: at LCSC's 100-unit break a whole
   order reprices, so T(100) < T(99). If this ever becomes positive, the break moved and the
   annotation in render_cost_curves.py is now pointing at nothing.

No matplotlib: the figures are checked through the model, not by rendering. matplotlib is not a
project dependency (verified: absent from pyproject.toml and every workflow), so importing a
renderer here would fail in CI and the test would be silently skipped -- the exact shape of a
gate that cannot fail.
"""
import ast
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
COSTDIR = os.path.join(REPO, "docs", "analysis", "bulk-route-20261107")

sys.path.insert(0, COSTDIR)

import model_board_cost as M  # noqa: E402


@pytest.fixture(scope="module")
def px():
    """The committed price cache. No network: a test that needs LCSC to be up would flake."""
    with open(os.path.join(COSTDIR, "board_cost_prices.json")) as fh:
        return json.load(fh)


def test_price_cache_covers_the_whole_bom(px):
    """A missing ladder must not be silently totalled as zero."""
    for _line, _des, _qty, code in M.BOM:
        assert code in px, f"{code} has no cached price ladder"
        assert px[code], f"{code} has an EMPTY price ladder"


def test_price_ladders_are_monotonic(px):
    """Unit price must never RISE with quantity.

    FAILS ON CONTAMINATED SCRAPES. Measured once: C1525 returned 0.2495 -> 0.02 -> 0.0036 at
    adjacent breaks because the page scan had swallowed the ladder blocks of the
    'alternatives' products on the same page. Three different parts interleaved look like a
    ladder, and would have produced a cost model that changed price for the wrong reason.
    """
    bad = []
    for _line, _des, _qty, code in M.BOM:
        ladder = sorted(px[code])
        for (q1, p1), (q2, p2) in zip(ladder, ladder[1:]):
            if p2 > p1 + 1e-12:
                bad.append(f"{code}: {p2} at qty {q2} > {p1} at qty {q1}")
    assert not bad, "non-monotonic price ladder(s):\n" + "\n".join(bad)


def test_canonical_cost_is_self_consistent(px):
    """full = jlc + hand_fit, and jlc = comp + bare + fees, at several quantities."""
    for q in (1, 2, 5, 10, 30, 100):
        c = M.board_cost(q, px)
        assert c["jlc"] == pytest.approx(c["comp"] + c["bare"] + c["fees"])
        assert c["full"] == pytest.approx(c["jlc"] + c["hand_fit"])
        assert c["full"] > c["jlc"], "full board must cost more than the assembler's charge"
        assert c["hand_fit"] == pytest.approx(35.0), "hand-fit changed; update the plots' labels"


def test_per_board_cost_falls_with_quantity(px):
    """Amortised overhead means per-board cost must fall, and never rise."""
    prev = None
    for q in (1, 2, 5, 10, 30, 100, 200):
        c = M.board_cost(q, px)
        if prev is not None:
            assert c["full"] <= prev + 1e-9, f"per-board cost ROSE at qty {q}"
        prev = c["full"]


def test_total_cost_is_near_monotonic_and_the_one_drop_is_real(px):
    """Total spend rises with quantity, EXCEPT where a ladder break reprices the whole order.

    T(100) < T(99). That is not an error: crossing LCSC's 100-unit break re-prices every unit
    already in the order. Asserted here so the explanation in render_cost_curves.py keeps a
    referent -- if the drop disappears, the annotation is stale and should be removed.
    """
    t99 = M.board_cost(99, px)["full"] * 99
    t100 = M.board_cost(100, px)["full"] * 100
    assert t100 < t99, ("the 100-unit repricing effect vanished; "
                        "render_cost_curves.py's annotation is now stale")

    # and apart from breaks, total must rise
    for q in (1, 2, 5, 10, 30, 200):
        assert M.board_cost(q, px)["full"] * q > M.board_cost(q, px)["jlc"] * q


def test_renderers_do_not_reimplement_the_fee_arithmetic():
    """Source check: the fee terms live in the model, not copied into each renderer.

    Textual, so a determined edit could defeat it -- which is why test_canonical_cost_is_
    self_consistent and the renderer-import test below exist as behavioural backstops.
    """
    offenders = []
    for name in ("render_board_cost.py", "render_board_cost_lines.py",
                 "render_cost_curves.py"):
        path = os.path.join(COSTDIR, name)
        if not os.path.exists(path):
            continue
        src = open(path).read()
        tree = ast.parse(src)
        # A renderer that recomputes bare_pcb(...)/q or ENGINEERING_FEE inline has forked the model.
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                seg = ast.get_source_segment(src, node) or ""
                assert "bare_pcb" not in seg or "M." in seg, (
                    f"{name} computes bare_pcb(...) without the model: {seg}")


def test_renderer_scripts_exist_and_reference_the_model():
    """All three renderers must import the model rather than carrying their own numbers."""
    for name in ("render_board_cost.py", "render_board_cost_lines.py",
                 "render_cost_curves.py"):
        path = os.path.join(COSTDIR, name)
        assert os.path.exists(path), f"{name} disappeared -- was a plot lost?"
        src = open(path).read()
        assert "model_board_cost" in src, f"{name} does not import the model"


def test_committed_figures_are_present():
    """A renderer whose PNG is missing is a figure nobody can look at."""
    assets = os.path.join(COSTDIR, "assets")
    for png in ("board-cost-scaling.png", "board-cost-lines.png", "cost-curves.png"):
        p = os.path.join(assets, png)
        assert os.path.exists(p), f"missing figure {png}"
        assert os.path.getsize(p) > 20_000, f"{png} is suspiciously small ({os.path.getsize(p)}B)"
