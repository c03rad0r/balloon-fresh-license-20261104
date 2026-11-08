"""Bring the three 0.360 mm vias back to S1's 0.300 mm.

WHY: S1 freezes via at 0.600 land / 0.300 drill (latest.kicad_dru lines 10-11, 22-24). The three
0.360 mm vias came in with the FR3NETS batch -- freerouting's own geometry -- and were never
normalised to S1. They carry:
  - annulus 0.120 mm, versus 0.150 mm for every other via on the board
  - annulus 0.120 mm versus JLCPCB's 0.13 mm minimum via annular ring  -> NON-COMPLIANT
  - and 0.360 is not a stocked drill; JLCPCB moves in 0.05 mm steps, so it becomes 0.35 (annulus
    0.125) or 0.40 (annulus 0.100, worse than today).

Fix is a DRILL REDUCTION on the same land, same position, same net: 0.600 / 0.300, annulus 0.150,
identical to the other 158 vias. It cannot make clearance worse -- the land is unchanged -- and it
increases the annulus and the hole-to-hole margins.

This is a rule-conformance fix, not a design change: it restores the frozen S1 numbers the board
is supposed to carry.
"""
import pcbnew as p

SRC = "/tmp/refilltest/b.kicad_pcb"
DST = "/tmp/refilltest/s1vias.kicad_pcb"
UM = 1e6

b = p.LoadBoard(SRC)
changed = []
for t in b.GetTracks():
    if t.Type() != p.PCB_VIA_T:
        continue
    if abs(t.GetDrillValue() / UM - 0.360) > 1e-6:
        continue
    pos = t.GetPosition()
    before = (t.GetDrillValue() / UM, t.GetWidth() / UM)
    t.SetDrill(int(round(0.300 * UM)))
    changed.append((pos.x / UM, pos.y / UM, t.GetNetname(), before[0], before[1]))

print("=== vias normalised to S1 (0.600 / 0.300) ===")
for (x, y, net, d0, land) in changed:
    print("  (%.3f, %.3f) %-14s drill %.3f -> 0.300  land %.3f unchanged  annulus %.3f -> 0.150"
          % (x, y, net, d0, land, (land - d0) / 2))

if not changed:
    raise SystemExit("no 0.360 vias found -- nothing to do")

b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
b.Save(DST)

# verify
b2 = p.LoadBoard(DST)
from collections import Counter
c = Counter()
for t in b2.GetTracks():
    if t.Type() == p.PCB_VIA_T:
        c[(round(t.GetWidth() / UM, 3), round(t.GetDrillValue() / UM, 3))] += 1
print()
print("=== after ===")
for k, v in sorted(c.items()):
    print("  land %.3f / drill %.3f : %d vias  annulus %.3f" % (k[0], k[1], v, (k[0] - k[1]) / 2))
print()
print("  saved %s" % DST)
