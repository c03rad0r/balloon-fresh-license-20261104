"""Reliable before/after open diff for this board.

WHY THIS EXISTS: kicad-cli's `unconnected_items` descriptions are NOT STABLE between runs on an
unchanged board. Measured over 6 consecutive runs of the same file:

    record count   : [11, 11, 11, 11, 11, 11]        STABLE
    descriptions   : 8 of 14 variants did not appear in every run   UNSTABLE
    net-name sets  : identical in all 6 runs         STABLE

Examples of the same defect described two ways across runs:
    "Pad 4 [/W3_SOLAR_N] of J_W3 on B.Cu || Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu"
    "Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu || Track [/W3_SOLAR_N] on B.Cu, length 3.3004 mm"
    "Track [/W2_SOLAR_N] on B.Cu ... || Track [/W2_SOLAR_N] on F.Cu, length 2.2000 mm"   (x5)
    "Track [/W2_SOLAR_N] on B.Cu ... || Track [/W2_SOLAR_N] on F.Cu, length 1.2000 mm"   (x1)

Consequence: a diff keyed on item descriptions reports phantom "closed 2 / new 2" changes on an
unchanged board. Every such claim made earlier in this campaign is suspect for that reason.

This tool keys on the SET OF NETS in each record, which is stable. It also reports the count,
which is stable, so a genuine change shows up in both.
"""
import json
import re
import subprocess
import sys

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "docs/analysis/bulk-route-20261107/latest.kicad_pcb"
OUT = "/tmp/open_diff_now.json"


def snapshot(board, out):
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "--units", "mm", "--output", out, board], capture_output=True)
    d = json.load(open(out))
    u = d.get("unconnected_items", [])
    recs = []
    for v in u:
        items = v.get("items", [])
        nets = []
        for x in items:
            nets += re.findall(r"\[(/[^\]]+)\]", x.get("description", ""))
        recs.append(tuple(sorted(set(nets))))
    return len(u), recs, d


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("usage: open_diff_relable.py <board>            # describe current state")
        print("       --compare A B                           # compare two boards")
        sys.exit(0)

    n, recs, d = snapshot(BOARD, OUT)
    print("board : %s" % BOARD)
    print("records: %d   pairs by net-key: %d" % (n, len(set(recs))))
    print()
    counts = {}
    for r in recs:
        counts[r] = counts.get(r, 0) + 1
    for r, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print("  x%d  %s" % (c, " | ".join(r) if r else "(no net names)"))
