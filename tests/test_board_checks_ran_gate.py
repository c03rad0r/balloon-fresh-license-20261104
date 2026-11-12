"""The CI gate that proves the PCB board checks executed must itself be exact.

WHY: the four behavioural pipeline gates were reported green while SKIPPED, so
the suite's only end-to-end evidence was a no-op. `scripts/assert_board_checks_ran.py`
turns the JUnit report into a hard requirement. These tests prove it refuses
every way a check can fail to run, and accepts the real report.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assert_board_checks_ran.py"
REQUIRED = (
    "test_pipeline_creates_board_headless[v1-fast-15-17]",
    "test_pipeline_creates_board_headless[v2-adc-17-18]",
    "test_v2_adc_board_has_vdiv_mid_net",
    "test_board_outline_is_50x40mm",
)


def _load():
    spec = importlib.util.spec_from_file_location("assert_board_checks_ran", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(name: str, state: str) -> str:
    body = {
        "passed": "",
        "failed": '<failure message="boom"/>',
        "error": '<error message="boom"/>',
        "skipped": '<skipped message="no pcbnew"/>',
    }[state]
    return f'<testcase classname="tests.test_pcb_pipeline_gates" name="{name}">{body}</testcase>'


def _xml(path: Path, cases: dict[str, str]) -> Path:
    path.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="pytest">'
        + "".join(_case(n, s) for n, s in cases.items())
        + "</testsuite></testsuites>"
    )
    return path


def test_accepts_a_report_where_all_four_passed(tmp_path):
    module = _load()
    xml = _xml(tmp_path / "ok.xml", {name: "passed" for name in REQUIRED})
    assert module.check(str(xml)) == {}
    assert module.main([str(xml)]) == 0


@pytest.mark.parametrize("state", ["skipped", "failed", "error"])
def test_refuses_when_a_required_check_did_not_pass(tmp_path, state):
    module = _load()
    cases = {name: "passed" for name in REQUIRED}
    cases[REQUIRED[2]] = state
    xml = _xml(tmp_path / f"{state}.xml", cases)
    assert module.check(str(xml)) == {REQUIRED[2]: state if state != "error" else "failed"}
    assert module.main([str(xml)]) == 1


def test_refuses_when_a_required_check_is_absent(tmp_path):
    """`-k`, `--deselect` or an early exit must not read as success."""
    module = _load()
    cases = {name: "passed" for name in REQUIRED[:-1]}
    xml = _xml(tmp_path / "absent.xml", cases)
    assert module.check(str(xml)) == {REQUIRED[-1]: "absent"}
    assert module.main([str(xml)]) == 1


def test_refuses_an_unreadable_or_missing_report(tmp_path):
    module = _load()
    assert module.main([str(tmp_path / "nope.xml")]) == 2
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuite><testcase>")
    assert module.main([str(broken)]) == 2


def test_reports_every_offending_check_not_just_the_first(tmp_path, capsys):
    module = _load()
    cases = {name: "passed" for name in REQUIRED}
    cases[REQUIRED[0]] = "skipped"
    cases[REQUIRED[3]] = "failed"
    xml = _xml(tmp_path / "multi.xml", cases)
    assert module.main([str(xml)]) == 1
    err = capsys.readouterr().err
    assert REQUIRED[0] in err and REQUIRED[3] in err


def test_runs_as_a_script_like_ci_invokes_it(tmp_path):
    xml = _xml(tmp_path / "cli.xml", {name: "passed" for name in REQUIRED})
    proc = subprocess.run([sys.executable, str(SCRIPT), str(xml)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "4/4 board checks ran and passed" in proc.stdout
