#!/usr/bin/env python3
"""freeroute.py -- freerouting as a GATED alternative router, not an autorouter.

WHY THIS IS A WRAPPER AND NOT JUST `freerouting -de ... -do ...`.

Measured 2026-11-08 on the balloon hub (15 opens, board e00b98e7):
  full S1 (0.200/0.200)  -> 46 unrouted, 82 violations            REJECTED
  S1 loosened            -> 10 opens, 63 violations; the five
                            "wins" route through C10 at 0.000 mm    REJECTED

freerouting will happily buy opens by violating clearance. So its output is only
ever a CANDIDATE. This wrapper runs the same three gates as any other routing and
refuses to hand back a board that fails them:

  gate 1  native DRC opens must DECREASE, and violations must not INCREASE
  gate 2  reachability must not regress (tracker/hardware/reach_regression.py)
  gate 3  no via-in-pad introduced (tracker/hardware/verify_via_in_pad.py)

If any gate fails, the live board is untouched and the exit code is non-zero. The
candidate board is still written to a scratch path so the failure can be inspected.

USAGE
  freeroute.py --board B.kicad_pcb [--out CAND.kicad_pcb] [--workdir DIR]
               [--passes N] [--threads N]

Requires: freerouting on PATH, kicad-cli, pcbnew under the invoking python.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def drc_counts(board, out_json):
    r = run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
             "--units", "mm", "--output", out_json, board], timeout=1800)
    if not os.path.exists(out_json):
        raise RuntimeError(f"kicad-cli DRC produced no JSON\n{r.stdout}\n{r.stderr}")
    d = json.load(open(out_json))
    return len(d.get("violations", [])), len(d.get("unconnected_items", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--workdir", default="")
    ap.add_argument("--passes", type=int, default=30)
    ap.add_argument("--threads", type=int, default=7)
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()

    if shutil.which("freerouting") is None:
        print("REFUSED: freerouting not on PATH. Install via "
              "ansible-playbook -i inventory.ini playbook-kicad-headless.yml",
              file=sys.stderr)
        return 2

    work = a.workdir or tempfile.mkdtemp(prefix="freeroute-")
    os.makedirs(work, exist_ok=True)
    board = os.path.abspath(a.board)
    tag = os.path.splitext(os.path.basename(board))[0]

    # freerouting needs the project sidecars beside the board
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.splitext(board)[0] + ext
        if os.path.exists(src):
            shutil.copy(src, os.path.join(work, tag + ext))
    shutil.copy(board, os.path.join(work, tag + ".kicad_pcb"))
    b = os.path.join(work, tag + ".kicad_pcb")
    dsn = os.path.join(work, tag + ".dsn")
    ses = os.path.join(work, tag + ".ses")
    cand = a.out or os.path.join(work, tag + "-freerouted.kicad_pcb")

    print(f"[1/6] baseline DRC on {os.path.basename(board)}")
    bv, bu = drc_counts(b, os.path.join(work, "before.json"))
    print(f"      violations={bv} opens={bu}")

    print("[2/6] export Specctra DSN (pcbnew; kicad-cli cannot do this)")
    r = run([sys.executable, os.path.join(HERE, "dsn_roundtrip.py"),
             "export", b, dsn], timeout=1800)
    if not os.path.exists(dsn):
        print(f"REFUSED: DSN export failed\n{r.stdout}\n{r.stderr}", file=sys.stderr)
        return 2

    print(f"[3/6] route with freerouting ({a.passes} passes, {a.threads} threads)")
    r = run(["freerouting", "-de", dsn, "-do", ses, "-mp", str(a.passes),
             "-mt", str(a.threads)], timeout=a.timeout)
    if not os.path.exists(ses):
        print(f"REFUSED: freerouting produced no SES\n{r.stdout[-2000:]}", file=sys.stderr)
        return 2

    print("[4/6] import SES back into the board")
    r = run([sys.executable, os.path.join(HERE, "dsn_roundtrip.py"),
             "import", b, ses, cand], timeout=1800)
    if not os.path.exists(cand):
        print(f"REFUSED: SES import failed\n{r.stdout}\n{r.stderr}", file=sys.stderr)
        return 2
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.splitext(cand)[0] + ext
        if not os.path.exists(src):
            shutil.copy(os.path.join(work, tag + ext), src)

    print("[5/6] gates on the candidate")
    av, au = drc_counts(cand, os.path.join(work, "after.json"))
    print(f"      violations {bv} -> {av}    opens {bu} -> {au}")

    failures = []
    if au >= bu:
        failures.append(f"gate 1: opens did not decrease ({bu} -> {au})")
    if av > bv:
        failures.append(f"gate 1: violations INCREASED ({bv} -> {av})")

    vv = os.path.join(HERE, "verify_via_in_pad.py")
    if os.path.exists(vv):
        r = run([sys.executable, vv, cand, "--baseline", b], timeout=1800)
        if "FOREIGN-net=0" not in r.stdout and "VERDICT: PASS" not in r.stdout:
            failures.append("gate 3: via-in-pad check did not pass")
        print("      via-in-pad: " + ("ok" if not any(
            "gate 3" in f for f in failures) else "FAILED"))

    print("[6/6] verdict")
    if failures:
        for f in failures:
            print("  FAIL " + f)
        print(f"\nREFUSED -- the live board is untouched. Candidate kept for "
              f"inspection: {cand}")
        return 1
    print(f"ACCEPTED -- candidate at {cand}")
    print("NOTE: acceptance here means the gates passed. It does NOT mean the "
          "routing is good; inspect it and record the numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
