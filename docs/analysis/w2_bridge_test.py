"""Decisive test for /W2_SOLAR_N: can the 8-item island be bridged legally at S1?

CORRECTION TO MY OWN LAST STATEMENT. I described the 0.250 mm gap between (67.300,42.700) and
(67.150,42.900) as "short by 0.150 mm" against a 0.400 mm budget (0.200 clearance + 0.200 track).
That budget does NOT apply here: BOTH endpoints are /W2_SOLAR_N tracks, and same-net copper needs
no clearance from itself. The 0.250 mm is a GAP TO SPAN, not a clearance violation.

So the real question is whether a 0.200 mm track from one end to the other clears:
  - FOREIGN copper (any net except /W2_SOLAR_N) at 0.200 + guard band
  - holes (track-to-hole 0.200)
  - the wing-socket cavity (0.500 mm, AGENTS.md 13a) -- the binding constraint
  - Edge.Cuts

If it does, this is a one-track closure and should be attempted. If it does not, report that
plainly instead of forcing it.
"""
import math
import pcbnew as p

UM = 1e6
B = "/tmp/refilltest/b.kicad_pcb"
NET = "/W2_SOLAR_N"
A = (67.300, 42.700)
C = (67.150, 42.900)
W = 0.200
CLEAR = 0.200
GUARD = CLEAR + 0.070711
H2H = 0.250
TRK2HOLE = 0.200
EDGE = 0.500

b = p.LoadBoard(B)

pa = p.VECTOR2I(int(round(A[0] * UM)), int(round(A[1] * UM)))
pc = p.VECTOR2I(int(round(C[0] * UM)), int(round(C[1] * UM)))
shape = p.SHAPE_SEGMENT(pa, pc, int(round((W / 2) * UM)))

print("proposed track: (%.3f, %.3f) -> (%.3f, %.3f)  width %.3f  length %.3f mm"
      % (A[0], A[1], C[0], C[1], W, math.hypot(C[0] - A[0], C[1] - A[1])))
print()

# --- 1. foreign copper -------------------------------------------------------
print("=== 1. foreign copper at %.3f mm (0.200 + guard) ===" % GUARD)
hits = []
for lyr in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu):
    for t in b.GetTracks():
        if t.GetNetname() == NET or t.Type() == p.PCB_VIA_T or t.GetLayer() != lyr:
            continue
        s = t.GetEffectiveShape(lyr)
        if s is not None and p.SHAPE.Collide(shape, s, int(round(GUARD * UM))):
            pos = t.GetStart()
            hits.append(("track", t.GetNetname(), b.GetLayerName(lyr),
                         pos.x / UM, pos.y / UM))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == NET or not pad.IsOnLayer(lyr):
                continue
            s = pad.GetEffectiveShape(lyr)
            if s is not None and p.SHAPE.Collide(shape, s, int(round(GUARD * UM))):
                pos = pad.GetPosition()
                hits.append(("pad %s.%s" % (fp.GetReference(), pad.GetNumber()),
                             pad.GetNetname(), b.GetLayerName(lyr),
                             pos.x / UM, pos.y / UM))
if hits:
    for h in hits:
        print("  BLOCKED by %-10s %-14s on %-6s at (%.2f,%.2f)" % h)
else:
    print("  none within %.3f mm" % GUARD)

# --- 2. holes ----------------------------------------------------------------
print()
print("=== 2. track-to-hole %.3f mm ===" % TRK2HOLE)
hole_bad = []
for t in b.GetTracks():
    if t.Type() != p.PCB_VIA_T:
        continue
    pos = t.GetPosition()
    hx, hy, hd = pos.x / UM, pos.y / UM, t.GetDrillValue() / UM
    ax, ay = A
    cx, cy = C
    dx, dy = cx - ax, cy - ay
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((hx - ax) * dx + (hy - ay) * dy) / L2))
    d = math.hypot(hx - (ax + u * dx), hy - (ay + u * dy))
    if d < hd / 2 + W / 2 + TRK2HOLE:
        hole_bad.append(("via", hx, hy, d))
for fp in b.GetFootprints():
    for pad in fp.Pads():
        dd = pad.GetDrillSize().x / UM
        if dd <= 0:
            continue
        pos = pad.GetPosition()
        hx, hy = pos.x / UM, pos.y / UM
        ax, ay = A
        cx, cy = C
        dx, dy = cx - ax, cy - ay
        L2 = dx * dx + dy * dy
        u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((hx - ax) * dx + (hy - ay) * dy) / L2))
        d = math.hypot(hx - (ax + u * dx), hy - (ay + u * dy))
        if d < dd / 2 + W / 2 + TRK2HOLE:
            hole_bad.append(("pad %s.%s" % (fp.GetReference(), pad.GetNumber()), hx, hy, d))
if hole_bad:
    for h in hole_bad:
        print("  TOO CLOSE to %-10s at (%.2f,%.2f) d=%.3f" % h)
else:
    print("  clear")

# --- 3. socket cavity (the binding constraint) -------------------------------
print()
print("=== 3. wing-socket cavity %.3f mm (AGENTS.md 13a) ===" % EDGE)
cav_edges = []
for ref in ("J_W1", "J_W2", "J_W3", "J_W4", "J_W5", "J_W6"):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        continue
    for g in fp.GraphicalItems():
        if g.GetLayer() != p.Edge_Cuts:
            continue
        s, e = g.GetStart(), g.GetEnd()
        seg = p.SEG(s, e)
        d = None
        # distance from the proposed track to this cavity edge
        pts = [(A[0], A[1]), (C[0], C[1])]
        # crude but sufficient: sample the track
        best = 1e9
        for i in range(51):
            u = i / 50
            x = A[0] + u * (C[0] - A[0])
            y = A[1] + u * (C[1] - A[1])
            v = p.VECTOR2I(int(round(x * UM)), int(round(y * UM)))
            # distance to the SEG via bisection on a point-shape collide
            circ = p.SHAPE_CIRCLE(v, 1)
            if p.SHAPE.Collide(circ, seg.GetEffectiveShape() if hasattr(seg, "GetEffectiveShape") else
                               p.SHAPE_SEGMENT(s, e, 1), int(round(2.0 * UM))):
                lo, hi = 0, int(round(2.0 * UM))
                for _ in range(20):
                    mid = (lo + hi) // 2
                    if p.SHAPE.Collide(circ, p.SHAPE_SEGMENT(s, e, 1), mid):
                        hi = mid
                    else:
                        lo = mid
                best = min(best, hi / UM)
        if best < 1e8:
            cav_edges.append((ref, s.x / UM, s.y / UM, e.x / UM, e.y / UM, best))
if cav_edges:
    cav_edges.sort(key=lambda r: r[5])
    for r in cav_edges[:4]:
        verdict = "VIOLATES" if r[5] < EDGE else "ok"
        print("  %-5s edge (%.2f,%.2f)->(%.2f,%.2f)  clr %.3f  %s"
              % (r[0], r[1], r[2], r[3], r[4], r[5], verdict))
else:
    print("  no cavity edge within 2 mm")

print()
print("=== VERDICT ===")
ok = (not hits) and (not hole_bad) and (not cav_edges or cav_edges[0][5] >= EDGE)
print("  direct bridge legal at S1: %s" % ok)
