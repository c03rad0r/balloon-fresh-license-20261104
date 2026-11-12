#!/usr/bin/env python3
"""route_guarded.py -- route one net, then ACCEPT ONLY IF DRC SAYS IT IS LEGAL.

WHY THIS EXISTS
---------------
route_batch.py routes and self-reports `agreement_ok: true` when its own A* grid and its own
validator agree. That is a statement about the router, not about the board. Measured on this
board, 2026-11-09:

    /IO0  routed 28 segments, 6 vias, 41.4 mm, agreement_ok TRUE
          -> kicad-cli DRC: 16 -> 18 violations, both `shorting_items`,
             /IO0 on B.Cu shorting to /USB_DN on B.Cu, in two places

A boot-strapping line shorted to USB D- can damage the ESP32 while flashing. The router's own
agreement check cannot see it, because the short is between two nets the router never compared.

So the acceptance test is not the router's report. It is:
    1. route the net
    2. run kicad-cli DRC on the RESULT
    3. reject if violations rose, or if any violation is a short / clearance / track-width item
       that was not already present in the baseline
    4. reject if the net is still unconnected (the route bought nothing)

Anything rejected leaves the previous board untouched. A rejected net is a fact to report, not a
result to ship.

Usage:
  route_guarded.py <board> --net /EN --a U1.3 --b J_PROG.3 [--deadline 400] [--pitch 0.08]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

# Violation types that make a route unacceptable when they are NEW.
FATAL = {"shorting_items", "clearance", "track_width", "via_diameter", "drill_out_of_range",
         "copper_edge_clearance", "solder_mask_bridge"}


def drc(board, out_json):
    r = subprocess.run(
        ["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm",
         "--output", out_json, board],
        capture_output=True, text=True, timeout=1800)
    if not os.path.exists(out_json):
        return None
    d = json.load(open(out_json))
    viol = d.get("violations", [])
    types = {}
    for v in viol:
        types[v.get("type", "?")] = types.get(v.get("type", "?"), 0) + 1
    return dict(n=len(viol), types=types, unconn=len(d.get("unconnected_items", [])), raw=d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--net", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--deadline", type=float, default=400.0)
    ap.add_argument("--pitch", type=float, default=0.08)
    ap.add_argument("--keepout", action="append", default=[])
    args = ap.parse_args()

    board = args.board
    workdir = os.path.dirname(os.path.abspath(board))
    stem = os.path.splitext(os.path.basename(board))[0]
    cand = os.path.join(workdir, f"{stem}.cand.kicad_pcb")
    rep = os.path.join(workdir, f"{stem}.cand.report.json")

    # DELETE any previous candidate FIRST. Measured 2026-11-09: an UNROUTED run left the prior
    # candidate on disk and step 3 DRC'd that stale board, reporting the previous run's shorts as
    # if they were this run's. Same defect class as the stale-baseline proof that once certified
    # a router no-op elsewhere in this repo.
    for stale in (cand, rep):
        if os.path.exists(stale):
            os.remove(stale)

    # sidecars so DRC uses the same rules as the board of record
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.join(workdir, f"{stem}{ext}")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(workdir, f"{stem}.cand{ext}"))

    print(f"[1/4] baseline DRC on {os.path.basename(board)}")
    base = drc(board, os.path.join(workdir, f"{stem}.base.drc.json"))
    if base is None:
        print("FAIL: baseline DRC produced no output; refusing to route blind")
        return 2
    print(f"      baseline: {base['n']} violations {base['types']}, {base['unconn']} unconnected")

    print(f"[2/4] routing {args.net} {args.a} -> {args.b} (pitch {args.pitch}, "
          f"deadline {args.deadline}s)")
    cmd = ["/usr/bin/python3", "tracker/hardware/route_batch.py", board,
           "--pair", f"{args.net}:{args.a}:{args.b}",
           "--pitch", str(args.pitch), "--deadline", str(args.deadline),
           "--out", cand, "--report", rep]
    for ko in args.keepout:
        cmd += ["--keepout", ko]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(args.deadline) + 900)
    tail = [ln for ln in (r.stdout or "").splitlines()
            if "applied" in ln or "UNROUTED" in ln or "ROUTED" in ln]
    print("      " + ("; ".join(tail) if tail else (r.stdout or "")[-200:]))

    pr = {}
    if os.path.exists(rep):
        pr = json.load(open(rep))
        p0 = (pr.get("pairs") or [{}])[0]
        print(f"      router: {p0.get('result')} segs={p0.get('segments')} "
              f"vias={p0.get('vias')} len={p0.get('length_mm')}")
    if not os.path.exists(cand):
        print("      REJECT: router produced no board (net did not route)")
        return 1
    if pr.get("pairs") and (pr["pairs"][0].get("result") != "ROUTED"):
        print(f"      REJECT: router reported {pr['pairs'][0].get('result')}; "
              f"not DRC-ing a candidate that was never produced")
        return 1

    print("[3/4] DRC on the ROUTED board -- this is the acceptance test")
    got = drc(cand, os.path.join(workdir, f"{stem}.cand.drc.json"))
    if got is None:
        print("      REJECT: DRC produced no output")
        return 1
    print(f"      routed: {got['n']} violations {got['types']}, {got['unconn']} unconnected")

    print("[4/4] verdict")
    if got["unconn"] >= base["unconn"]:
        print(f"      REJECT: unconnected did not fall ({base['unconn']} -> {got['unconn']}); "
              f"the route bought nothing")
        return 1

    new_fatal = {t: c for t, c in got["types"].items()
                 if t in FATAL and c > base["types"].get(t, 0)}
    if new_fatal:
        print(f"      REJECT: NEW illegal copper {new_fatal}")
        print("      the router's agreement check passed; kicad-cli disagrees. Not shipped.")
        return 1
    if got["n"] > base["n"]:
        print(f"      REJECT: violations rose {base['n']} -> {got['n']}")
        return 1

    print(f"      ACCEPT: unconnected {base['unconn']} -> {got['unconn']}, "
          f"violations {base['n']} -> {got['n']}, no new fatal types")
    shutil.copy(cand, board)
    print(f"[done] {board} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
