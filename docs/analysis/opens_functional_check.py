"""For each of the 5 REAL copper opens: does it terminate on a part that will be FITTED?

The population decision (partial assembly) makes this a real question. An open that ends on a DNP
pad is a bare land with no component on it -- the copper is not connected, but nothing needs
connecting, because there is nothing there. For THIS build that is not a functional defect. For a
future full build it would be.

Prints, per open, the endpoints, whether each endpoint's part is fitted, and the verdict. Does not
assert a reduced count -- it shows the table so the claim can be checked.
"""
import pcbnew as p

BOARD = "docs/analysis/bulk-route-20261107/latest.kicad_pcb"
b = p.LoadBoard(BOARD)
UM = 1e6

DNP = {str(f.GetReference()): str(f.GetFPID().GetLibItemName())
       for f in b.GetFootprints() if f.GetAttributes() & p.FP_EXCLUDE_FROM_BOM}
FIT = {str(f.GetReference()) for f in b.GetFootprints()
       if not (f.GetAttributes() & p.FP_EXCLUDE_FROM_BOM)
       and not str(f.GetFPID().GetLibItemName()).startswith("MountingHole")}

# The 5 REAL opens, as established by the exclusion gate (two-face and GND records excluded).
OPENS = [
    ("/EN",         ["U1", "J_PROG"],  "pad U1.3 -> PTH pad J_PROG.3"),
    ("/SPI2_SCK",   ["U1", "U2"],      "pad U1.4 -> pad U2.12"),
    ("/F33_VSENSE", ["U1"],            "pad U1.21 -> B.Cu track (net sense of the F33)"),
    ("/VSCAP",      ["R_BAL1", "C_CAP1"], "via -> R_BAL1.1 ; zone -> C_CAP1.1 PTH"),
    ("/W2_SOLAR_N", [],                "B.Cu track -> F.Cu track, no via"),
]

print("%-13s %-34s %s" % ("NET", "ENDPOINTS", "VERDICT FOR THIS BUILD"))
print("-" * 96)
functional = 0
nonfunctional = 0
for net, refs, what in OPENS:
    if not refs:
        verdict = "REAL: track-to-track, no part involved"
        functional += 1
        print("%-13s %-34s %s" % (net, what[:34], verdict))
        continue
    dnp_hit = [r for r in refs if r in DNP]
    fit_hit = [r for r in refs if r in FIT]
    detail = " ".join("%s=%s" % (r, "DNP" if r in DNP else "fitted") for r in refs)
    if dnp_hit:
        verdict = "NOT FUNCTIONAL: ends on DNP part -> %s" % detail
        nonfunctional += 1
    else:
        verdict = "FUNCTIONAL: %s" % detail
        functional += 1
    print("%-13s %-34s %s" % (net, what[:34], verdict))

print()
print("FUNCTIONAL opens for this partial build : %d" % functional)
print("open on a DNP part (not fitted)         : %d" % nonfunctional)
print()
print("DNP parts relevant to the opens:")
for r in sorted({r for _, refs, _ in OPENS for r in refs if r in DNP}):
    print("   %-10s %s" % (r, DNP[r]))
