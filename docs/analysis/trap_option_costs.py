"""Cost both options for the four pad-local traps, measured. No option chosen.

OPTION A: a 0.150 mm clearance rule scoped to the four pads only.
OPTION B: move the enclosing copper.

For each trapped pad, measure what the neighbour gap actually is, what a 0.150 rule would permit,
and which specific object is the blocker so Option B has a target.
"""
import pcbnew as p

UM = 1e6
b = p.LoadBoard("docs/analysis/bulk-route-20261107/latest.kicad_pcb")

TRAPS = [
    ("/EN",        "U1",  "3",  "J_PROG", "3"),
    ("/SPI2_SCK",  "U1",  "4",  "U2",     "12"),
    ("/F33_VSENSE","U1",  "21", "R_MON1", "2"),
    ("/VSCAP",     "R_BAL1", "1", "C_CAP1", "1"),
]

S1 = 0.200
FAB_MIN = 0.090     # JLCPCB >=4 layer 0.5/1oz
TRACK_W = 0.200


def pad_of(ref, num):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        return None, None
    for pad in fp.Pads():
        if pad.GetNumber() == num:
            return fp, pad
    return fp, None


def gap_between(shape_a, shape_b, hi=1.0):
    """Bisection on SHAPE.Collide. Distance is unreliable on pads on this board."""
    if p.SHAPE.Collide(shape_a, shape_b, 0):
        return 0.0
    if not p.SHAPE.Collide(shape_a, shape_b, int(round(hi * UM))):
        return None
    lo, h = 0, int(round(hi * UM))
    for _ in range(24):
        mid = (lo + h) // 2
        if p.SHAPE.Collide(shape_a, shape_b, mid):
            h = mid
        else:
            lo = mid
    return h / UM


print("=== the four pad-local traps: what blocks each one ===")
print()
for net, ref_a, num_a, ref_b, num_b in TRAPS:
    fa, pa = pad_of(ref_a, num_a)
    fb, pb = pad_of(ref_b, num_b)
    if pa is None:
        print("%-13s %s.%s NOT FOUND" % (net, ref_a, num_a))
        continue
    pos = pa.GetPosition()
    print("%-13s pin %s.%s at (%.3f, %.3f)" % (net, ref_a, num_a, pos.x / UM, pos.y / UM))

    # For every foreign copper object within 1.5 mm on any copper layer, the measured gap.
    sa_layers = [l for l in pa.GetLayerSet().Seq()
                 if b.GetLayerName(l) in ("F.Cu", "B.Cu", "In1.Cu", "In2.Cu")]
    blockers = []
    for lyr in sa_layers:
        sa = pa.GetEffectiveShape(lyr)
        if sa is None:
            continue
        for t in b.GetTracks():
            if t.GetNetname() == net or t.Type() == p.PCB_VIA_T or t.GetLayer() != lyr:
                continue
            s = t.GetEffectiveShape(lyr)
            if s is None:
                continue
            g = gap_between(sa, s)
            if g is not None and g < 1.0:
                blockers.append((g, "track %s" % t.GetNetname(), b.GetLayerName(lyr), t))
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() == net or not pad.IsOnLayer(lyr):
                    continue
                if fp.GetReference() == ref_a and pad.GetNumber() == num_a:
                    continue
                s = pad.GetEffectiveShape(lyr)
                if s is None:
                    continue
                g = gap_between(sa, s)
                if g is not None and g < 1.0:
                    blockers.append((g, "pad %s.%s" % (fp.GetReference(), pad.GetNumber()),
                                     b.GetLayerName(lyr), pad))

    blockers.sort(key=lambda r: r[0])
    if not blockers:
        print("     no foreign copper within 1.0 mm on its own layers")
    for g, name, lyr, obj in blockers[:3]:
        # CORRIDOR BUDGET IS 0.400, NOT 0.200. A 0.200 mm track passing between this pad and a
        # neighbour needs clearance (0.200) PLUS its own width (0.200). Using S1's 0.200 alone
        # inflates every verdict by exactly 0.200 -- the documented clearance-budget error from
        # earlier in this campaign, repeated here in my own script until this fix.
        CORRIDOR = 0.400
        verdict_s1 = "OK at S1" if g >= CORRIDOR else "SHORT %.3f (needs 0.400)" % (CORRIDOR - g)
        c150 = 0.150 + 0.200
        verdict_150 = "OK at 0.150" if g >= c150 else "SHORT %.3f (needs %.3f)" % (c150 - g, c150)
        cfab = FAB_MIN + 0.200
        verdict_fab = "OK at fab" if g >= cfab else "SHORT %.3f (needs %.3f)" % (cfab - g, cfab)
        print("     gap %6.3f mm to %-22s on %-5s   %-18s %-16s %s"
              % (g, name, lyr, verdict_s1, verdict_150, verdict_fab))
    print()
