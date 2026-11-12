#!/usr/bin/env python3
"""verify_batch.py -- per-batch proof for the pressure-controller core route.

The referee is native `kicad-cli pcb drc`, parsed as JSON -- never a grep of a text report and
never a custom count that could disagree with it. What is reported, per batch:

  opens_before / opens_after          native unconnected_items record count
  opens_by_net_after                  per net, from the DRC records themselves
  nets_closed / nets_opened           set difference on net names, not on totals
  previously_connected_pairs_broken   pad-pair connectivity via pcbnew's own connectivity
                                      engine, compared as a SET of pad pairs, so a pair that
                                      was joined and then cut cannot hide in an unchanged total
  shorts / clearance / other          every violation class, named, count per class
  new_violations                      each new record listed individually with its items

A batch that does not strictly decrease opens, or that breaks any previously-connected pair,
or that introduces a short/clearance record, FAILS.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

import pcbnew

UM = 1_000_000


def drc(board, out):
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", out, board],
                   check=True, capture_output=True)
    return json.load(open(out))


def net_of(item):
    m = re.search(r"\[(.*?)\]", item["description"])
    return m.group(1) if m else ""


def opens_by_net(records):
    c = collections.Counter()
    for r in records:
        nets = {net_of(i) for i in r["items"]}
        for n in nets:
            c[n] += 1
    return dict(c)


def connected_pairs(board):
    """Every pad pair the board's own connectivity engine says are joined.

    Identity is (reference, pad number, pad uuid) so duplicated pad numbers (stacked pads,
    multi-pad switch terminals) cannot alias each other.
    """
    b = pcbnew.LoadBoard(board)
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    pairs = set()
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if not p.GetNumber():
                continue
            a = (fp.GetReference(), p.GetNumber(), p.m_Uuid.AsString())
            for q in conn.GetConnectedPads(p):
                fq = q.GetParentFootprint()
                d = (fq.GetReference(), q.GetNumber(), q.m_Uuid.AsString())
                if a != d:
                    pairs.add(tuple(sorted((a, d))))
    return pairs


def describe(v):
    return {"type": v["type"], "severity": v.get("severity"),
            "description": v["description"],
            "items": [i["description"] for i in v.get("items", [])]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--before", required=True, help="previous batch board")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow", default="lib_footprint_mismatch",
                    help="comma-separated violation types tolerated (declared, not blanket)")
    a = ap.parse_args()

    allow = {s for s in a.allow.split(",") if s}
    d_after = drc(a.board, os.path.splitext(a.out)[0] + "-drc-after.json")
    d_before = drc(a.before, os.path.splitext(a.out)[0] + "-drc-before.json")

    opens_before = len(d_before["unconnected_items"])
    opens_after = len(d_after["unconnected_items"])
    by_before = opens_by_net(d_before["unconnected_items"])
    by_after = opens_by_net(d_after["unconnected_items"])

    pairs_before = connected_pairs(a.before)
    pairs_after = connected_pairs(a.board)
    broken = sorted(pairs_before - pairs_after)

    cnt_after = collections.Counter(v["type"] for v in d_after["violations"] if v["type"])
    cnt_before = collections.Counter(v["type"] for v in d_before["violations"] if v["type"])
    hard = ("shorting_items", "clearance", "tracks_crossing", "copper_edge_clearance",
            "hole_clearance", "hole_to_hole", "courtyards_overlap", "starved_thermal",
            "unconnected_items")
    hard_after = {k: v for k, v in cnt_after.items() if k in hard}
    unexpected = {k: v for k, v in cnt_after.items() if k not in allow and k not in hard}

    sig_before = collections.Counter(
        json.dumps(describe(v), sort_keys=True) for v in d_before["violations"])
    sig_after = collections.Counter(
        json.dumps(describe(v), sort_keys=True) for v in d_after["violations"])
    new_records = list((sig_after - sig_before).elements())
    gone_records = list((sig_before - sig_after).elements())

    verdict = []
    if opens_after >= opens_before:
        verdict.append(f"FAIL opens did not strictly decrease ({opens_before}->{opens_after})")
    if broken:
        verdict.append(f"FAIL {len(broken)} previously-connected pair(s) broken")
    if hard_after:
        verdict.append(f"FAIL hard violation classes present {hard_after}")
    if unexpected:
        verdict.append(f"FAIL unexpected violation classes {unexpected}")

    proof = {
        "label": a.label,
        "board": {"path": os.path.abspath(a.board),
                  "sha256": __import__("hashlib").sha256(open(a.board, "rb").read()).hexdigest(),
                  "bytes": os.path.getsize(a.board)},
        "before": {"path": os.path.abspath(a.before), "opens": opens_before,
                   "violations": dict(cnt_before)},
        "after": {"opens": opens_after, "violations": dict(cnt_after)},
        "opens_delta": opens_after - opens_before,
        "opens_by_net_before": by_before,
        "opens_by_net_after": by_after,
        "nets_closed": sorted({n for n in by_before if n not in by_after}),
        "nets_improved": sorted(n for n in by_after if n in by_before and by_after[n] < by_before[n]),
        "nets_worsened": sorted(n for n in by_after if n in by_before and by_after[n] > by_before[n]),
        "nets_opened": sorted({n for n in by_after if n not in by_before}),
        "connected_pad_pairs_before": len(pairs_before),
        "connected_pad_pairs_after": len(pairs_after),
        "previously_connected_pairs_broken": [
            {"a": list(x[0]), "b": list(x[1])} for x in broken],
        "shorts": cnt_after.get("shorting_items", 0),
        "clearance": cnt_after.get("clearance", 0),
        "tolerated_violation_types": sorted(allow),
        "new_violation_records": [json.loads(s) for s in new_records],
        "cleared_violation_records": [json.loads(s) for s in gone_records],
        "verdict": verdict or ["PASS"],
    }
    json.dump(proof, open(a.out, "w"), indent=1)
    print(json.dumps({k: proof[k] for k in
                      ("label", "opens_delta", "after", "nets_closed", "nets_opened",
                       "previously_connected_pairs_broken", "new_violation_records",
                       "verdict")}, indent=1))
    return 0 if not verdict else 1


if __name__ == "__main__":
    sys.exit(main())
