"""What width of track can actually fit between a trapped pad and each of its blockers?

THE ARITHMETIC THAT HAS NOW BEEN WRONG THREE TIMES IN THIS CAMPAIGN.

A new track passing between a pad edge and an existing track edge, with gap G between them, needs:
    clearance to the pad      C
    its own width             W
    clearance to the track    C
so                                    G >= 2C + W   =>   W <= G - 2C

At S1 (C = 0.200):  W <= G - 0.400
At fab (C = 0.090): W <= G - 0.180

Earlier in this campaign I used "C + W = 0.400" as the budget, which omits ONE of the two clearance
gaps. That is why the same error keeps recurring: every version understates the requirement by
exactly one C, and every version looks plausible.

This script does not assert a budget. It solves for the maximum feasible width per gap, so the answer
is a number the board gives, not a formula I re-derive.
"""
import pcbnew as p

BOARD = "docs/analysis/bulk-route-20261107/latest.kicad_pcb"
UM = 1e6
S1_CLEAR = 0.200
FAB_CLEAR = 0.090
S1_TRACK = 0.200

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


print("W <= G - 2C.  Negative means no track of any width fits at that clearance.")
print()
for net, ref, num in TRAPS:
    pad = pad_of(ref, num)
    sa = pad.GetEffectiveShape(p.F_Cu)
    rows = []
    for t in b.GetTracks():
        if t.GetNetname() == net or t.Type() == p.PCB_VIA_T or t.GetLayer() != p.F_Cu:
            continue
        g = gap(sa, t.GetEffectiveShape(p.F_Cu), 0.9)
        if g is None:
            continue
        rows.append((g, t.GetNetname()))
    rows.sort()

    print("=== %-12s %s.%s" % (net, ref, num))
    best_s1 = best_fab = None
    for g, tn in rows[:4]:
        w_s1 = g - 2 * S1_CLEAR
        w_fab = g - 2 * FAB_CLEAR
        if best_s1 is None or w_s1 > best_s1[0]:
            best_s1 = (w_s1, tn, g)
        if best_fab is None or w_fab > best_fab[0]:
            best_fab = (w_fab, tn, g)
        tag = ""
        if w_s1 >= S1_TRACK:
            tag = "  <-- a 0.200 track FITS at S1"
        elif w_s1 > 0:
            tag = "  (only a %.3f track)" % w_s1
        else:
            tag = "  NO track at S1"
        print("   gap %.3f to %-14s  max width at S1 %+.3f  at fab %+.3f%s"
              % (g, tn, w_s1, w_fab, tag))
    print("   BEST case at S1: %.3f mm available vs %.3f needed -> %s"
          % (best_s1[0], S1_TRACK, "FITS" if best_s1[0] >= S1_TRACK else "DOES NOT FIT"))
    print("   BEST case at fab minimums: %.3f mm -> %s"
          % (best_fab[0], "a %.3f mm track" % best_fab[0] if best_fab[0] > 0 else "nothing fits"))
    print()
