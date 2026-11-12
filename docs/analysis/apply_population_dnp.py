"""Apply the documented population decision to the board as DNP flags.

SOURCE OF TRUTH: docs/fab/RECOMMENDATIONS-ON-OPEN-DECISIONS.md (2026-10-14), which records the
operator's LOCKED SPLIT plus four recommendations that were accepted:
    D1  U_CUT1-4, U_HUB_CVT -> DNP (order the board as-is, defer the cut channel)
    D3  U5 (GPS), U6 (baro) -> DNP (the LOCKED SPLIT is primary; the old BOM CSV drifted)
    D4  C_CAP1, C_CAP2 (supercaps) -> DNP (the accepted-risk register assumes them unfitted)
    D6  U2 (LoRa2021F33) -> DNP, keep the site (its power is unlawful in DE; optionality retained)

Plus J_VCC, already DNP on the board (a solder jumper; the footprint IS the part).

WHY THE BOARD AND NOT A LIST: a CSV list of DNP references is derived state, and this campaign has
caught six derived artefacts that drifted from the truth. Setting FP_EXCLUDE_FROM_BOM and
FP_EXCLUDE_FROM_POS_FILES makes the board self-describing: kicad-cli already honours both flags, so
the BOM and CPL cannot disagree with the board by construction.

WHAT THIS DOES NOT DO: it does not touch copper, placement, or geometry. Attribute bits only, so
the C10 freeze and the routed board are untouched.
"""
import pcbnew as p
import sys

BOARD = "docs/analysis/bulk-route-20261107/latest.kicad_pcb"

# reference -> (decision id, reason)   Derived from the doc, one line each.
DNP = {
    "U_CUT1":    ("D1", "cut channel deferred; circuit is electrically incomplete (3/6 pads)"),
    "U_CUT2":    ("D1", "cut channel deferred; circuit is electrically incomplete (3/6 pads)"),
    "U_CUT3":    ("D1", "cut channel deferred; circuit is electrically incomplete (3/6 pads)"),
    "U_CUT4":    ("D1", "cut channel deferred; circuit is electrically incomplete (3/6 pads)"),
    "U_HUB_CVT": ("D1", "hub converter deferred; only 3/18 pads connected, cannot function"),
    "U5":        ("D3", "GPS: LOCKED SPLIT says DNP rows + 4 loose (hand-soldered)"),
    "U6":        ("D3", "baro: cabin-pressurised thermal cycling makes its value low"),
    "C_CAP1":    ("D4", "supercap DNP on flight 1; accepted-risk register assumes unfitted"),
    "C_CAP2":    ("D4", "supercap DNP on flight 1; accepted-risk register assumes unfitted"),
    "U2":        ("D6", "F33 PA unlawful at capability in DE (10 mW ERP); keep site for optionality"),
}

b = p.LoadBoard(BOARD)
existing = {str(f.GetReference()): f for f in b.GetFootprints()}

missing = [r for r in DNP if r not in existing]
if missing:
    print("ERROR: references not found on the board: %s" % missing)
    sys.exit(1)

changed = []
for ref, (did, why) in sorted(DNP.items()):
    f = existing[ref]
    before = f.GetAttributes()
    f.SetAttributes(before | p.FP_EXCLUDE_FROM_BOM | p.FP_EXCLUDE_FROM_POS_FILES)
    after = f.GetAttributes()
    if after != before:
        changed.append(ref)
    print("  %-10s %-4s %s" % (ref, did, why))

print()
print("set DNP on %d part(s): %s" % (len(changed), changed))

# Report the resulting population, derived from the board after the change.
pop, dnp = [], []
for f in b.GetFootprints():
    ref = str(f.GetReference())
    if f.GetAttributes() & p.FP_EXCLUDE_FROM_BOM:
        dnp.append(ref)
    elif not str(f.GetFPID().GetLibItemName()).startswith("MountingHole"):
        pop.append(ref)

print()
print("DNP (excluded from BOM and CPL): %d" % len(dnp))
print("  %s" % sorted(dnp))
print()
print("TO BE ASSEMBLED: %d" % len(pop))
print("  %s" % sorted(pop))
print()
print("board also carries %d NPTH mounting holes (no part, never assembled)"
      % len([f for f in b.GetFootprints()
             if str(f.GetFPID().GetLibItemName()).startswith("MountingHole")]))

b.Save(BOARD)
print()
print("saved %s" % BOARD)
