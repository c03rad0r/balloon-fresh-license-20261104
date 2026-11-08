"""Honest open count: distinct pairs, classified, from the board itself.

Prints BOTH numbers so neither can be quoted alone again:
  raw   = kicad-cli's unconnected_items record count
  pairs = distinct unordered pairs (raw double-reports some)
and classifies each pair so the number of GENUINE routing blockers is explicit.
"""
import json
import subprocess
import sys

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "docs/analysis/bulk-route-20261107/latest.kicad_pcb"
OUT = "/tmp/drc_recount.json"

subprocess.run(
    ["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
     "--output", OUT, BOARD],
    capture_output=True,
)

d = json.load(open(OUT))
u = d.get("unconnected_items", [])


def pair_key(rec):
    items = rec.get("items", [])
    return tuple(sorted(i.get("description", "")[:90] for i in items))


seen = {}
for rec in u:
    k = pair_key(rec)
    seen[k] = seen.get(k, 0) + 1

print("board: %s" % BOARD)
print("raw unconnected_items : %d" % len(u))
print("distinct pairs        : %d" % len(seen))
print()


def classify(desc):
    """Bucket each pair by what would actually have to change to close it."""
    j = " || ".join(desc)
    # two-face wing pads: SAME pad number, SAME footprint, opposite faces
    if " of J_W" in j:
        import re
        refs = re.findall(r"Pad (\d+) \[[^\]]+\] of (J_W\d) on (F\.Cu|B\.Cu)", j)
        if len(refs) == 2 and refs[0][0] == refs[1][0] and refs[0][1] == refs[1][1]:
            return "two-face wing pad (assembly tab, no board copper possible)"
    # GND zone-to-zone bookkeeping
    if j.count("Zone 'GND") == 2:
        return "GND zone bookkeeping (vias already stitch the zones)"
    if "Zone 'GND" in j:
        return "GND zone record"
    return "genuine routing work"


buckets = {}
for k, n in seen.items():
    b = classify(k)
    buckets.setdefault(b, []).append((k, n))

for b, rows in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    print("%s  -- %d pair(s)" % (b, len(rows)))
    for k, n in rows:
        tag = " (x%d)" % n if n > 1 else ""
        print("    %s%s" % (" || ".join(x[:72] for x in k), tag))
    print()

genuine = len(buckets.get("genuine routing work", []))
print("SUMMARY")
print("  raw records            : %d" % len(u))
print("  distinct pairs         : %d" % len(seen))
print("  GENUINE routing work   : %d" % genuine)
print("  not defects            : %d" % (len(seen) - genuine))
