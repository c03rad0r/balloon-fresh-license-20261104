#!/usr/bin/env python3
"""SCOPED starved-thermal repair, DRC-graded, refill-first.

Why not `tracker/hardware/clear_starved_thermal.py`: that script sets EVERY pad of an offending
footprint to a SOLID zone connection. Measured on hub_board_v10_lora1280_7of9 on 2026-11-02, that is
16 U_LORA1280 pads including nine signal pads that never touch a zone — and its own gate then FAILED
(starved_thermal 1, because J_PROG.1 was never matched by its `of <REF><digits>` regex). It reports
"nothing changed" or a failed gate while having mutated the wrong copper.

This tool is scoped: it takes explicit REF.PIN targets, from the DRC's own violation items, and
applies the rule the repo already documents (docs/fab/HUB-V9-FULL-ROUTE-RESULT.md): a pad whose short
axis cannot host two thermal spokes is connected SOLID instead of by relief.

Gate (all must hold, else the result is not written):
  starved_thermal == 0 | copper_edge_clearance unchanged | no new error class
  | unconnected unchanged | warnings not increased

Usage: repair_scoped_thermal.py <in.kicad_pcb> <out.kicad_pcb> REF.PIN [REF.PIN ...]
Exit 0 = gate PASS, 1 = gate FAIL or usage error. A PASS is a CANDIDATE, not a fab approval.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
REFILL = os.path.join(REPO, "tracker", "hardware", "refill_zones.py")
SIDECARS = (".kicad_pro", ".kicad_prl", ".kicad_dru")


def copy_sidecars(src, dst):
    for ext in SIDECARS:
        s = os.path.splitext(src)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(dst)[0] + ext)


def refill(src, dst):
    r = subprocess.run(["python3", REFILL, src, dst], capture_output=True, text=True)
    if not os.path.exists(dst):
        print(f"refill failed rc={r.returncode}: {r.stderr[-300:]}")
        return False
    copy_sidecars(src, dst)
    return True


def drc(board):
    out = os.path.splitext(board)[0] + "-drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out, board], capture_output=True, text=True)
    with open(out) as fh:
        d = json.load(fh)
    errs = {}
    for v in d["violations"]:
        if v["severity"] == "error":
            errs[v["type"]] = errs.get(v["type"], 0) + 1
    return {"errors": errs, "total": sum(errs.values()),
            "warnings": sum(1 for v in d["violations"] if v["severity"] == "warning"),
            "unconnected": len(d["unconnected_items"]),
            "starved": [" | ".join(i["description"] for i in v["items"])
                        for v in d["violations"] if v["type"] == "starved_thermal"],
            "json": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("targets", nargs="+")
    a = ap.parse_args()

    base, ext = os.path.splitext(a.dst)
    ctrl_raw, ctrl = f"{base}-ctrl-raw{ext}", f"{base}-ctrl{ext}"
    shutil.copy(a.src, ctrl_raw)
    copy_sidecars(a.src, ctrl_raw)
    if not refill(ctrl_raw, ctrl):
        return 1
    c = drc(ctrl)
    print(f"CONTROL (refilled, untouched): {c['total']} errors "
          f"{json.dumps(c['errors'], sort_keys=True)} warnings {c['warnings']} "
          f"unconnected {c['unconnected']}")
    for s in c["starved"]:
        print(f"   starved: {s}")

    b = pcbnew.LoadBoard(a.src)
    if b is None:
        print("FAIL: could not load source board")
        return 1
    for t in a.targets:
        try:
            ref, pin = t.split(".")
        except ValueError:
            print(f"FAIL: target {t!r} is not REF.PIN")
            return 1
        fp = next((f for f in b.GetFootprints() if f.GetReference() == ref), None)
        if fp is None:
            print(f"FAIL: no footprint {ref}")
            return 1
        pad = next((p for p in fp.Pads() if p.GetNumber() == pin), None)
        if pad is None:
            print(f"FAIL: no pad {ref}.{pin}")
            return 1
        before = pad.GetLocalZoneConnection()
        pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        print(f"  APPLIED {ref}.{pin} net={pad.GetNetname()!r} "
              f"size {pad.GetSize().x / 1e6:.2f}x{pad.GetSize().y / 1e6:.2f} "
              f"zone_connection {before} -> {pad.GetLocalZoneConnection()}")

    raw = f"{base}-raw{ext}"
    pcbnew.SaveBoard(raw, b)
    copy_sidecars(a.src, raw)
    if not refill(raw, a.dst):
        return 1
    f = drc(a.dst)
    print(f"RESULT  (refilled): {f['total']} errors {json.dumps(f['errors'], sort_keys=True)} "
          f"warnings {f['warnings']} unconnected {f['unconnected']}")
    for s in f["starved"]:
        print(f"   starved remains: {s}")

    checks = [
        ("starved_thermal == 0", f["errors"].get("starved_thermal", 0) == 0,
         f["errors"].get("starved_thermal", 0)),
        ("copper_edge_clearance unchanged",
         f["errors"].get("copper_edge_clearance", 0) == c["errors"].get("copper_edge_clearance", 0),
         f"{c['errors'].get('copper_edge_clearance', 0)} -> "
         f"{f['errors'].get('copper_edge_clearance', 0)}"),
        ("no new error class", not (set(f["errors"]) - set(c["errors"])),
         sorted(set(f["errors"]) - set(c["errors"])) or "none"),
        ("unconnected unchanged", f["unconnected"] == c["unconnected"],
         f"{c['unconnected']} -> {f['unconnected']}"),
        ("warnings not increased", f["warnings"] <= c["warnings"],
         f"{c['warnings']} -> {f['warnings']}"),
    ]
    print("\nGATE:")
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:32} {detail}")
        ok = ok and passed
    print("\nGATE: " + ("PASS -- candidate produced (NOT frozen-rule-approved, NOT fab-approved)"
                        if ok else "FAIL -- do not promote"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
