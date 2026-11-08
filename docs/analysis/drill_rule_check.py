"""The three 0.360 mm vias: is the drill size safe, and what happens if JLCPCB rounds it?

0.360 mm is NOT a JLCPCB standard drill (they stock in 0.05 mm steps). The risk is not cosmetic:
rounding UP to 0.40 mm removes 0.020 mm of annular ring all round, and that is what IPC-2221
minimums and JLCPCB's own rules care about.

Measure, for each of the three vias:
  - land diameter and drill
  - annular ring as built = (land - drill)/2
  - annular ring if the drill is rounded to 0.350 and to 0.400
  - whether the drill change would break the 0.150 mm minimum annular ring JLCPCB requires
    for PTH (and 0.100 mm for via in their capability table)
  - how close the resulting land is to foreign copper (SRS-1 clearance), before and after
"""
import pcbnew as p

UM = 1e6
b = p.LoadBoard("docs/analysis/bulk-route-20261107/latest.kicad_pcb")

print("=== every via with drill 0.360 mm ===")
found = []
for t in b.GetTracks():
    if t.Type() != p.PCB_VIA_T:
        continue
    drill = t.GetDrillValue() / UM
    if abs(drill - 0.360) > 1e-6:
        continue
    pos = t.GetPosition()
    land = t.GetWidth() / UM
    ann = (land - drill) / 2
    found.append((pos.x / UM, pos.y / UM, land, drill, ann, t.GetNetname()))
    print("  via at (%.3f, %.3f)  net=%-14s land %.3f  drill %.3f  annular ring %.3f"
          % (pos.x / UM, pos.y / UM, t.GetNetname(), land, drill, ann))

print()
print("=== annular ring if the drill is rounded ===")
for (x, y, land, drill, ann, net) in found:
    print("  (%.2f,%.2f) %s  land %.3f" % (x, y, net, land))
    for cand in (0.350, 0.360, 0.400):
        a = (land - cand) / 2
        # JLCPCB: min via annular ring 0.100 mm; min PTH annular ring 0.150 mm
        v = "OK" if a >= 0.100 else "FAIL (<0.100 via min)"
        print("     drill %.3f -> annulus %.4f mm   %s" % (cand, a, v))

print()
print("=== are these vias actually REQUIRED to be 0.360? check the net and neighbours ===")
for (x, y, land, drill, ann, net) in found:
    pt = p.VECTOR2I(int(round(x * UM)), int(round(y * UM)))
    land_shape = p.SHAPE_CIRCLE(pt, int(round((land / 2) * UM)))
    worst = None
    for lyr in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu):
        for t in b.GetTracks():
            if t.GetNetname() == net or t.Type() == p.PCB_VIA_T or t.GetLayer() != lyr:
                continue
            s = t.GetEffectiveShape(lyr)
            if s is None:
                continue
            if not p.SHAPE.Collide(land_shape, s, int(round(0.8 * UM))):
                continue
            lo, hi = 0, int(round(0.8 * UM))
            for _ in range(20):
                mid = (lo + hi) // 2
                if p.SHAPE.Collide(land_shape, s, mid):
                    hi = mid
                else:
                    lo = mid
            g = hi / UM
            if worst is None or g < worst[0]:
                worst = (g, t.GetNetname(), b.GetLayerName(lyr))
    print("  (%.2f,%.2f) %s: nearest foreign copper %s"
          % (x, y, net, ("%.3f mm to %s on %s" % worst) if worst else ">0.8 mm"))
