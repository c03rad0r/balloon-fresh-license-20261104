"""BOM derived from the board, grouping identical parts, with the population decision recorded.

Derived from the board, not from a CSV: this campaign has caught six derived artefacts that drifted
from the truth. The board is the primary.
"""
import pcbnew as p
from collections import defaultdict

b = p.LoadBoard("asm.kicad_pcb")

groups = defaultdict(list)
dnp = []
for f in b.GetFootprints():
    ref = str(f.GetReference())
    if f.GetAttributes() & p.FP_EXCLUDE_FROM_BOM:
        dnp.append((ref, str(f.GetFPID().GetLibItemName()), str(f.GetValue() or "")))
        continue
    val = str(f.GetValue() or "")
    pkg = str(f.GetFPID().GetLibItemName())
    groups[(val, pkg)].append(ref)

print("=== TO BE ASSEMBLED (%d placements, %d unique lines) ===" % (
    sum(len(v) for v in groups.values()), len(groups)))
print()
print("%-22s %-30s %-5s %s" % ("VALUE", "PACKAGE", "QTY", "REFERENCES"))
for (val, pkg), refs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0])):
    print("%-22s %-30s %-5d %s" % (val[:22], pkg[:30], len(refs), ", ".join(sorted(refs))))

print()
print("=== NOT ASSEMBLED (DNP, %d sites) ===" % len(dnp))
print("%-10s %-28s %-12s" % ("REF", "PACKAGE", "VALUE"))
for ref, pkg, val in sorted(dnp):
    print("%-10s %-28s %-12s" % (ref, pkg[:28], val[:12]))
