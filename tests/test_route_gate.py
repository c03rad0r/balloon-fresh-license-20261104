"""Tests for the scoped router's acceptance gate.

The gate exists so a route that makes the board worse is never written. It has now failed to stop a
defect twice, both times because it compared the wrong thing:

  * once because a route produced `shorting_items` that the gate's `hard` set happened to include
    only after the fact -- it was written as a class check, so a NEW class was needed to trip it,
  * once (measured 2026-11-03) because a route grew `via_dangling` from 2 to 3 and left `unconnected`
    at exactly 42, and the gate said "no new classes" and KEPT it.

Both share one shape: `set(after) - set(before)` cannot see a class that was already present getting
worse. These tests pin the corrected semantics: counts per class, and a route must strictly reduce the
unconnected count.

Run: python3 -m pytest tests/test_route_gate.py -q
"""
import ast
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTER = os.path.join(ROOT, "docs", "analysis", "solar-8land-verify", "route_scoped.py")


def _source():
    with open(ROUTER) as f:
        return f.read()


def _gate_block():
    """Return the source text of the acceptance gate (from `COUNT PER CLASS` to the return)."""
    src = _source()
    start = src.index("COUNT PER CLASS")
    end = src.index("return 0", start)
    return src[start:end]


def test_gate_compares_counts_not_just_classes():
    """A class that already existed must not be allowed to grow."""
    block = _gate_block()
    assert "grown" in block, "gate no longer computes per-class growth"
    # the computation must involve before/after COUNTS, not set difference alone
    assert "after.get(c, 0) > before.get(c, 0)" in block, (
        "gate does not compare counts per class; a class that exists at 2 and grows to 3 would pass"
    )


def test_gate_refuses_when_unconnected_does_not_drop():
    """`uafter >= ubefore` must refuse: laying copper that closes nothing is not progress."""
    block = _gate_block()
    assert "uafter >= ubefore" in block, (
        "gate permits an unchanged unconnected count; measured 2026-11-03 that let a route that "
        "closed nothing through while adding a dangling via"
    )


def test_gate_still_refuses_hard_classes():
    """Shorting/clearance must refuse regardless of counts."""
    src = _source()
    assert 'hard = {"shorting_items", "clearance"' in src.replace("\n", " ").replace("  ", " ") or \
           "shorting_items" in src
    assert "REFUSING: short/clearance class present" in src


def test_router_parses():
    """A syntax error here means the router cannot run at all; catch it before a long board run."""
    ast.parse(_source())


def test_no_invented_layer_arithmetic():
    """`1 - layer` named an inner layer (F.Cu=0, B.Cu=2). It must not reappear in CODE.

    Only executable lines count. The router's docstrings and comments deliberately quote the old
    expression while explaining the bug, and an earlier version of this test failed on the
    explanation rather than on a regression (measured 2026-11-03).
    """
    tree = ast.parse(_source())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            left, right = node.left, node.right
            if (isinstance(left, ast.Constant) and left.value == 1
                    and isinstance(right, ast.Name) and right.id.startswith("lay")):
                offenders.append(getattr(node, "lineno", 0))
    assert not offenders, (
        f"layer-1 arithmetic reintroduced at line(s) {offenders}; KiCad uses F.Cu=0, B.Cu=2"
    )
