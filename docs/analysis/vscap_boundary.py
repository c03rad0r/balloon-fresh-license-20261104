"""Map the VSCAP pour boundary around C_CAP1.1 so a real bridge can be drawn.

The 0.050 mm "track" failed because the search started at r=0.55 (already outside the pad
land) and stopped at the first point where the pour was present -- a stub that spans neither
the pad nor the gap. That is a geometry error in the search, not a routing failure.

This measures, in 16 directions, the two radii that matter:
  r_pad  : where the pad's own copper ends
  r_pour : where the poured copper begins
A bridge exists only where r_pour > r_pad AND the span between them is clear.
"""
import math
import pcbnew as p

UM = 1e6
b = p.LoadBoard("/tmp/refilltest/b.kicad_pcb")
NET = "/VSCAP"
zone, zl = None, None
for z in b.Zones():
    if z.GetNetname() == NET and z.IsFilled():
        for l in z.GetLayerSet().Seq():
            if b.GetLayerName(l) == "B.Cu":
                zone, zl = z, l

fpc = b.FindFootprintByReference("C_CAP1")
pad = None
for pd in fpc.Pads():
    if pd.GetNumber() == "1":
        pad = pd
padshape = pad.GetEffectiveShape(p.B_Cu)
pos = pad.GetPosition()
PX, PY = pos.x / UM, pos.y / UM
sz = pad.GetSize()
print("C_CAP1.1 at (%.3f, %.3f)  size %.3f x %.3f  drill %.3f  shape %s"
      % (PX, PY, sz.x / UM, sz.y / UM, pad.GetDrillSize().x / UM, pad.GetShape()))


def pad_has(x, y):
    return p.SHAPE.Collide(padshape, p.VECTOR2I(int(round(x * UM)), int(round(y * UM))), 0)


def pour_has(x, y):
    return zone.HitTestFilledArea(zl, p.VECTOR2I(int(round(x * UM)), int(round(y * UM))))


print()
print("  dir   r_pad_end   r_pour_start   gap_to_bridge")
print("  " + "-" * 52)
rows = []
for deg in range(0, 360, 15):
    ux, uy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    r_pad = None
    for i in range(0, 200):        # 0 .. 2.000 mm in 0.010 steps
        r = i * 0.01
        if not pad_has(PX + r * ux, PY + r * uy):
            r_pad = r
            break
    r_pour = None
    if r_pad is not None:
        for i in range(int(r_pad * 100), 400):
            r = i * 0.01
            if pour_has(PX + r * ux, PY + r * uy):
                r_pour = r
                break
    if r_pad is None:
        print("  %3d   (pad never ends within 2mm)" % deg)
        continue
    if r_pour is None:
        print("  %3d   %8.3f      (no pour within 4mm)" % (deg, r_pad))
        continue
    print("  %3d   %8.3f    %10.3f     %8.3f" % (deg, r_pad, r_pour, r_pour - r_pad))
    rows.append((r_pour - r_pad, deg, r_pad, r_pour))

rows.sort()
print()
if rows:
    print("  shortest spans:")
    for gap, deg, rp, rq in rows[:5]:
        print("    %3d deg : pad ends %.3f, pour starts %.3f, span %.3f"
              % (deg, rp, rq, gap))
