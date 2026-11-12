"""Did the VSCAP via actually change anything? Judge with a noise-tolerant comparison.

Both boards are measured 4 times. Because descriptions vary run to run, a single
before/after pair proves nothing; the question is whether the MULTISET OF NET-KEYS differs
more between the two boards than it does between repeated runs of the SAME board.

If the two boards' key-multisets are within the noise, the via changed nothing and must be
reverted rather than claimed as a win.
"""
import json
import re
import subprocess
from collections import Counter

BASE = "/tmp/refilltest/b.kicad_pcb"
VIA = "/tmp/refilltest/vscapvia.kicad_pcb"
RUNS = 4


def keys(board, tag):
    out = []
    for i in range(RUNS):
        f = "/tmp/refilltest/cmp_%s_%d.json" % (tag, i)
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                        "--units", "mm", "--output", f, board], capture_output=True)
        d = json.load(open(f))
        u = d.get("unconnected_items", [])
        ks = []
        for v in u:
            nets = []
            for x in v.get("items", []):
                nets += re.findall(r"\[(/[^\]]+)\]", x.get("description", ""))
            ks.append(tuple(sorted(set(nets))))
        out.append((len(u), Counter(ks), d.get("violations", [])))
    return out


print("measuring baseline %d times..." % RUNS)
base = keys(BASE, "base")
print("measuring via board %d times..." % RUNS)
via = keys(VIA, "via")

print()
print("=== record counts ===")
print("  baseline : %s" % [r[0] for r in base])
print("  via      : %s" % [r[0] for r in via])

print()
print("=== net-key multisets, per run ===")
for tag, runs in (("baseline", base), ("via", via)):
    print("  %s:" % tag)
    for i, (n, c, _) in enumerate(runs):
        print("    run%d: %d records, keys %s" % (i, n, dict(sorted(c.items()))))

# Is the two-board difference larger than the same-board spread?
base_sets = {tuple(sorted(r[1].items())) for r in base}
via_sets = {tuple(sorted(r[1].items())) for r in via}
print()
print("  distinct key-multisets within BASELINE runs: %d" % len(base_sets))
print("  distinct key-multisets within VIA runs     : %d" % len(via_sets))
overlap = base_sets & via_sets
print("  multisets common to BOTH boards            : %d" % len(overlap))
if overlap:
    print()
    print("  RESULT: the via board's open signature is INDISTINGUISHABLE from the baseline's")
    print("          within run-to-run noise. The via closed nothing. Revert it.")
else:
    print()
    print("  RESULT: the signatures differ in every run -- the via DID change the open set.")
    b = base[0][1]
    v = via[0][1]
    print("          baseline-only keys: %s" % dict(b - v))
    print("          via-only keys     : %s" % dict(v - b))
