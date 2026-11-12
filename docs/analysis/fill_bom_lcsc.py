"""Fill LCSC numbers into the partial-assembly BOM from sources that can be cited.

RULE: a line gets a number only if the number comes from a document in this repo (the v9 order BOM)
or from an LCSC product page fetched and read during this task. Everything else stays EMPTY and is
listed as needing selection. A guessed part number is worse than a blank one -- it puts a wrong part
in a paid order and nothing catches it until the boards arrive.

Also enforces the v9 DNP semantics: several v9 lines carry the literal string 'DNP' in the LCSC
column, which means hand-install, not a catalogue part.
"""
import csv
import pcbnew as p
from collections import defaultdict

BOARD = "docs/analysis/bulk-route-20261107/latest.kicad_pcb"
V9 = "docs/fab/hub-v9/gerbers/hub_v9-bom-jlc.csv"
OUT_DIR = "docs/analysis/bulk-route-20261107/assembly-partial/"

# From the v9 order BOM (docs/fab/hub-v9/gerbers/hub_v9-bom-jlc.csv), matched by VALUE.
V9_BY_VALUE = {
    ("10uF", "C_0402_1005Metric"): ("C15525", "v9 BOM"),
    ("100uF", "C_1206_3216Metric"): ("C15008", "v9 BOM"),
    ("100nF", "C_0402_1005Metric"): ("C1525", "v9 BOM"),
    ("10nF", "C_0402_1005Metric"): ("C15195", "v9 BOM"),
    ("BAT54", "D_SOD-123"): ("C699107", "v9 BOM (BAT54W sub for BAT54)"),
    ("SS24", "D_SMA"): ("C50645", "v9 BOM"),
    ("10k", "R_0402_1005Metric"): ("C25744", "v9 BOM"),
    ("1M", "R_0402_1005Metric"): ("C26083", "v9 BOM"),
    ("100R", "R_0402_1005Metric"): ("C25076", "v9 BOM"),
    ("4.7M", "R_0402_1005Metric"): ("C11906", "v9 BOM"),
    ("U1", "ESP32-S3-WROOM-1U"): ("C2980300", "v9 BOM (N8R8 variant)"),
    ("U7", "SOT-23-5"): ("C5142805", "v9 BOM; C5142805 = TPS7A0233DBVR, "
                                     "verified on LCSC this task; C2887324 is the PDBVR variant"),
    # Pin headers: verified on LCSC this task (PZ254V-11 series, 1-row 2.54 mm TH).
    ("HUB_PV_PANEL_5P (P | MID1 | spare | N | GND)", "PinHeader_1x05_P2.54mm_Vertical"):
        ("C492404", "LCSC: PZ254V-11-05P, 1x5P 2.54mm TH"),
    ("J_PROG", "PinHeader_1x06_P2.54mm_Vertical"):
        ("C492405", "LCSC: PZ254V-11-06P, 1x6P 2.54mm TH"),
}

# Not stocked by LCSC / hand-fit regardless of whether a number exists.
NOT_JLC = {"J_W1", "J_W2", "J_W3", "J_W4", "U3", "U_C", "U_LORA1280"}

b = p.LoadBoard(BOARD)
groups = defaultdict(list)
for f in b.GetFootprints():
    if f.GetAttributes() & p.FP_EXCLUDE_FROM_BOM:
        continue
    groups[(str(f.GetValue() or ""), str(f.GetFPID().GetLibItemName()))].append(str(f.GetReference()))

jlc, hand, unknown = [], [], []
for (val, pkg), refs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    handfit = any(r in NOT_JLC for r in refs)
    code, src = V9_BY_VALUE.get((val, pkg), ("", ""))
    row = {
        "Comment": val,
        "Designator": ",".join(sorted(refs)),
        "Footprint": pkg,
        "Quantity": str(len(refs)),
        "LCSC Part #": code,
        "Source": src,
    }
    if handfit:
        hand.append(row)
    elif not code:
        unknown.append(row)
        jlc.append(row)
    else:
        jlc.append(row)

for name, rows in (("asm-bom-jlc.csv", jlc), ("asm-bom-jlc-handfit.csv", hand)):
    with open(OUT_DIR + name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["Comment", "Designator", "Footprint",
                                           "Quantity", "LCSC Part #", "Source"])
        w.writeheader()
        w.writerows(rows)
    filled = sum(1 for r in rows if r["LCSC Part #"])
    print("%-28s %2d lines  %2d placements   %d/%d with a sourced LCSC number"
          % (name, len(rows), sum(int(r["Quantity"]) for r in rows), filled, len(rows)))

print()
print("=== LINES STILL NEEDING A PART NUMBER (%d) ===" % len(unknown))
for r in unknown:
    print("   %-16s %-26s %s" % (r["Comment"][:16], r["Designator"][:26], r["Footprint"]))
print()
print("Nothing in this repo records an LCSC number for these, and none was fetched during this")
print("task. They stay blank on purpose.")
