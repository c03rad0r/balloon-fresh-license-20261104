"""Does forcing C_CAP1.1 to a solid zone connection close the VSCAP open?

MEASURED CONTEXT
  C_CAP1.1 is a PTH through-hole: 1.000 mm drill, copper on F.Cu/B.Cu/In1.In2
  Its local zone connection is -1 (INHERITED). EVERY other /VSCAP pad on the board is 2
  (THERMAL): D1.1, U7.1, U7.3, R_DIV1.1, R_BAL1.1, J_VCC.1, U_CUT1..4.1. C_CAP1.1 is the only
  one that inherits, so it is the anomaly.
  The zone's default pad connection is 1 (FULL/SOLID).
  The pad's copper ring DOES overlap the filled pour on B.Cu (measured: pour True at r=0.60
  inside the pad, span 0.000 along the pad axes). So the copper is in contact and yet DRC says
  unconnected -- which points at the connection MODE rather than at geometry.

TEST: set local zone connection to 0 (inherit -> solid, matching the zone default) and to 3
(THT_THERMAL) in separate candidates, refill, and compare with the stable comparator.
Nothing is written to the working board.
"""
import pcbnew as p
import subprocess, json, re
from collections import Counter

BASE = "/tmp/refilltest/b.kicad_pcb"
UM = 1e6


def sig(board, tag, runs=3):
    outs = []
    for i in range(runs):
        f = "/tmp/refilltest/zc_%s_%d.json" % (tag, i)
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                        "--units", "mm", "--output", f, board], capture_output=True)
        d = json.load(open(f))
        ks = []
        for v in d.get("unconnected_items", []):
            nets = []
            for x in v.get("items", []):
                nets += re.findall(r"\[(/[^\]]+)\]", x.get("description", ""))
            ks.append(tuple(sorted(set(nets))))
        outs.append((len(d.get("unconnected_items", [])), Counter(ks),
                     len(d.get("violations", []))))
    return outs


base = sig(BASE, "base")
print("baseline: counts %s violations %s" % ([r[0] for r in base], [r[2] for r in base]))
base_sig = {tuple(sorted(r[1].items())) for r in base}
print()

for label, mode in (("solid (0=inherit)", 0), ("THT thermal (3)", 3), ("thermal (2)", 2)):
    b = p.LoadBoard(BASE)
    fp = b.FindFootprintByReference("C_CAP1")
    pad = [q for q in fp.Pads() if q.GetNumber() == "1"][0]
    pad.SetLocalZoneConnection(mode)
    b.BuildConnectivity()
    p.ZONE_FILLER(b).Fill(b.Zones())
    out = "/tmp/refilltest/zc_%d.kicad_pcb" % mode
    b.Save(out)
    r = sig(out, "m%d" % mode)
    s = {tuple(sorted(x[1].items())) for x in r}
    same = s == base_sig
    print("  %-20s counts %s  violations %s  identical_to_baseline=%s"
          % (label, [x[0] for x in r], [x[2] for x in r], same))
    if not same:
        bs = base[0][1]
        ms = r[0][1]
        print("      baseline-only: %s" % dict(bs - ms))
        print("      candidate-only: %s" % dict(ms - bs))
    print()
