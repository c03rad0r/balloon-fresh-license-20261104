"""VSCAPTRACK: join C_CAP1 pad 1 to the VSCAP_BCu pour with one 0.200 mm track on B.Cu.

Established by measurement, not assumption:
  - C_CAP1 pad 1 is a PTH through-hole (1.000 mm drill) on F.Cu/B.Cu/In1/In2
  - the VSCAP_BCu zone is filled, but HitTestFilledArea at the pad centre is False
  - no /VSCAP tracks exist within 3 mm of the pad
  - a bare via at r=0.900 mm passed every check and closed nothing
  - the antipad-retreat theory is disproved: the fill does not move when the via is added

So the pour stops short of the pad and the gap must be bridged by copper. This draws one
0.200 mm track from the pad edge to the nearest point where the pour is already present,
checking S1 clearance (plus guard band) and every hole on the route.

Judged with the stable comparator: record count plus the net-key multiset over 3 runs each
side, because descriptions are not reproducible.
"""
import math
import pcbnew as p

SRC = "/tmp/refilltest/b.kicad_pcb"
DST = "/tmp/refilltest/vscaptrack.kicad_pcb"
UM = 1e6

NET = "/VSCAP"
TRACK_W = 0.200
CLEAR = 0.200
GUARD = CLEAR + 0.070711
H2H = 0.250
PAD = (36.000, 37.500)
PAD_DRILL = 1.000
HALF_W = TRACK_W / 2

b = p.LoadBoard(SRC)
net_obj = b.FindNet(NET)

zone, zl = None, None
for z in b.Zones():
    if z.GetNetname() == NET and z.IsFilled():
        for l in z.GetLayerSet().Seq():
            if b.GetLayerName(l) == "B.Cu":
                zone, zl = z, l
if zone is None:
    raise SystemExit("no filled %s zone on B.Cu" % NET)

fpc = b.FindFootprintByReference("C_CAP1")
padshape = None
for pad in fpc.Pads():
    if pad.GetNumber() == "1":
        padshape = pad.GetEffectiveShape(p.B_Cu)
if padshape is None:
    raise SystemExit("C_CAP1.1 has no B.Cu copper")


def pour_at(x, y):
    return zone.HitTestFilledArea(zl, p.VECTOR2I(int(round(x * UM)), int(round(y * UM))))


def foreign(shape, clearance):
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


# Every drill on the board, so the track can be kept off holes (track-to-hole 0.200 here).
holes = []
for t in b.GetTracks():
    if t.Type() == p.PCB_VIA_T:
        pos = t.GetPosition()
        holes.append((pos.x / UM, pos.y / UM, t.GetDrillValue() / UM))
for fp in b.GetFootprints():
    for pad in fp.Pads():
        d = pad.GetDrillSize().x / UM
        if d > 0:
            pos = pad.GetPosition()
            holes.append((pos.x / UM, pos.y / UM, d))


def seg_clear(a, c, skip_hole_near_pad=True):
    """Is a TRACK_W segment from a to c clear of copper, holes and the edge?"""
    pa = p.VECTOR2I(int(round(a[0] * UM)), int(round(a[1] * UM)))
    pc = p.VECTOR2I(int(round(c[0] * UM)), int(round(c[1] * UM)))
    shape = p.SHAPE_SEGMENT(pa, pc, int(round(HALF_W * UM)))

    h = foreign(shape, int(round(GUARD * UM)))
    if h:
        return False, "copper: %s" % h[:3]

    # holes: distance from each drill centre to the segment
    ax, ay = a
    cx, cy = c
    dx, dy = cx - ax, cy - ay
    L2 = dx * dx + dy * dy
    for (hx, hy, hd) in holes:
        if skip_hole_near_pad and hd >= PAD_DRILL - 1e-9 and \
                (hx - PAD[0]) ** 2 + (hy - PAD[1]) ** 2 < 1e-6:
            continue  # the pad we are routing to
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((hx - ax) * dx + (hy - ay) * dy) / L2))
        px, py = ax + t * dx, ay + t * dy
        d = math.hypot(hx - px, hy - py)
        if d < (hd / 2 + HALF_W + H2H):
            return False, "hole at (%.2f,%.2f) d=%.3f" % (hx, hy, d)

    # board edge
    for dr in b.GetDrawings():
        if dr.GetLayer() != p.Edge_Cuts:
            continue
        s = p.SEG(dr.GetStart(), dr.GetEnd())
        if p.SHAPE.Collide(shape, s, int(round(0.500 * UM))):
            return False, "edge"
    return True, ""


# Find the shortest legal radial from the pad edge into the pour.
print("=== searching for a legal track from C_CAP1.1 into the pour ===")
best = None
for deg in range(0, 360, 2):
    ux, uy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    # start just outside the pad copper, so the track lands ON the pad
    start_r = 0.55
    for r in (0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.1, 2.5, 3.0):
        x = PAD[0] + r * ux
        y = PAD[1] + r * uy
        if not pour_at(x, y):
            continue
        a = (PAD[0] + start_r * ux, PAD[1] + start_r * uy)
        c = (x, y)
        ok, why = seg_clear(a, c)
        if not ok:
            continue
        # the track must actually touch the pad copper at its start
        pa = p.VECTOR2I(int(round(a[0] * UM)), int(round(a[1] * UM)))
        pc = p.VECTOR2I(int(round(c[0] * UM)), int(round(c[1] * UM)))
        shape = p.SHAPE_SEGMENT(pa, pc, int(round(HALF_W * UM)))
        if not p.SHAPE.Collide(shape, padshape, 0):
            continue
        L = math.hypot(c[0] - a[0], c[1] - a[1])
        if best is None or L < best[0]:
            best = (L, deg, a, c)
        break

if not best:
    raise SystemExit("no legal track found from the pad into the pour")

L, deg, a, c = best
print("  found: %.0f deg, length %.3f mm" % (deg, L))
print("    from (%.3f, %.3f) to (%.3f, %.3f)" % (a[0], a[1], c[0], c[1]))
print("    width %.3f, clearance %.3f (guard %.3f), hole-to-hole %.3f" % (TRACK_W, CLEAR, GUARD, H2H))

t = p.PCB_TRACK(b)
t.SetStart(p.VECTOR2I(int(round(a[0] * UM)), int(round(a[1] * UM))))
t.SetEnd(p.VECTOR2I(int(round(c[0] * UM)), int(round(c[1] * UM))))
t.SetWidth(int(round(TRACK_W * UM)))
t.SetLayer(p.B_Cu)
t.SetNet(net_obj)
b.Add(t)

b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
b.Save(DST)
print("  applied and saved %s" % DST)
