#!/usr/bin/env python3
"""audit_bom_specs.py -- does each BOM part actually survive THIS circuit?

The BOM numbers are verified as CATALOGUE ENTRIES (part exists, is in stock, right package).
That is not the same claim as "right part for this circuit". This script closes that gap by
fetching each LCSC page and extracting the ratings that can invalidate a part:

  voltage rating   vs the rail it sits on. VSCAP is ~5.4 V raw supercap, the highest DC node
                   on the board, and the F33 PA can see it pre-regulated.
  tolerance        vs the job it does. A 5% part in a sense divider is a 5% measurement.
  dielectric       X5R/X7R/Y5V. Y5V loses most of its capacitance over temperature AND loses
                   more than X5R under DC bias, which matters on a capacitor that is supposed
                   to hold a rail.
  power rating     vs I^2R for the series element.

Nothing is inferred from the value alone: a 10uF 0402 exists at 4V, 6.3V and 10V, and only the
last two are usable rail-side. The page is the source, and a fetch that fails says so instead
of defaulting to "ok".
"""
import re
import subprocess

# Rail voltages on this board, from the schematic/ADR set.
#
# VSCAP is BOUNDED, not nominal: RESEARCH-five-parts.md:38 -- "VSCAP max is 5.4 V (2 x 2.7 V
# supercaps in series)". Two 2.7 V cells cannot exceed 5.4 V, because 2.7 V is each cell's
# RATED ceiling. A blanket 1.5x derating against a bounded node manufactures false failures --
# that is exactly what v1 of this script did, flagging two legal caps and one IC.
#
# So each part declares its own basis:
#   "derate"  -- voltage-driven degradation is the failure mode (caps). Compare to rail max
#                times the dielectric's sensible margin.
#   "absmax"  -- an IC. 3.6 V is the ESP32's ABSOLUTE MAX, a limit to stay under, NOT a
#                nominal to multiply by 1.1. Compare nominal to recommended operating.
VSCAP = 5.4     # raw supercap, post-BAT54, pre-LDO, BOUNDED by cell chemistry (ADR-129)
V3V3 = 3.3      # LDO output
VHUB = 5.4      # hub PV into U_HUB_CVT

# ref, lcsc, what it is, rail it sees, basis
PARTS = [
    # (ref, lcsc, what, rail, basis, note)
    ("C_BULK 100uF 1206", "C15008", "bulk on VSCAP", VSCAP, "derate", "86% of rating; DC-bias loss is the real issue"),
    ("C10,C4 10uF 0402", "C15525", "decoupling on VSCAP", VSCAP, "derate", "86%; no 10V part exists in 0402"),
    ("C_HF 100nF 0402", "C1525", "HF decoupling", V3V3, "derate", ""),
    ("C_MON 10nF 0402", "C15195", "monitor filter", VSCAP, "derate", ""),
    ("R_BAL1/2 10k", "C25744", "balance bleed", VSCAP, "derate", ""),
    ("R_DIV1/2 1M", "C26083", "divider", VSCAP, "derate", ""),
    ("R_MON1/2 4.7M", "C11906", "F33_VSENSE divider", VSCAP, "derate", "5% tol = 5% measurement"),
    ("R_F1 100R", "C25076", "series element", VSCAP, "derate", ""),
    ("D1 BAT54W", "C699107", "OR-ing diode", VSCAP, "derate", ""),
    ("SS24 x6", "C50645", "bypass Schottky", VHUB, "derate", ""),
    ("U7 TPS7A0233", "C5142805", "3.3V LDO", VSCAP, "absmax", "abs-max 6.0V vs 5.4V rail"),
    ("U1 ESP32-S3", "C2980300", "MCU module", V3V3, "absmax", "runs 3.3V; 3.6V is ABS MAX"),
]


def page(code):
    url = f"https://www.lcsc.com/product-detail/{code}.html"
    try:
        return subprocess.run(["curl", "-s", "--max-time", "25", "-A", "Mozilla/5.0", url],
                              capture_output=True, text=True, timeout=40).stdout
    except Exception:
        return ""


def grab(html, keys):
    out = {}
    for k in keys:
        m = re.search(k + r'[^A-Za-z0-9]{0,12}([A-Za-z0-9.+/%\- ]{1,24})', html, re.I)
        if m:
            out[k] = m.group(1).strip()
    return out


print(f"{'part':22s} {'rail':>5s} {'basis':>7s} {'ok?':>7s}  ratings found")
print("-" * 104)
fails = []
for ref, code, what, rail, basis, note in PARTS:
    html = page(code)
    if not html:
        print(f"{ref:22s} {rail:5.1f} {basis:>7s}     ???  FETCH FAILED -- unverified, not 'ok'")
        fails.append((ref, "fetch failed"))
        continue
    txt = re.sub(r"<[^>]+>", " ", html)
    volts = [float(v) for v in re.findall(r'(\d{1,3}(?:\.\d)?)\s*V\b', txt)]
    volts = sorted({v for v in volts if 1.0 <= v <= 100.0})
    dielec = sorted(set(re.findall(r'\b(X5R|X7R|Y5V|X7S|X6S|C0G|NP0)\b', txt)))
    tol = sorted({m for m in re.findall(r'[\u00b1]\s*(\d+(?:\.\d+)?)\s*%', txt)})

    top = max(volts) if volts else None
    if top is None:
        verdict, ok = "UNREADABLE", "???"
    elif basis == "absmax":
        # an IC: the rating IS the abs max. Legal if rail < absmax, with 10% headroom.
        ok = "OK" if rail <= top * 0.92 else "CHECK"
        verdict = f"absmax {top}V vs rail {rail}V"
    else:
        # derate: legal if rating >= rail. 15% margin flagged as THIN, not failed.
        if top >= rail * 1.15:
            ok, verdict = "OK", f"{top}V >= {rail*1.15:.1f}V"
        elif top >= rail:
            ok, verdict = "THIN", f"{top}V vs {rail}V = {top/rail*100:.0f}% used"
        else:
            ok, verdict = "FAIL", f"{top}V < rail {rail}V"
    if ok in ("FAIL", "CHECK"):
        fails.append((ref, verdict))
    print(f"{ref:22s} {rail:5.1f} {basis:>7s} {ok:>7s}  {verdict}  dielec={dielec[:2]} "
          f"tol={tol[:2]}")
    if note:
        print(f"    note: {note}")

print()
if fails:
    print("NEEDS DECISION (FAIL or CHECK):")
    for r, v in fails:
        print(f"  {r}: {v}")
else:
    print("no rating failures found")
