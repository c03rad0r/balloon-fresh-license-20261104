"""Find a VSCAP via site that satisfies HOLE-TO-HOLE as well as copper clearance.

FAILED ATTEMPT, recorded so it is not repeated: a via placed at r=0.750 mm from C_CAP1 pad 1
passed every copper check (land overlapped the pad, land sat on the filled pour, no foreign
copper within the guard band) and still produced TWO hole_to_hole violations against the
1.000 mm PTH drill.

Why: the drill-to-drill gap is 0.750 - (1.000/2) - (0.300/2) = 0.100 mm, and the board rule is
0.250 mm. Copper clearance said yes; hole clearance said no. My probe tested one constraint and
reported "no foreign copper within guard band" as if that settled it — it did not.

Lesson: a via has TWO keep-outs, copper AND drill. Check both or the check is theatre.

Required centre spacing: (1.000 + 0.300)/2 + 0.250 = 0.900 mm minimum.
"""
import math
import pcbnew as p

SRC = "/tmp/refilltest/b.kicad_pcb"
DST = "/tmp/refilltest/vscapvia.kicad_pcb"
UM = 1e6

NET = "/VSCAP"
CLEAR = 0.200
GUARD = CLEAR + 0.070711
VIA_LAND, VIA_DRILL = 0.600, 0.300
H2H = 0.250
PAD_POS = (36.000, 37.500)
PAD_DRILL = 1.000
MIN_SPACING = (PAD_DRILL + VIA_DRILL) / 2 + H2H

b = p.LoadBoard(SRC)
net_obj = b.FindNet(NET)

zone = None
zone_layer = None
for z in b.Zones():
    if z.GetNetname() == NET and z.IsFilled():
        for l in z.GetLayerSet().Seq():
            if b.GetLayerName(l) == "B.Cu":
                zone, zone_layer = z, l
if zone is None:
    raise SystemExit("no filled %s zone" % NET)

fpc = b.FindFootprintByReference("C_CAP1")
pad_shape = None
for pad in fpc.Pads():
    if pad.GetNumber() == "1":
        pad_shape = pad.GetEffectiveShape(p.B_Cu)
if pad_shape is None:
    raise SystemExit("C_CAP1.1 has no B.Cu copper")

# every drilled hole on the board, so hole_to_hole can be checked against all of them
holes = []
for t in b.GetTracks():
    if t.Type() == p.PCB_VIA_T:
        pos = t.GetPosition()
        holes.append((pos.x / UM, pos.y / UM, t.GetDrillValue() / UM, "via " + t.GetNetname()))
for fp in b.GetFootprints():
    for pad in fp.Pads():
        d = pad.GetDrillSize().x / UM
        if d > 0:
            pos = pad.GetPosition()
            holes.append((pos.x / UM, pos.y / UM, d,
                          "pad %s.%s" % (fp.GetReference(), pad.GetNumber())))


def foreign_copper(shape, clearance):
    hits = []
    for lyr in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu):
        for t in b.GetTracks():
            if t.GetNetname() == NET or t.Type() == p.PCB_VIA_T or t.GetLayer() != lyr:
                continue
            s = t.GetEffectiveShape(lyr)
            if s is not None and p.SHAPE.Collide(shape, s, clearance):
                hits.append("track %s %s" % (t.GetNetname(), b.GetLayerName(lyr)))
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() == NET or not pad.IsOnLayer(lyr):
                    continue
                s = pad.GetEffectiveShape(lyr)
                if s is not None and p.SHAPE.Collide(shape, s, clearance):
                    hits.append("pad %s.%s %s" % (fp.GetReference(), pad.GetNumber(),
                                                 b.GetLayerName(lyr)))
    return hits


print("=== search ring, requiring BOTH copper and hole clearance ===")
print("  min centre spacing to the C_CAP1 PTH: %.3f mm (drill %.3f + %.3f)/2 + h2h %.3f"
      % (MIN_SPACING, PAD_DRILL, VIA_DRILL, H2H))
print()

found = None
for step in range(9, 31):        # 0.90 mm .. 3.00 mm radius
    r = step * 0.10
    if r < MIN_SPACING - 1e-9:
        continue
    for deg in range(0, 360, 3):
        x = PAD_POS[0] + r * math.cos(math.radians(deg))
        y = PAD_POS[1] + r * math.sin(math.radians(deg))
        pt = p.VECTOR2I(int(round(x * UM)), int(round(y * UM)))
        land = p.SHAPE_CIRCLE(pt, int(round((VIA_LAND / 2) * UM)))

        # 1. must still touch the pad copper, or the via joins nothing
        if not p.SHAPE.Collide(land, pad_shape, 0):
            continue
        # 2. must sit on poured copper
        if not zone.HitTestFilledArea(zone_layer, pt):
            continue
        # 3. copper clearance
        if foreign_copper(land, int(round(GUARD * UM))):
            continue
        # 4. HOLE clearance against every drill on the board -- the check the last attempt skipped
        bad_hole = None
        for (hx, hy, hd, hname) in holes:
            need = (hd + VIA_DRILL) / 2 + H2H
            if (hx - x) ** 2 + (hy - y) ** 2 < need ** 2:
                bad_hole = "%s (need %.3f)" % (hname, need)
                break
        if bad_hole:
            continue
        found = (r, deg, x, y)
        break
    if found:
        break

if not found:
    raise SystemExit("no site satisfies copper AND hole clearance")

r, deg, vx, vy = found
print("  legal site: r=%.2f mm %.0f deg -> (%.3f, %.3f)" % (r, deg, vx, vy))

via = p.PCB_VIA(b)
via.SetPosition(p.VECTOR2I(int(round(vx * UM)), int(round(vy * UM))))
via.SetWidth(int(round(VIA_LAND * UM)))
via.SetDrill(int(round(VIA_DRILL * UM)))
via.SetViaType(p.VIATYPE_THROUGH)
via.SetLayerPair(p.F_Cu, p.B_Cu)
via.SetNet(net_obj)
b.Add(via)

b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
b.Save(DST)
print("  applied and saved %s" % DST)
