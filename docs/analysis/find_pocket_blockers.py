"""Identify, exactly, which tracks bound each pad-local pocket.

reach_fast.py says all five are pad-local pockets on F.Cu. A pocket is bounded by SOMETHING. This
prints every F.Cu track within 0.6 mm of each trapped pad, with its endpoints, so a nudge can be
defined as a concrete move rather than a guess.

Note on the target gap: reach_fast.py floods at GUARD = CLEAR + half diagonal step = 0.2708 mm. For a
0.200 mm track to pass, the gap to an obstacle must be at least CLEAR + half width = 0.200 + 0.100 =
0.300 mm at minimum, and the flood needs 0.2708 measured to the CENTRELINE, which is the same
0.300/0.200 pair after accounting for how the guard is applied. Two budgets, both ~0.30-0.54.
This script therefore reports the raw gaps and lets the flood decide -- it does not assert a target.
"""
import pcbnew as p

BOARD = "docs/analysis/bulk-route-20261107/latest.kicad_pcb"
UM = 1e6

TRAPS = [("/EN", "U1", "3"), ("/SPI2_SCK", "U1", "4"),
         ("/F33_VSENSE", "U1", "21"), ("/VSCAP", "R_BAL1", "1")]

b = p.LoadBoard(BOARD)


def gap(a, c, hi=1.5):
    if p.SHAPE.Collide(a, c, 0):
        return 0.0
    if not p.SHAPE.Collide(a, c, int(round(hi * UM))):
        return None
    lo, h = 0, int(round(hi * UM))
    for _ in range(26):
        mid = (lo + h) // 2
        if p.SHAPE.Collide(a, c, mid):
            h = mid
        else:
            lo = mid
    return h / UM


def pad_of(ref, num):
    fp = b.FindFootprintByReference(ref)
    if not fp:
        return None
    for pd in fp.Pads():
        if pd.GetNumber() == num:
            return pd
    return None


for net, ref, num in TRAPS:
    pad = pad_of(ref, num)
    pos = pad.GetPosition()
    print("=== %-12s %s.%s  at (%.3f, %.3f)" % (net, ref, num, pos.x / UM, pos.y / UM))
    lay = p.F_Cu
    sa = pad.GetEffectiveShape(lay)
    rows = []
    for t in b.GetTracks():
        if t.GetNetname() == net or t.Type() == p.PCB_VIA_T or t.GetLayer() != lay:
            continue
        g = gap(sa, t.GetEffectiveShape(lay), 0.9)
        if g is None:
            continue
        s, e = t.GetStart(), t.GetEnd()
        rows.append((g, t.GetNetname(), s.x / UM, s.y / UM, e.x / UM, e.y / UM,
                     t.GetWidth() / UM))
    rows.sort()
    for g, tn, sx, sy, ex, ey, w in rows[:6]:
        print("   gap %.3f  %-14s (%.3f,%.3f)->(%.3f,%.3f)  w=%.3f"
              % (g, tn, sx, sy, ex, ey, w))
    print()
