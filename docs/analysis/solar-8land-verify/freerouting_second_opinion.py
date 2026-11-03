#!/usr/bin/env python3
"""Second-opinion route via FreeRouting, then import ONLY the new copper back.

WHY A SECOND ENGINE
`route_scoped.py` (my A*) closed 2 of 12 remaining pairs and then hit a hard memory ceiling: the
box has ~4 GB and the frontier at 0.10-0.15 mm over a 60 mm span OOMs (rc=137) before the pair set
finishes. FreeRouting is an established DSN-based router already named in
tracker/hardware/PLAN-flight-board-routing.md as the "second opinion / baseline route" tool. It is a
different engine with different memory behaviour and it works on the whole board at once rather than
pair by pair, so it can find corridors a per-pair search misses.

WHAT THIS DOES NOT DO
It does NOT replace the board with FreeRouting's output. FreeRouting may rip up and re-route EVERY
net, which would discard 6 verified solar routes, 37 GND stitches, 12 3V3 taps, the In2 plane, the
/VSCAP taps, the thermal fix and the via upsizing. So the result is compared against the input and
only net-by-net DELTA is considered; nothing is committed until DRC agrees on the merged board.

Steps:
  1. pcbnew ExportSpecctraDSN(input) -> .dsn
  2. java -jar freerouting ... -de in.dsn -do out.ses
  3. pcbnew ImportSpecctraSES(original, out.ses) -> candidate
  4. kicad-cli DRC candidate vs input; report the delta and every new violation class

Usage: freerouting_second_opinion.py <src.kicad_pcb> <workdir> --dru <frozen.kicad_dru>
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

JAR = "/tmp/freerouting_extracted/freerouting-2.2.4-linux-x64/lib/app/freerouting-executable.jar"
JAVA = "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"


def run_drc(pcb, dru, out_json):
    stem = os.path.splitext(pcb)[0]
    shutil.copyfile(dru, stem + ".kicad_dru")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out_json, pcb], capture_output=True, text=True)
    if not os.path.exists(out_json):
        return None, None
    d = json.load(open(out_json))
    from collections import Counter
    return Counter(v["type"] for v in d.get("violations", [])), len(d.get("unconnected_items", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("workdir")
    ap.add_argument("--dru", required=True)
    ap.add_argument("--passes", type=int, default=20)
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)

    if not os.path.exists(JAR):
        print(f"REFUSE: FreeRouting jar missing at {JAR}")
        return 2

    before, ubefore = run_drc(a.src, a.dru, os.path.join(a.workdir, "fr-before.json"))
    dsn = os.path.join(a.workdir, "board.dsn")
    ses = os.path.join(a.workdir, "board.ses")

    b = pcbnew.LoadBoard(a.src)
    if not pcbnew.ExportSpecctraDSN(b, dsn):
        print("REFUSE: ExportSpecctraDSN failed")
        return 2
    print(f"DSN written: {os.path.getsize(dsn)} bytes")

    cmd = [JAVA, "-jar", JAR, "-de", dsn, "-do", ses,
           "-mp", str(a.passes)]
    print("running:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    tail = (r.stdout or "")[-1200:] + (r.stderr or "")[-600:]
    print(tail)
    if not os.path.exists(ses):
        print("REFUSE: no .ses produced; FreeRouting did not finish")
        return 3

    merged = os.path.join(a.workdir, "fr-merged.kicad_pcb")
    b2 = pcbnew.LoadBoard(a.src)
    ok = pcbnew.ImportSpecctraSES(b2, ses)
    print("ImportSpecctraSES:", ok)
    if not ok:
        print("REFUSE: import failed")
        return 3
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    b2.Save(merged)

    after, uafter = run_drc(merged, a.dru, os.path.join(a.workdir, "fr-after.json"))
    print(f"\nBEFORE {dict(before)} unconnected={ubefore}")
    print(f"AFTER  {dict(after)} unconnected={uafter}")
    new = set(after) - set(before)
    print(f"NEW classes: {sorted(new) if new else 'none'}")
    print("\nThis is a CANDIDATE. FreeRouting re-routes every net, so a lower unconnected count does")
    print("NOT by itself justify replacing the board -- the verified solar/GND/3V3 work would be lost.")
    print("Read the delta, then decide net-by-net.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
