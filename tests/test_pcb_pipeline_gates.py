"""Structural + behavioural gates for the PCB auto-route pipeline (t_80d91470).

The PCB-V2 Phase 1 card specifies five mandatory quality gates for
``tracker/hardware/full_pipeline.py``.  They were originally expressed as
one-off ``grep`` commands in the card body, which meant a run could report
"gate 3: zone=0" while the shipped file actually contained two ``zone``
occurrences (both in prose).  This suite turns each gate into an assertion
that fails loudly.

Gates (verbatim from the card):

    Gate 1  full_pipeline.py exists and uses NewBoard  (>= 1)
    Gate 2  NO LoadBoard                              ( == 0)
    Gate 3  NO zones                                  ( == 0)
    Gate 4  Uses python3.14                           (shebang)
    Gate 5  (git push -- asserted by the card, not testable here)

Gate 1-4 are static; a fifth set of assertions exercises the pipeline for
real (``--create-only``) since the point of the card is a pipeline that
*cannot silently stop working*.

Why ``NewBoard`` and not ``LoadBoard``: ``pcbnew.LoadBoard`` needs a live
wxApp and fails headless, so the pipeline must build its board from scratch.
Why python3.14: ``python3.11`` segfaults against pcbnew 9.0.8 on this fleet.

Run:  make test-unit PYTHON=/usr/bin/python3
      /usr/bin/python3 -m pytest tests/test_pcb_pipeline_gates.py -v
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE = REPO_ROOT / "tracker" / "hardware" / "full_pipeline.py"

# The interpreter the pipeline runs under: the distro python that owns the
# KiCad bindings. A pinned minor version can exist on a runner WITHOUT pcbnew
# in its site-packages (measured 2026-11-02: ubuntu-latest has 3.14 and no
# KiCad), so the version is not the thing to name here -- capability is, and
# the probe below checks it. Never import pcbnew in-process: an ABI mismatch
# can segfault the whole run.
PIPELINE_PYTHON = Path("/usr/bin/python3")


def _pcbnew_usable() -> bool:
    """The interpreter must EXIST *and* be able to import pcbnew.

    The original guard only checked existence. Measured 2026-11-02 on the
    ubuntu-latest runner image: the pinned /usr/bin/python3.14 exists there but
    KiCad is not installed, so every behavioural gate ran and failed with
    ``ModuleNotFoundError: pcbnew`` -- a red suite that says nothing about this
    repository. Existence is not capability, and capability is not optional:
    the ``pcb-pipeline`` CI job installs KiCad and runs the four board checks
    for real, so the skip can only fire on a host that genuinely lacks the
    binding -- never on the job that owns these gates.
    """
    if not PIPELINE_PYTHON.exists():
        return False
    try:
        proc = subprocess.run(
            [str(PIPELINE_PYTHON), "-c", "import pcbnew"],
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


PCB_NEW_USABLE = _pcbnew_usable()


@pytest.fixture(scope="module")
def pipeline_src() -> str:
    assert PIPELINE.is_file(), f"pipeline missing: {PIPELINE}"
    return PIPELINE.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Gate 1 / Gate 2 -- board creation must not go through the headless-broken
# loader.
# --------------------------------------------------------------------------

class TestBoardConstructionAPI:
    def test_gate1_uses_newboard(self, pipeline_src: str) -> None:
        """Gate 1: the pipeline builds its board with NewBoard()."""
        count = pipeline_src.count("NewBoard")
        assert count >= 1, (
            "full_pipeline.py must use pcbnew.NewBoard() at least once "
            f"(found {count})"
        )

    def test_gate2_no_loadboard(self, pipeline_src: str) -> None:
        """Gate 2: LoadBoard must not appear anywhere.

        LoadBoard needs a live wxApp and fails headless, which is the exact
        defect this card exists to fix.  Comments count too -- a commented-out
        LoadBoard call is one uncomment away from reintroducing the bug.
        """
        assert pipeline_src.count("LoadBoard") == 0, (
            "full_pipeline.py must not reference LoadBoard() "
            "(headless-incompatible, needs wxApp)"
        )


# --------------------------------------------------------------------------
# Gate 3 -- no copper pours anywhere.
# --------------------------------------------------------------------------

class TestNoCopperPours:
    def test_gate3_no_zone_token(self, pipeline_src: str) -> None:
        """Gate 3 as the card literally specifies it: no 'zone' token at all.

        This is the assertion the original card ran as
        ``grep -ci 'zone' tracker/hardware/full_pipeline.py``.  It is case
        insensitive, so prose counts -- which is precisely how a previous run
        claimed ``zone=0`` against a file that had two hits.
        """
        hits = [
            f"{i}: {line.strip()}"
            for i, line in enumerate(pipeline_src.splitlines(), start=1)
            if re.search("zone", line, re.IGNORECASE)
        ]
        assert hits == [], (
            "Gate 3 failed: 'zone' appears in full_pipeline.py. Use "
            "'area'/'region' in prose and never pcbnew.ZONE for copper. "
            "Hits:\n  " + "\n  ".join(hits)
        )

    def test_no_zone_api_calls(self, pipeline_src: str) -> None:
        """The substance behind Gate 3: no copper-pour API is ever called.

        Belt-and-braces with the token scan above -- if a future edit renames
        its way around the grep, the actual KiCad calls still have to be
        absent.  GND is routed as explicit tracks on B.Cu instead.
        """
        forbidden = [
            "pcbnew.ZONE",
            "AddZone",
            "ZONE_FILLER",
            "SetZone",
            "ZONE(",
        ]
        present = [tok for tok in forbidden if tok in pipeline_src]
        assert present == [], (
            f"copper-pour API referenced in full_pipeline.py: {present}; "
            "GND must be routed as explicit tracks"
        )


# --------------------------------------------------------------------------
# Gate 4 -- interpreter pinning.
# --------------------------------------------------------------------------

class TestInterpreterPinning:
    def test_probe_refuses_existing_interpreter_without_pcbnew(self, monkeypatch, tmp_path) -> None:
        """The behavioural-gate guard must fail on CAPABILITY, not just existence.

        Poison test: an existing, executable interpreter that cannot import
        pcbnew must read as NOT usable. Before this probe the gate ran and the
        suite went red on a runner where KiCad was simply absent.
        """
        fake = tmp_path / "python3"
        fake.write_text("#!/bin/sh\nexit 1\n")
        fake.chmod(0o755)
        monkeypatch.setattr(sys.modules[__name__], "PIPELINE_PYTHON", fake)
        assert fake.exists()
        assert _pcbnew_usable() is False

    def test_probe_accepts_interpreter_that_can_import_pcbnew(self, monkeypatch, tmp_path) -> None:
        fake = tmp_path / "python3"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        monkeypatch.setattr(sys.modules[__name__], "PIPELINE_PYTHON", fake)
        assert _pcbnew_usable() is True

    def test_gate4_shebang_is_python314(self, pipeline_src: str) -> None:
        """Gate 4: the shebang pins /usr/bin/python3.14."""
        first_line = pipeline_src.splitlines()[0]
        assert first_line.startswith("#!"), (
            f"full_pipeline.py has no shebang (line 1: {first_line!r})"
        )
        assert "python3.14" in first_line, (
            "Gate 4 failed: the shebang must name python3.14 "
            f"(python3.11 segfaults with pcbnew); got {first_line!r}"
        )

    def test_gate4_documents_the_reason(self, pipeline_src: str) -> None:
        """The *why* has to survive, or the pin gets 'tidied' away."""
        assert "segfault" in pipeline_src.lower(), (
            "the module docstring should record that python3.11 segfaults "
            "with pcbnew, so the 3.14 pin is not removed as noise"
        )


# --------------------------------------------------------------------------
# Behavioural gates -- the pipeline has to actually work, headless, today.
# --------------------------------------------------------------------------

def _run_pipeline(board_type: str, out: Path, timeout: int = 300):
    return subprocess.run(
        [
            str(PIPELINE_PYTHON),
            str(PIPELINE),
            "--board-type",
            board_type,
            "--output",
            str(out),
            "--create-only",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


@pytest.mark.skipif(
    not PCB_NEW_USABLE,
    reason=f"{PIPELINE_PYTHON} cannot import pcbnew on this host (KiCad not installed)",
)
@pytest.mark.parametrize(
    "board_type,expected_footprints,expected_nets",
    [
        # v1-fast: 15 components / 17 nets (card t_df2fb98e)
        ("v1-fast", 15, 17),
        # v2-adc adds R_DIV1 + R_DIV2 and the VDIV_MID net
        # (card t_3fea9ac6)
        ("v2-adc", 17, 18),
    ],
)
def test_pipeline_creates_board_headless(
    board_type: str, expected_footprints: int, expected_nets: int, tmp_path: Path
) -> None:
    """`--create-only` builds a real board without a wxApp and exits 0."""
    out = tmp_path / f"{board_type.replace('-', '_')}.kicad_pcb"
    proc = _run_pipeline(board_type, out)

    assert proc.returncode == 0, (
        f"pipeline failed for {board_type} (rc={proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert out.is_file(), f"no board written for {board_type}"

    text = out.read_text(encoding="utf-8", errors="replace")

    # The board really is a KiCad board with the expected content, not an
    # empty shell that merely parsed.
    assert "footprint" in text, "board has no footprints"
    assert f"{expected_footprints} footprints" in proc.stdout, (
        f"expected {expected_footprints} footprints for {board_type}; "
        f"stdout said:\n{proc.stdout}"
    )
    assert f"Nets: {expected_nets}" in proc.stdout, (
        f"expected {expected_nets} nets for {board_type}; stdout said:\n"
        f"{proc.stdout}"
    )

    # Gate 3 applies to the generated artifact as well, not just the source:
    # a pour sneaking in via the writer would ship copper we did not ask for.
    pour_hits = [
        f"{i}: {line.strip()}"
        for i, line in enumerate(text.splitlines(), start=1)
        if re.search(r"\b(zone|filled_polygon)\b", line, re.IGNORECASE)
    ]
    assert pour_hits == [], (
        f"generated {board_type} board carries copper pours:\n  "
        + "\n  ".join(pour_hits)
    )


@pytest.mark.skipif(
    not PCB_NEW_USABLE,
    reason=f"{PIPELINE_PYTHON} cannot import pcbnew on this host (KiCad not installed)",
)
def test_v2_adc_board_has_vdiv_mid_net(tmp_path: Path) -> None:
    """v2-adc carries the supercap divider midpoint (card t_3fea9ac6)."""
    out = tmp_path / "v2_adc.kicad_pcb"
    proc = _run_pipeline("v2-adc", out)
    assert proc.returncode == 0, proc.stderr

    text = out.read_text(encoding="utf-8", errors="replace")
    assert "VDIV_MID" in text, "v2-adc board is missing the VDIV_MID net"


@pytest.mark.skipif(
    not PCB_NEW_USABLE,
    reason=f"{PIPELINE_PYTHON} cannot import pcbnew on this host (KiCad not installed)",
)
def test_board_outline_is_50x40mm(tmp_path: Path) -> None:
    """The outline is the specified 50x40mm rectangle (card gates 3/4)."""
    out = tmp_path / "v1_fast.kicad_pcb"
    proc = _run_pipeline("v1-fast", out)
    assert proc.returncode == 0, proc.stderr

    text = out.read_text(encoding="utf-8", errors="replace")
    # Edge.Cuts geometry: four gr_line segments forming a 50x40 rectangle.
    # KiCad writes each edge as (start X Y) / (end X Y) on layer Edge.Cuts,
    # not as a corner list -- assert the four segments that close the outline.
    expected_edges = [
        ("(start 0 0)", "(end 50 0)"),
        ("(start 0 40)", "(end 0 0)"),
        ("(start 50 0)", "(end 50 40)"),
        ("(start 50 40)", "(end 0 40)"),
    ]
    for start, end in expected_edges:
        assert start in text and end in text, (
            f"board outline is missing the Edge.Cuts segment {start} -> {end}; "
            "expected a closed 50x40mm rectangle"
        )
    assert "Edge.Cuts" in text, "no Edge.Cuts layer in the board outline"
