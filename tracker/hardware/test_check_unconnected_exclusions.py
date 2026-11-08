#!/usr/bin/env python3
"""Tests for check_unconnected_exclusions.py -- the classifier must be able to BOTH pass
and fail, and must never silently swallow a real record.

The controls use the REAL board and the REAL DRC output, because a synthetic fixture
would only prove the harness works. Three properties are asserted:

  1 POSITIVE  the live board classifies 5 REAL opens, and the gate FAILS when asked to
              expect 6. If this stops failing, the expectation check is broken.
  2 NEGATIVE  the same run with --expect-real 5 PASSES. A gate that fails on a correct
              board trains people to ignore it.
  3 CONTENT   the five exclusions are the exact set measured: 3 two-face + 2 GND anchors
              + 1 duplicate. And /EN, /SPI2_SCK, /F33_VSENSE, /VSCAP are REAL, never
              excluded. If a real trap ever gets excluded, this test is what notices.

Run: /usr/bin/python3 -m pytest tracker/hardware/test_check_unconnected_exclusions.py -q
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "check_unconnected_exclusions.py")
ADIR = os.path.join(HERE, "..", "..", "docs", "analysis", "bulk-route-20261107")
BOARD = os.path.join(ADIR, "DRCLIVE.kicad_pcb")
DRC = os.path.join(ADIR, "drc-live.json")

needs = pytest.mark.skipif(
    not (os.path.exists(BOARD) and os.path.exists(DRC)),
    reason="live board + DRC not present (regenerate with kicad-cli)")


def run(expect, tmp):
    js = os.path.join(tmp, "out.json")
    r = subprocess.run(
        [sys.executable, TOOL, BOARD, "--drc", DRC,
         "--expect-real", str(expect), "--json-out", js],
        capture_output=True, text=True, timeout=900)
    return r, (json.load(open(js)) if os.path.exists(js) else None)


@needs
def test_wrong_expectation_fails(tmp_path):
    """POSITIVE CONTROL: expecting 6 must FAIL, because the measured answer is 5."""
    r, data = run(6, str(tmp_path))
    assert r.returncode == 1, f"gate passed a wrong expectation:\n{r.stdout[-2000:]}"
    assert data["real"] == 5, data["real"]


@needs
def test_correct_expectation_passes(tmp_path):
    """NEGATIVE CONTROL: expecting the measured 5 must PASS."""
    r, data = run(5, str(tmp_path))
    assert r.returncode == 0, f"gate failed a correct board:\n{r.stdout[-2000:]}"
    assert data["real"] == 5


@needs
def test_exclusions_are_the_measured_set(tmp_path):
    """CONTENT: exactly 3 two-face, 2 GND anchors, 1 duplicate -- no more, no fewer."""
    r, data = run(5, str(tmp_path))
    c = data["counts"]
    assert c.get("TWO_FACE") == 3, c
    assert c.get("GND_ANCHOR") == 2, c
    assert c.get("DUPLICATE") == 1, c
    assert c.get("UNCLASSIFIED", 0) == 0, c


@needs
def test_real_traps_are_never_excluded(tmp_path):
    """CONTENT: the four genuine traps must stay REAL. An exclusion that swallows one
    of these is worse than no exclusion at all."""
    r, data = run(5, str(tmp_path))
    real_text = " ".join(
        " ".join(rec["items"]) for rec in data["records"] if rec["class"] == "REAL")
    for net in ("/EN", "/SPI2_SCK", "/F33_VSENSE", "/VSCAP"):
        assert net in real_text, f"{net} was not classified REAL:\n{real_text}"


@needs
def test_two_face_index_covers_all_sixteen(tmp_path):
    """CONTENT: the pattern index must find 16 pad numbers, matching count_two_face.py."""
    r = subprocess.run([sys.executable, TOOL, BOARD, "--drc", DRC],
                       capture_output=True, text=True, timeout=900)
    assert "two-face pad numbers derived from the board: 16" in r.stdout, r.stdout[:1500]


def test_rejects_missing_drc():
    """The tool must fail loudly, not pass, when it cannot read its input."""
    r = subprocess.run([sys.executable, TOOL, BOARD, "--drc", "/nonexistent.json"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode != 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
