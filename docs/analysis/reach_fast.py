"""Fast same-layer reachability using a coarse raster -- replaces the 20+ min per-pair flood.

WHY THE OLD TOOL WAS SLOW: reachability.py evaluates via_ok lazily over all 3054 track/via objects,
and a full via-aware flood costs 20+ minutes per pair. Several partial verdicts this campaign came
from that cost: I could only afford one or two floods per turn, so conclusions were reported before
the set was measured.

WHY NOT JUST WAIT FOR IT: the answer only needs to distinguish three states:
  CONNECTED       -- the two halves are already one conductor
  SAME-LAYER-GAP  -- a raster flood from one half reaches near the other (this tool answers it)
  NEEDS-VIA       -- the flood cannot reach the other half on one layer, so a layer change is needed

The third state is exactly what this tool CANNOT answer, and saying so is the point: for those nets
the honest verdict is NEEDS-VIA / UNDETERMINED, not "blocked". This campaign already produced two
wrong "genuinely blocked" claims from a same-layer raster read as a routing verdict.

METHOD: 0.1 mm raster per layer, cells blocked when Collide with foreign copper at the S1 guard.
Flood 4-connected within the start half's layer, then test whether any reached cell touches the goal
half's own copper on that same layer. 0.1 mm pitch is fine enough for a 0.2 mm track to pass: any
0.2 mm gap is 2 cells wide.

Reported per net: flood size, whether the halves met, and the closest approach distance. A large
flood that still does not meet is a genuine same-layer obstacle. A tiny flood is a pad-local pocket,
which means the question is a layer-change question and this tool declines it.
"""

import sys
import time
import pcbnew as p

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
UM = 1_000_000.0
PITCH = 100_000          # 0.1 mm
GUARD = 200_000 + 70_711  # S1 clearance + half diagonal step
HALF = 100_000           # track half width

PAIRS = [
    ('/EN', 'U1', '3', 'J_PROG', '3'),
    ('/SPI2_SCK', 'U1', '4', 'U2', '12'),
    ('/F33_VSENSE', 'U1', '21', 'R_MON1', '2'),
    ('/VSCAP', 'R_BAL1', '1', 'C_CAP1', '1'),
    ('/VSCAP', 'R_BAL1', '1', 'D1', '1'),
]

b = p.LoadBoard(BOARD)
b.BuildConnectivity()

fps = {f.GetReference(): f for f in b.GetFootprints()}


def pad_of(ref, num):
    f = fps.get(ref)
    if f is None:
        return None
    for pd in f.Pads():
        if pd.GetNumber() == str(num):
            return pd
    return None


