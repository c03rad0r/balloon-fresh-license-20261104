#!/usr/bin/env python3
"""Batch proof for the pressure-controller routing campaign.

Every routing batch must be proven before the next one starts: a batch that adds
copper and does not reduce the open count is a rejection, and a batch that adds ANY
clearance or shorting record is a rejection regardless of how many opens it closed.

WHAT IT REFUSES TO DO
  * it does not trust a total: `unconnected_items` RECORDS are not defects (a pair can be
    reported from both sides) and a total can mask a regression, so the open count is
    normalised to unordered net pairs and reported per net;
  * it does not accept a DRC that failed to run, or a `violations` array read on its own --
    kicad-cli writes opens to `unconnected_items`, NOT to `violations`, so a reader that
    filters `violations` for `unconnected_items` always reports 0 on a board full of opens;
  * it does not accept a candidate without its same-stem `.kicad_pro`, because native DRC
    would then silently use DEFAULT rules rather than the project's.

USAGE
    batch_proof.py --board <board.kicad_pcb> [--baseline <opens.json>] [--expect-open N]

Exit 0 only when: DRC ran, clearance==0, shorting_items==0, copper_edge_clearance==0,
and the normalised open count is <= the baseline (or equals --expect-open when given).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

HARD_BLOCKING = ("clearance", "shorting_items", "copper_edge_clearance",
                 "courtyards_overlap", "hole_to_hole")


def run_drc(board):
    """Run native DRC in JSON and return the parsed document, or raise."""
    stem = os.path.splitext(board)[0]
    pro = stem + ".kicad_pro"
    if not os.path.exists(pro):
        raise SystemExit(f"REFUSED: no same-stem project file at {pro}. Native DRC would "
                         f"silently use DEFAULT rules instead of the project's.")
    out = os.path.join(tempfile.mkdtemp(prefix="batch-drc-"), "drc.json")
    cmd = ["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
           "--units", "mm", "-o", out, board]
    r = subprocess.run(cmd, capture_output=True, text=True)
    # kicad-cli exits 5 when there are violations; that is findings, not process failure.
    if r.returncode not in (0, 5):
        raise SystemExit(f"REFUSED: DRC did not run (exit {r.returncode})\n{r.stdout}\n{r.stderr}")
    if not os.path.exists(out):
        raise SystemExit(f"REFUSED: DRC produced no report (exit {r.returncode})")
    with open(out, encoding="utf-8") as fh:
        return json.load(fh)


def violates(d):
    """Per-type violation counts from the `violations` array."""
    c = Counter()
    for v in d.get("violations", []):
        c[v.get("type", "?")] += 1
    return c


def _net_of(item):
    """Net name of a DRC item.

    THERE IS NO `net` FIELD. `kicad-cli` writes the net only inside the human description
    ("Pad 6 [/+3V3] of U2 on F.Cu"), so a reader that looks for `item["net"]` gets nothing
    and every record collapses to one anonymous key -- measured 2026-11-10: 69 opens
    reported as a single `<no-net>` pair, which is a parse failure masquerading as a clean
    one-net board. Parse the bracket, and keep the raw description when it is absent so an
    unparsed record is visible rather than merged into a fake net.
    """
    desc = item.get("description") or ""
    m = re.search(r"\[([^\]]+)\]", desc)
    if m:
        return m.group(1)
    m = re.search(r"Net\s+(\S+)", desc)
    if m:
        return m.group(1)
    return ""


def normalise_opens(d):
    """Unordered net-pair multiset for `unconnected_items`.

    DESCRIPTIONS are not reproducible between runs on identical bytes (measured: 8 of 14
    variants absent from at least one of six runs), so they are never used as identity.
    The stable identity is the unordered set of net names in the record.
    """
    pairs = Counter()
    for u in d.get("unconnected_items", []):
        nets = set()
        for it in (u.get("items") or []):
            n = _net_of(it)
            if n:
                nets.add(n)
        key = tuple(sorted(nets)) if nets else ("<unparsed>",)
        pairs[key] += 1
    return pairs


def per_net(pairs):
    c = Counter()
    for key, n in pairs.items():
        for name in key:
            c[name] += n
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--baseline", default="",
                    help="previous batch's proof JSON; the open count must not increase")
    ap.add_argument("--expect-open", type=int, default=None,
                    help="exact normalised open count required (mandatory for a CLAIMED "
                         "milestone; omit only for intermediate batches)")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    d = run_drc(args.board)
    v = violates(d)
    opens = normalise_opens(d)
    n_open = sum(opens.values())
    pn = per_net(opens)

    print(f"board        {args.board}")
    print(f"label        {args.label or '(batch)'}")
    print(f"records      opens={n_open} normalised-pairs={len(opens)}")
    print(f"per net      {dict(sorted(pn.items(), key=lambda kv: -kv[1]))}")
    print(f"violations   {dict(v) if v else '{}'}")

    hard = {k: v[k] for k in HARD_BLOCKING if v.get(k)}
    ok = True
    if hard:
        print(f"REJECT  hard violation class present: {hard}")
        ok = False

    baseline = None
    if args.baseline and os.path.exists(args.baseline):
        with open(args.baseline, encoding="utf-8") as fh:
            prev = json.load(fh)
        baseline = prev.get("opens_normalised")
        print(f"baseline     {baseline}")
        # COMPARE PER NET, NOT A TOTAL. A same-net open record carries ONE net name, so all
        # of a net's records collapse into a single unordered-pair key: /GND's 30 records are
        # one pair. Pair counts therefore cannot show a regression inside a net. The stable,
        # comparable identity is the per-net record count (and the total).
        prev_net = prev.get("opens_per_net") or {}
        worse = {k: (prev_net.get(k, 0), n) for k, n in pn.items() if n > prev_net.get(k, 0)}
        if worse:
            print(f"REJECT  opens rose on {worse} (baseline -> now)")
            ok = False
        if baseline is not None and n_open > baseline:
            print(f"REJECT  total open records rose {baseline} -> {n_open}")
            ok = False
    if args.expect_open is not None and n_open != args.expect_open:
        print(f"REJECT  expected exactly {args.expect_open} normalised opens, measured {n_open}")
        ok = False

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"board": args.board, "label": args.label,
                       "opens_normalised": n_open,
                       "opens_pairs": {"/".join(k): n for k, n in opens.items()},
                       "opens_per_net": dict(pn),
                       "violations": dict(v),
                       "hard_blocking": hard,
                       "verdict": "PASS" if ok else "REJECT"}, fh, indent=1)
        print(f"wrote        {args.out}")

    print("VERDICT", "PASS" if ok else "REJECT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
