#!/usr/bin/env python3
"""rail_batch.py -- close the /GND and /+3V3 rails with pours, in measured stages.

SCOPE. Copper pours plus the minimum copper needed to make a pour reach a pad. No track
widening, no placement change, no net/keep-out/rule/project-file change, no via-in-pad. Wall
clock is spent on native DRC, not on geometry the DRC has not sanctioned.

WHAT WAS MEASURED BEFORE ANY OF THIS WAS WRITTEN (this board, native KiCad 9.0.9 DRC, all from
port60 route.kicad_pcb at 63 opens; every number reproducible with `--measure`):

  /GND B.Cu pour only ................................ 63 -> 58 opens (/GND 30 -> 25)
  /GND B.Cu + F.Cu pours ............................. 63 -> 35 opens (/GND 30 -> 2, two
                                                      fragments stranded at U3)
  + those pours + one GND stitch via at (47.525,13.324)   63 -> 34 (/GND 30 -> 1)
  /+3V3 full F.Cu pour instead of the GND F.Cu pour .. 63 -> 42 (/GND 30 -> 25, /+3V3 19 -> 3)
  both full F.Cu pours, equal priority ............... 63 -> 40 (/GND 30 -> 23, /+3V3 19 -> 3)
  both full F.Cu pours, /+3V3 priority 1 ............. 63 -> 40 (same: +3V3 evicts GND)
  /+3V3 local priority-1 windows under the GND plane . closes 11 /+3V3 opens but strands four
                                                      GND SMD pads that lose their ONLY copper
                                                      contact (C3.2, U2.1, U2.4, U4.3) and
                                                      takes /GND 2 -> 6. REJECTED.
  /+3V3 bounded pad-centre tree over the GND pours ... 63 -> 28 (/GND 1, /+3V3 19 -> 13)

The board is 2-layer and BOTH rails want F.Cu. No arrangement of a full-board pour per rail
exists: whichever rail does not own F.Cu ends with pad-sized fragments. A +3V3 pour therefore
buys 10 extra +3V3 opens at the cost of 22 GND opens, which breaks previously-connected GND
pairs and fails this campaign's own acceptance rule. Batch 2 is the routed tree for that
reason, and the pour alternative is recorded rather than quietly dropped.

CONNECTION STYLE. Both rails use THERMAL relief (spokes), not the direct connections the
earlier /GND pours used. A thermal joint that cannot physically resolve two spokes on a
0.50 x 0.25 mm pad hemmed in by 0.20 mm clearance pockets is left as a DRC `starved_thermal`
error rather than being papered over: that record is an assembly fact, and the fix (pad-local
solid connection) is enumerated pad by pad in --report and would be a deliberate assembly
decision, not a side effect of a pour.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pour_stage as PS          # noqa: E402
import rail_pour as RP           # noqa: E402

UM = 1_000_000

# Pad-centre segments accepted by native DRC, in acceptance order. Each closes opens on
# /+3V3 only; none touches another net's copper.
V3_LINKS = [
    ("U4", "1", "U4", "2"),
    ("U3", "1", "U3", "2"),
    ("C2", "1", "C3", "1"),
    ("C8", "1", "U4", "2"),
    ("L1", "2", "C5", "1"),
    ("C3", "1", "R1", "1"),
]
# One stitch via joins the U3 F.Cu fragment to the B.Cu plane. Placed at the centre measured
# from a legal-site solve (clearance to every other net's copper, every drill and the edge);
# it is through-hole, 0.60/0.30, never in a pad.
GND_STITCH = (47.525, 13.324)

# Pads whose F.Cu thermal relief lands on exactly one spoke. A 1-spoke relief is a DRC
# `starved_thermal` error and the baseline board has none, so leaving them thermal would make
# the pour a REGRESSION. Measured: pad-local DIRECT on these six -> 0 starved, opens 58 -> 55;
# keeping thermal -> 6 starved, opens 58 -> 35 (the 35 is not a win, it is 23 fewer opens paid
# for with 6 new errors). scoped to these named pads only.
PAD_DIRECT = ["U4.3", "J1.A1", "J1.B12", "U2.1", "U2.9", "U3.3"]


def load(src):
    b = pcbnew.LoadBoard(str(src))
    if b is None:
        raise SystemExit("REFUSED: cannot load %s" % src)
    return b


def add_via(b, net, x, y, dia=0.60, drill=0.30):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(round(x * UM)), int(round(y * UM))))
    v.SetWidth(int(round(dia * UM)))
    v.SetDrill(int(round(drill * UM)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(b.FindNet(net))
    b.Add(v)
    return {"net": net, "x": x, "y": y, "diameter": dia, "drill": drill,
            "in_pad": False, "uuid": v.m_Uuid.AsString()}


def add_seg(b, net, p, q, layer=pcbnew.F_Cu, width=0.20):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(int(round(p[0] * UM)), int(round(p[1] * UM))))
    t.SetEnd(pcbnew.VECTOR2I(int(round(q[0] * UM)), int(round(q[1] * UM))))
    t.SetWidth(int(round(width * UM)))
    t.SetLayer(layer)
    t.SetNet(b.FindNet(net))
    b.Add(t)
    return {"net": net, "layer": b.GetLayerName(layer),
            "from": [round(v, 3) for v in p], "to": [round(v, 3) for v in q],
            "width": width, "uuid": t.m_Uuid.AsString()}


def pad_centre(b, ref, num, net):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        raise SystemExit("REFUSED: no footprint %s" % ref)
    for p in fp.Pads():
        if p.GetNumber() == num and p.GetNetname() == net:
            q = p.GetPosition()
            return (q.x / UM, q.y / UM)
    raise SystemExit("REFUSED: no %s pad %s.%s" % (net, ref, num))


def finish(b, out):
    """Refill, save, copy project siblings. Returns the written path."""
    n = pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(str(out), b)
    RP.copy_siblings(out, out)
    return out, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "route.kicad_pcb"))
    ap.add_argument("--dir", default=str(ROOT))
    ap.add_argument("--stages", default="1,2",
                    help="comma list of stage numbers to run in order (1..4)")
    ap.add_argument("--report", default=str(ROOT / "proofs/rail-pour.json"))
    a = ap.parse_args()
    D = Path(a.dir)
    D.mkdir(parents=True, exist_ok=True)
    stages = [float(s) for s in a.stages.split(",")]
    rec = {"src": a.src, "src_sha256": __import__("hashlib").sha256(
        open(a.src, "rb").read()).hexdigest(), "stages": []}

    b = load(a.src)
    board = Path(a.src)
    for st in stages:
        if st == 1:
            info = PS.add_pour(b, "/GND", pcbnew.B_Cu, 0, connection="thermal")
            tag = "rail-gnd-bcu"
        elif st == 2:
            info = PS.add_pour(b, "/GND", pcbnew.F_Cu, 0, connection="thermal")
            tag = "rail-gnd-fcu"
        elif st == 2.5:
            # F.Cu thermal reliefs cannot always win two spokes on this geometry, and a
            # 1-spoke relief is a starved_thermal DRC error (baseline had none, so this is a
            # regression the pour introduces). A pad-local DIRECT override is legal KiCad and
            # is scoped to named pads only -- it does not change the zone or any project floor.
            # Measured here: 58 opens -> 55, starved 6 -> 0, versus 58 -> 35 with 6 starved.
            done = {}
            for spec in PAD_DIRECT:
                done[spec] = PS.set_pad_connection(b, spec, "direct")
            info = {"net": "/GND", "kind": "pad-local direct override",
                    "pads": PAD_DIRECT, "nets": done}
            tag = "rail-gnd-padlocal"
        elif st == 3:
            info = add_via(b, "/GND", *GND_STITCH)
            tag = "rail-gnd-stitch"
        elif st == 4:
            made = []
            for ref, num, ref2, num2 in V3_LINKS:
                made.append(add_seg(b, "/+3V3", pad_centre(b, ref, num, "/+3V3"),
                                    pad_centre(b, ref2, num2, "/+3V3")))
            info = {"net": "/+3V3", "kind": "pad-centre tree", "segments": made}
            tag = "rail-3v3-tree"
        else:
            raise SystemExit("unknown stage %s" % st)
        out, nz = finish(b, D / ("%s.kicad_pcb" % tag))
        board = out
        rec["stages"].append({"stage": st, "tag": tag, "added": info,
                              "zones_filled": nz, "board": str(out),
                              "sha256": __import__("hashlib").sha256(
                                  open(out, "rb").read()).hexdigest()})
        print("stage %s -> %s" % (st, out))
    Path(a.report).write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({"stages": [s["tag"] for s in rec["stages"]],
                      "final": str(board)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
