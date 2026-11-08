"""Why did the VSCAP via not close the open? Test the antipad-retreat hypothesis.

The via at r=0.900 from C_CAP1.1 was legal (16 violations, no hole_to_hole) but the open
survived, re-reported as "Pad 1 of R_BAL1 || Via [/VSCAP]".

HYPOTHESIS: ZONE_FILLER punches an antipad around the new via with the zone's clearance, so
after the refill the pour retreats from the via land. Then the via touches the PAD but not the
POUR, and the open merely moves from "pad vs track" to "pad vs via" -- which is exactly what
the DRC said.

TEST: compare zone coverage at the via position BEFORE and AFTER the refill. If the fill
retreats, HitTestFilledArea flips true->false at the same point.

If confirmed, the fix is not a via: it is to extend the pour to the pad, or to route one 0.200
track from the pad edge to where the pour already is, keeping S1.
"""
import pcbnew as p

UM = 1e6
b = p.LoadBoard("/tmp/refilltest/b.kicad_pcb")
NET = "/VSCAP"
VX, VY = 36.899, 37.547

zone = None
zl = None
for z in b.Zones():
    if z.GetNetname() == NET and z.IsFilled():
        for l in z.GetLayerSet().Seq():
            if b.GetLayerName(l) == "B.Cu":
                zone, zl = z, l


def covered(x, y):
    return zone.HitTestFilledArea(zl, p.VECTOR2I(int(round(x * UM)), int(round(y * UM))))


print("=== BEFORE adding anything ===")
for label, (x, y) in (
    ("pad centre      (36.000,37.500)", (36.000, 37.500)),
    ("via site        (36.899,37.547)", (VX, VY)),
    ("1.5 mm out      (37.500,37.500)", (37.500, 37.500)),
    ("2.5 mm out      (38.500,37.500)", (38.500, 37.500)),
):
    print("  %-34s pour present: %s" % (label, covered(x, y)))

# Now add the via exactly as the previous attempt did, refill, and re-measure.
net_obj = b.FindNet(NET)
via = p.PCB_VIA(b)
via.SetPosition(p.VECTOR2I(int(round(VX * UM)), int(round(VY * UM))))
via.SetWidth(int(round(0.600 * UM)))
via.SetDrill(int(round(0.300 * UM)))
via.SetViaType(p.VIATYPE_THROUGH)
via.SetLayerPair(p.F_Cu, p.B_Cu)
via.SetNet(net_obj)
b.Add(via)
b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())

print()
print("=== AFTER adding the via and refilling ===")
zone2 = None
zl2 = None
for z in b.Zones():
    if z.GetNetname() == NET and z.IsFilled():
        for l in z.GetLayerSet().Seq():
            if b.GetLayerName(l) == "B.Cu":
                zone2, zl2 = z, l


def covered2(x, y):
    return zone2.HitTestFilledArea(zl2, p.VECTOR2I(int(round(x * UM)), int(round(y * UM))))


for label, (x, y) in (
    ("pad centre      (36.000,37.500)", (36.000, 37.500)),
    ("via site        (36.899,37.547)", (VX, VY)),
    ("via land edge   (37.199,37.547)", (37.199, 37.547)),
    ("1.5 mm out      (37.500,37.500)", (37.500, 37.500)),
    ("2.5 mm out      (38.500,37.500)", (38.500, 37.500)),
):
    print("  %-34s pour present: %s" % (label, covered2(x, y)))

print()
print("=== does the via land still overlap the poured copper? ===")
pt = p.VECTOR2I(int(round(VX * UM)), int(round(VY * UM)))
land = p.SHAPE_CIRCLE(pt, int(round(0.300 * UM)))
try:
    poly = zone2.GetFilledPolysList(zl2)
    hit = p.SHAPE.Collide(land, poly, 0)
    print("  land vs filled polys (SHAPE.Collide): %s" % hit)
    print("  NOTE: SHAPE_POLY_SET containment makes this unreliable; the HitTestFilledArea")
    print("        readings above are the trustworthy ones.")
except Exception as e:
    print("  could not test:", e)

# And the decisive question: is the via's drill inside the pour at all?
print()
print("=== sample the pour on a circle of radius 0.30 around the via centre ===")
import math
inside = 0
total = 0
for deg in range(0, 360, 15):
    x = VX + 0.30 * math.cos(math.radians(deg))
    y = VY + 0.30 * math.sin(math.radians(deg))
    total += 1
    if covered2(x, y):
        inside += 1
print("  %d of %d sample points on the land perimeter are on poured copper" % (inside, total))
if inside == 0:
    print("  CONFIRMED: the fill retreats from the via. The antipad hypothesis holds --")
    print("  an isolated via here cannot join the pour, so it cannot close the open.")
