#!/usr/bin/env python3
"""Fail closed unless the four PCB pipeline board checks actually RAN and passed.

WHY THIS EXISTS
    The four behavioural checks in ``tests/test_pcb_pipeline_gates.py`` build a
    real board with pcbnew. When the binding was missing they were skipped
    (originally by a ``skipif`` on interpreter EXISTENCE), so CI reported a green
    tick while the pipeline's only end-to-end evidence was a no-op. A skipped
    check is a missing check, not a pass.

    This reads the JUnit XML that the CI job writes and exits non-zero if any of
    the required cases is absent, skipped, errored or failed. It deliberately
    does NOT care how the job invoked pytest: ``-k``, ``--deselect``, a stray
    skip marker, or an early exit all show up as "absent" or "skipped" here.

Usage:
    python3 scripts/assert_board_checks_ran.py <junit.xml> [--require NAME ...]
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

REQUIRED = (
    "test_pipeline_creates_board_headless[v1-fast-15-17]",
    "test_pipeline_creates_board_headless[v2-adc-17-18]",
    "test_v2_adc_board_has_vdiv_mid_net",
    "test_board_outline_is_50x40mm",
)


def outcomes(xml_path: str) -> dict[str, str]:
    """Map testcase name -> passed | failed | skipped."""
    root = ET.parse(xml_path).getroot()
    result: dict[str, str] = {}
    for case in root.iter("testcase"):
        name = case.get("name") or ""
        if case.find("skipped") is not None:
            state = "skipped"
        elif case.find("failure") is not None or case.find("error") is not None:
            state = "failed"
        else:
            state = "passed"
        result[name] = state
    return result


def check(xml_path: str, required=REQUIRED) -> dict[str, str]:
    """Return {name: state} for every required case that is not a pass."""
    seen = outcomes(xml_path)
    return {name: seen.get(name, "absent") for name in required if seen.get(name) != "passed"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("junit_xml")
    parser.add_argument("--require", action="append", default=None,
                        help="testcase name that must have passed (repeatable)")
    args = parser.parse_args(argv)

    required = tuple(args.require) if args.require else REQUIRED
    try:
        bad = check(args.junit_xml, required)
    except (OSError, ET.ParseError) as exc:
        print(f"REFUSING: cannot read a JUnit report at {args.junit_xml}: {exc}",
              file=sys.stderr)
        return 2
    if bad:
        for name, state in bad.items():
            print(f"NOT RUN: {state:<8} {name}", file=sys.stderr)
        print("REFUSING: the board checks did not execute for real. A skip is not a pass.",
              file=sys.stderr)
        return 1
    print(f"{len(required)}/{len(required)} board checks ran and passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