# --- build per-layer obstacles once -------------------------------------------------
bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = bb.GetLeft(), bb.GetTop()
NX = int(bb.GetWidth() // PITCH) + 1
NY = int(bb.GetHeight() // PITCH) + 1
print('raster %d x %d at %.3f mm pitch' % (NX, NY, PITCH / UM))

LAYERS = [(p.F_Cu, 'F.Cu'), (p.B_Cu, 'B.Cu')]

# obstacle shapes per layer, from tracks/vias/pads (zones excluded: pours are not obstacles)
obs = {lay: [] for lay, _ in LAYERS}
for t in b.GetTracks():
    if t.Type() == p.PCB_TRACE_T:
        lay = t.GetLayer()
        if lay in obs:
            obs[lay].append(t.GetEffectiveShape(lay))
    else:
        for lay, _ in LAYERS:
            if t.IsOnLayer(lay):
                obs[lay].append(t.GetEffectiveShape(lay))
for f in b.GetFootprints():
    for pd in f.Pads():
        for lay, _ in LAYERS:
            if pd.IsOnLayer(lay):
                obs[lay].append(pd.GetEffectiveShape(lay))
print('obstacles: F.Cu %d, B.Cu %d' % (len(obs[p.F_Cu]), len(obs[p.B_Cu])))


def cells_for_shape(shape, lay):
    """Raster cells whose disc overlaps this shape -- the cells a flood may not cross."""
    out = set()
    bx = shape.BBox()
    x1 = int((bx.GetLeft() - GUARD - HALF - X0) // PITCH) - 1
    x2 = int((bx.GetRight() + GUARD + HALF - X0) // PITCH) + 1
    y1 = int((bx.GetTop() - GUARD - HALF - Y0) // PITCH) - 1
    y2 = int((bx.GetBottom() + GUARD + HALF - Y0) // PITCH) + 1
    for i in range(x1, x2 + 1):
        for j in range(y1, y2 + 1):
            c = p.SHAPE_CIRCLE(p.VECTOR2I(X0 + i * PITCH, Y0 + j * PITCH), HALF)
            if p.SHAPE.Collide(shape, c, GUARD):
                out.add((i, j))
    return out


def run(pair):
    net, ra, pa, rb, pb = pair
    a = pad_of(ra, pa)
    g = pad_of(rb, pb)
    if a is None or g is None:
        return net, 'NO SUCH PAD', 0, None

    # own copper: cells the pad occupies are legal to stand on
    for lay, lname in LAYERS:
        if not a.IsOnLayer(lay):
            continue
        # THE START AND GOAL PADS' OWN COPPER MUST NOT BE OBSTACLES.
        # First version put every pad in obs[], including these two, so the flood seeded
        # inside its own blocked disc and never escaped -- every net came back "pad-local
        # pocket", including /EN which has a measured 1.40 mm clear run. Excluding the two
        # terminal shapes is what makes the seed legal.
        # Compare by BBOX, not identity: GetEffectiveShape() hands back a fresh Python wrapper on
        # every call, so `s is o` is always False and the first dedup attempt changed nothing
        # (identical 373-cell output before and after -- that is how I caught it).
        def bbox_key(sh):
            bx = sh.BBox()
            return (bx.GetLeft(), bx.GetTop(), bx.GetRight(), bx.GetBottom())
        own = {bbox_key(a.GetEffectiveShape(lay))}
        if g.IsOnLayer(lay):
            own.add(bbox_key(g.GetEffectiveShape(lay)))
        blocked = set()
        for s in obs[lay]:
            if bbox_key(s) in own:
                continue
            blocked |= cells_for_shape(s, lay)

        seed = cells_for_shape(a.GetEffectiveShape(lay), lay)
        goal = cells_for_shape(g.GetEffectiveShape(lay), lay) if g.IsOnLayer(lay) else set()
        if not seed:
            continue
        free = lambda c: c not in blocked
        start = {c for c in seed if free(c)} or seed

        seen = set(start)
        stack = list(start)
        t0 = time.time()
        while stack:
            i, j = stack.pop()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = (i + di, j + dj)
                if c in seen or not (0 <= c[0] < NX and 0 <= c[1] < NY):
                    continue
                if c in blocked:
                    continue
                seen.add(c)
                stack.append(c)
            if len(seen) > 3_000_000:
                break
        dt = time.time() - t0
        met = bool(seen & goal)
        if met:
            return net, 'CONNECTED on %s' % lname, len(seen), dt
        if len(seen) < 5000:
            return net, 'PAD-LOCAL pocket on %s (%d cells) -> NEEDS-VIA question' % (lname, len(seen)), len(seen), dt
        # closest approach from the flood to the goal pad
        try:
            gs = g.GetEffectiveShape(lay)
        except Exception:
            gs = None
        best = None
        if gs is not None:
            step = max(1, len(seen) // 4000)
            for k, (i, j) in enumerate(seen):
                if k % step:
                    continue
                c = p.SHAPE_CIRCLE(p.VECTOR2I(X0 + i * PITCH, Y0 + j * PITCH), HALF)
                if p.SHAPE.Collide(gs, c, 5_000_000):
                    lo, hi = 0, 5_000_000
                    for _ in range(20):
                        mid = (lo + hi) // 2
                        if p.SHAPE.Collide(gs, c, mid):
                            hi = mid
                        else:
                            lo = mid
                    if best is None or hi < best:
                        best = hi
        return net, 'NOT MET on %s (flood %d, closest %.3f mm)' % (
            lname, len(seen), (best or 0) / UM), len(seen), dt

    return net, 'NO COMMON LAYER', 0, None


print('\n%-13s %-8s %s' % ('NET', 'PADS', 'VERDICT'))
print('-' * 96)
t00 = time.time()
for pr in PAIRS:
    net, verdict, n, dt = run(pr)
    print('%-13s %-8s %s' % (net, '%s.%s>' % (pr[1], pr[2]) + '%s.%s' % (pr[3], pr[4]), verdict))
    sys.stdout.flush()
print('\ntotal %.1f s for %d pairs' % (time.time() - t00, len(PAIRS)))
print('\nNOTE: NOT MET on one layer means the net needs a LAYER CHANGE or is blocked -- this tool')
print('cannot distinguish those, so it does not claim "blocked".')
