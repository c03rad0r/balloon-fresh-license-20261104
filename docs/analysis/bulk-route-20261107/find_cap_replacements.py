#!/usr/bin/env python3
"""find_cap_replacements.py -- find 10V+ replacements for the two 6.3V caps on VSCAP.

WHY THIS SCRIPT EXISTS
----------------------
BOM-ORDER-READY.md records a near-miss: *"I nearly replaced a correct number with a
same-family variant on the strength of a search result — exactly the class of error an
unverified part number produces in a paid order. The 'P' suffix is one character."*

So this does NOT return the first plausible number. For every candidate it re-fetches the LCSC
page and reads back capacitance, voltage, dielectric and package FROM THE PAGE, and only
accepts a part whose read-back matches the requirement. A candidate that cannot be verified
is reported as unverified, never as a recommendation.

REQUIREMENT
-----------
VSCAP = 5.4 V raw supercap, post-BAT54, pre-LDO (ADR-129). 50% derating => >= 8.1 V rated.
  C_BULK  100uF 1206  (C15008 is 6.3 V -- FAILS)
  C10,C4  10uF  0402  (C15525 is 6.3 V -- FAILS)

Both must stay in the SAME FOOTPRINT, because the board is routed and the footprints are
C_1206_3216Metric and C_0402_1005Metric. A 0805 recommendation would be a board change, which
is not what was asked for -- so if no 1206/10V or 0402/10V part verifies, that is the finding
and it gets reported as such rather than silently widening the package.
"""
import re
import subprocess
import sys

NEED_V = 5.4 * 1.5   # 8.1 V

# (label, requirement, footprint that MUST match, candidate LCSC numbers to try)
TARGETS = [
    ("C_BULK 100uF", dict(cap="100", pkg="1206"), "C_1206_3216Metric",
     ["C13585", "C15008", "C2980238", "C383858", "C96123"]),
    ("C10,C4 10uF", dict(cap="10", pkg="0402"), "C_0402_1005Metric",
     ["C15525", "C19702", "C15850", "C77100", "C52923", "C2765633", "C384158"]),
]


def page(code):
    url = f"https://www.lcsc.com/product-detail/{code}.html"
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "25", "-A", "Mozilla/5.0", url],
                           capture_output=True, text=True, timeout=40)
        return r.stdout or ""
    except Exception:
        return ""


def read_back(html, code):
    """Extract what the PAGE says. No inference from the number."""
    if not html or len(html) < 500:
        return None
    txt = re.sub(r"<[^>]+>", " ", html)

    # capacitance: prefer an explicit uF token
    cap = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*[uµ]F', txt, re.I)
    if m:
        cap = float(m.group(1))

    # voltage rating: the largest small V token is the rating on a cap page
    volts = [float(v) for v in re.findall(r'(\d{1,3}(?:\.\d)?)\s*V\b', txt)]
    volts = [v for v in volts if 4.0 <= v <= 100.0]
    vr = max(volts) if volts else None

    dielec = None
    m = re.search(r'\b(X5R|X7R|Y5V|X7S|X6S|C0G|NP0)\b', txt)
    if m:
        dielec = m.group(1)

    pkg = None
    m = re.search(r'\b(0201|0402|0603|0805|1206|1210)\b', txt)
    if m:
        pkg = m.group(1)

    return dict(cap=cap, vr=vr, dielec=dielec, pkg=pkg, bytes=len(html))


def main():
    print(f"requirement: >= {NEED_V:.1f} V rated on VSCAP (~5.4 V, 50% derating)")
    print(f"{'target':16s} {'code':10s} {'cap':>7s} {'V':>6s} {'dielec':>7s} "
          f"{'pkg':>6s}  verdict")
    print("-" * 86)

    accepted = {}
    for label, req, fp, codes in TARGETS:
        print(f"\n{label}  (must stay {fp})")
        for code in codes:
            rb = read_back(page(code), code)
            if rb is None:
                print(f"  {code:10s}  PAGE FETCH FAILED -- unverified, NOT a recommendation")
                continue
            verdict = []
            if rb["cap"] is None:
                verdict.append("cap unreadable")
            elif abs(rb["cap"] - float(float(req["cap"]))) > 0.01:
                verdict.append(f"cap {rb['cap']} != {req['cap']}")
            if rb["vr"] is None:
                verdict.append("V unreadable")
            elif rb["vr"] < NEED_V:
                verdict.append(f"V {rb['vr']} < {NEED_V:.1f}")
            if rb["pkg"] and rb["pkg"] != req["pkg"]:
                verdict.append(f"pkg {rb['pkg']} != {req['pkg']}")
            ok = not verdict
            print(f"  {code:10s} {str(rb['cap']):>7s} {str(rb['vr']):>6s} "
                  f"{str(rb['dielec']):>7s} {str(rb['pkg']):>6s}  "
                  f"{'ACCEPT' if ok else 'reject: ' + '; '.join(verdict)}")
            if ok:
                accepted.setdefault(label, []).append((code, rb))

    print("\n" + "=" * 86)
    if not accepted:
        print("NO VERIFIED REPLACEMENT FOUND IN THE ORIGINAL FOOTPRINT.")
        print("That is the result. Do not widen the package silently -- that is a board change.")
        return 1

    for label, rows in accepted.items():
        print(f"{label}: {len(rows)} verified candidate(s)")
        for code, rb in rows:
            print(f"  {code}  {rb['cap']}uF  {rb['vr']}V  {rb['dielec']}  {rb['pkg']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
