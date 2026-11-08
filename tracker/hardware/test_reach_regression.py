#!/usr/bin/env python3
"""Tests for reach_regression.py -- the gate must be able to BOTH fail and pass.

A gate that only ever passes is not a gate. The real board state gives us both controls for
free, which is stronger than a synthetic fixture:

  POSITIVE CONTROL (must FAIL): the /SPI1_SCK batch, which laid a 2.60 mm B.Cu run at x=35.25
      and walled /SPI1_MOSI off from the rest of the board. Every other gate I had passed this
      batch. If this test stops failing, the gate has regressed into uselessness.

  NEGATIVE CONTROL (must PASS): the /SPI1_SCK batch compared against ITSELF -- same board before
      and after. A gate that reports a regression when nothing changed is worse than no gate,
      because it trains the operator to ignore it.

Run: ~/.venvs/pcbci/bin/python -m pytest tracker/hardware/test_reach_regression.py -q
"""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOL = os.path.join(HERE, "reach_regression.py")
BATCH = os.path.join(REPO, "docs", "analysis", "bulk-route-20261107", "batches", "SPI1SCK_UC")
BEFORE_DRC = os.path.join(REPO, "docs", "analysis", "bulk-route-20261107", "batches",
                          "U3IRQ", "drc.json")

needs_batch = pytest.mark.skipif(
    not (os.path.exists(os.path.join(BATCH, "routed.kicad_pcb"))
         and os.path.exists(BEFORE_DRC)),
    reason="SPI1SCK_UC batch artifacts not present")


def run(before, after, drc_before, drc_after, tmp_path):
    rep = tmp_path / "r.json"
    r = subprocess.run(
        [sys.executable, TOOL, "--before", before, "--after", after,
         "--drc-before", drc_before, "--drc-after", drc_after, "--report", str(rep)],
        capture_output=True, text=True, timeout=1800)
    return r, (json.load(open(rep)) if rep.exists() else None)


@needs_batch
def test_catches_the_spi1_sck_reachability_loss(tmp_path):
    """POSITIVE CONTROL: this exact batch destroyed /SPI1_MOSI reachability. Must FAIL."""
    r, rep = run(os.path.join(BATCH, "board.kicad_pcb"),
                 os.path.join(BATCH, "routed.kicad_pcb"),
                 BEFORE_DRC, os.path.join(BATCH, "drc.json"), tmp_path)
    assert r.returncode == 1, f"gate passed a batch that lost a pair:\n{r.stdout}"
    assert rep["verdict"] == "FAIL"
    lost = {tuple(x) for x in rep["lost"]}
    assert any(net == "/SPI1_MOSI" for net, _, _ in lost), (
        f"/SPI1_MOSI not detected as lost; got {lost}")


@needs_batch
def test_same_board_is_not_a_regression(tmp_path):
    """NEGATIVE CONTROL: board against itself must PASS, or the gate cries wolf."""
    p = os.path.join(BATCH, "routed.kicad_pcb")
    d = os.path.join(BATCH, "drc.json")
    r, rep = run(p, p, d, d, tmp_path)
    assert r.returncode == 0, f"gate invented a regression on an unchanged board:\n{r.stdout}"
    assert rep["verdict"] == "PASS"
    assert rep["lost"] == []


def test_module_imports_and_has_both_entry_points():
    """The tool must expose main() and the pair enumerator, and fail loudly without args."""
    spec = importlib.util.spec_from_file_location("rr", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert hasattr(m, "main")
    assert hasattr(m, "net_pairs")
    assert hasattr(m, "reachable")
    r = subprocess.run([sys.executable, TOOL], capture_output=True, text=True, timeout=120)
    assert r.returncode != 0, "tool exited 0 with no arguments"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
