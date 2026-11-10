#!/usr/bin/env python3
"""NATIVE ERC GATE for the base-station schematic, against a NAMED logical baseline.

WHAT THIS PROVES: the schematic loads in KiCad's own engine, its connectivity is complete
enough for ERC to run, and its violations are exactly the ones the pre-existing logical
source already had -- no new class, no new count.

WHAT IT DOES NOT PROVE: anything about the PCB. The board is a separate, rejected artifact
(143 DRC violations incl. 37 clearance, 63 unconnected, 0 tracks). ERC cannot see copper,
so this gate's green is silent about every one of those.

The baseline is not "zero". It is the 7 single-endpoint nets the generator declares today:
  RF_TEE_MAST   J_LNA_FEED.1     -- coax feed boundary, other end is off-board
  RF_LNA_OUT    TEE1.2          -- masthead LNA output, off-board by design
  RF_COAX_RX    TEE2.1          -- board-side bias tee input, off-board
  RF_2450_TX    J_2450_TX.1     -- 2.45 GHz antenna port, nothing drives it on the PCBA
  VGA_RF_OUT    U_VGA.5         -- VGA output, goes off-board
  USB_DM        U_MCU.46        -- USB data pad with no connector in the v1 BOM
  USB_DP        U_MCU.47        -- same
Each is a real open item in the frozen design, not a transcription artefact: the generator
emits them as single-node nets and KiCad names them label_dangling. They are named here BY
NET so the allowance cannot absorb a different net that happens to have the same count.

Exit codes: 0 == exactly the baseline, 1 == drift (new class/count/net), 2 == could not run.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCH = HERE / "base_station_v1.kicad_sch"

BASELINE = {
    "label_dangling": 7,
}
BASELINE_NETS = {
    "RF_TEE_MAST", "RF_LNA_OUT", "RF_COAX_RX", "RF_2450_TX",
    "VGA_RF_OUT", "USB_DM", "USB_DP",
}
# Why each is allowed, so a reviewer can dispute the reason rather than the number.
BASELINE_WHY = {
    "RF_TEE_MAST": "J_LNA_FEED.1 coax feed to the masthead; the other end is off-board",
    "RF_LNA_OUT": "TEE1.2 masthead LNA output; the LNA is not on the PCBA (freeze row 17)",
    "RF_COAX_RX": "TEE2.1 board-side bias-tee input; fed by the off-board coax",
    "RF_2450_TX": "J_2450_TX.1 2.45 GHz antenna port; no PA and no driver on the PCBA",
    "VGA_RF_OUT": "U_VGA.5 VGA RF output; leaves the board to the receive chain",
    "USB_DM": "U_MCU.46 USB D- pad; no USB connector exists in the v1 BOM",
    "USB_DP": "U_MCU.47 USB D+ pad; no USB connector exists in the v1 BOM",
}


def run_erc(sch: Path):
    """(violations [dict], raw_report_text) or raise SystemExit on a tool failure."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "erc.json"
        r = subprocess.run(["kicad-cli", "sch", "erc", "--severity-all", "--format", "json",
                            "-o", str(out), str(sch)],
                           capture_output=True, text=True, timeout=900)
        if not out.exists():
            raise SystemExit(f"REFUSED: kicad-cli produced no ERC report for {sch.name} "
                             f"(rc={r.returncode})\n{r.stderr[-2000:]}")
        data = json.loads(out.read_text())
    violations = [v for sheet in data.get("sheets", []) for v in sheet.get("violations", [])]
    return violations, data


def classify(violations):
    """{type: n} plus, for label_dangling, the set of net names it fired on."""
    types, nets = {}, set()
    for v in violations:
        types[v["type"]] = types.get(v["type"], 0) + 1
        if v["type"] == "label_dangling":
            for item in v.get("items", []):
                m = re.search(r"Label '([^']+)'", item.get("description", ""))
                if m:
                    nets.add(m.group(1).lstrip("/"))
    return types, nets


def evaluate(violations, verbose=True):
    """Compare a violation list against the named baseline. Returns (ok, failures)."""
    types, nets = classify(violations)
    failures = []
    if "lib_symbol_issues" in types:
        failures.append(f"{types['lib_symbol_issues']} lib_symbol_issues -- a symbol did not "
                        f"resolve; the schematic is not self-contained")
    if "footprint_link_issues" in types:
        failures.append(f"{types['footprint_link_issues']} footprint_link_issues -- a footprint "
                        f"library is missing from the search path")
    for kind, count in sorted(types.items()):
        want = BASELINE.get(kind, 0)
        if count > want:
            failures.append(f"NEW/BEYOND BASELINE: {kind} {count} > {want}")
        elif count < want:
            failures.append(f"BASELINE DRIFT: {kind} {count} < {want} -- the baseline is stale, "
                            f"re-derive it rather than quietly accepting an improvement that "
                            f"may be a lost net")
    extra = sorted(nets - BASELINE_NETS)
    gone = sorted(BASELINE_NETS - nets)
    if extra:
        failures.append(f"label_dangling fired on net(s) not in the named baseline: {extra}")
    if gone:
        failures.append(f"baseline net(s) are no longer dangling: {gone} -- the design changed, "
                        f"so the baseline must be re-derived, not silently re-used")
    if verbose:
        print(f"   ERC classes  : {dict(sorted(types.items())) or 'none'}")
        print(f"   dangling nets: {sorted(nets)}")
    return not failures, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sch", default=str(SCH))
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    if not Path(args.sch).exists():
        print(f"REFUSED: no schematic at {args.sch}")
        return 2
    try:
        violations, _ = run_erc(Path(args.sch))
    except SystemExit as e:
        print(str(e))
        return 2

    print(f"   schematic    : {Path(args.sch).name}")
    print(f"   violations   : {len(violations)}")
    ok, failures = evaluate(violations)
    types, _nets = classify(violations)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "schematic": str(Path(args.sch).resolve()),
            "kicad_cli": subprocess.run(["kicad-cli", "version"], capture_output=True,
                                        text=True).stdout.strip(),
            "violations_total": len(violations),
            "classes": dict(sorted(types.items())),
            "baseline": BASELINE,
            "baseline_nets": {n: BASELINE_WHY[n] for n in sorted(BASELINE_NETS)},
            "within_baseline": ok,
            "failures": failures,
            "not_seen_by_erc": [
                "the PCB: 143 DRC violations including 37 clearance; 63 unconnected; "
                "44 footprints and zero tracks",
                "any copper, placement, impedance or thermal property",
                "whether the generator's logical pin numbers match the ADL5240 / AD8318 / "
                "SAW / load-switch datasheets -- the local symbols are UNVERIFIED",
                "whether the 433 MHz filter, bias tee or detector parts are orderable",
            ],
        }, indent=2) + "\n")
    for f in failures:
        print(f"   FAIL  {f}")
    if failures:
        print("ERC: FAIL")
        return 1
    print(f"ERC: PASS -- {len(violations)} violation(s), all named in the pre-existing logical "
          f"baseline; nothing new, nothing missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
