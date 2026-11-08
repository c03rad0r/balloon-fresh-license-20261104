"""How unstable is kicad-cli's unconnected_items output on an UNCHANGED board?

Three consecutive DRC runs on the same file produced different descriptions for the same
defect, which means a naive before/after diff cannot distinguish a board change from noise.
This quantifies it over more runs, and separates the two questions:

  (a) is the COUNT stable?          if not, every "opens decreasing" gate is unreliable
  (b) is the IDENTITY stable?       if not, every "closed X, opened Y" claim is unreliable

Identity is compared on the multiset of DESCRIPTIONS (what a naive diff uses) and, separately,
on the NETS involved (a coarser key that should be stable if the count is).
"""
import json
import re
import subprocess
from collections import Counter

BOARD = "/tmp/refilltest/b.kicad_pcb"
RUNS = 6

counts = []
desc_sets = []
net_sets = []

for i in range(RUNS):
    out = "/tmp/refilltest/stab_%d.json" % i
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json",
                    "--severity-all", "--units", "mm", "--output", out, BOARD],
                   capture_output=True)
    d = json.load(open(out))
    u = d["unconnected_items"]
    counts.append(len(u))
    descs = []
    nets = []
    for v in u:
        items = v.get("items", [])
        descs.append(tuple(sorted(x.get("description", "") for x in items)))
        # net key: pull /NETNAMES out of the descriptions, sorted
        found = []
        for x in items:
            found += re.findall(r"\[(/[^\]]+)\]", x.get("description", ""))
        nets.append(tuple(sorted(set(found))))
    desc_sets.append(sorted(descs))
    net_sets.append(sorted(nets))

print("board: %s (NOT MODIFIED between runs)" % BOARD)
print("runs : %d" % RUNS)
print()
print("(a) RECORD COUNT per run: %s" % counts)
print("    stable: %s" % (len(set(counts)) == 1))
print()
desc_ok = all(d == desc_sets[0] for d in desc_sets)
net_ok = all(n == net_sets[0] for n in net_sets)
print("(b) IDENTITY")
print("    descriptions identical across all runs : %s" % desc_ok)
print("    net-name sets identical across all runs: %s" % net_ok)
print()

if not desc_ok:
    # how many distinct description-variants appear per slot
    allv = Counter()
    for ds in desc_sets:
        for d in ds:
            allv[d] += 1
    unstable = [d for d, n in allv.items() if n < RUNS]
    print("    %d of %d distinct description(s) did not appear in every run:"
          % (len(unstable), len(allv)))
    for d in sorted(unstable)[:10]:
        print("      (x%d) %s" % (allv[d], " || ".join(s[:60] for s in d)))
    print()

if net_ok:
    print("    The NETS involved are stable even though the descriptions are not.")
    print("    => diff on net keys, never on item descriptions.")
else:
    print("    The NETS themselves vary, so even a net-keyed diff is unreliable at this")
    print("    granularity. Count-only comparisons are all that can be trusted.")
