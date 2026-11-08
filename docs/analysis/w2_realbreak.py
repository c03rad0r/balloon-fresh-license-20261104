"""Find the ACTUAL break in /W2_SOLAR_N, by testing which bridge merges the components.

Two wrong theories already recorded for this net:
  1. "the B.Cu chain stops 1.700 mm short of J_W3 pad 1"  -- false, a 1.700 mm track reaches it
  2. "the 0.250 mm near-approach is the break"            -- false, a 0.250 mm bridge there is
     legal at S1 and closes NOTHING (opens 11 -> 11, signature identical over 4 runs each)
     A near-approach is two different components' copper passing close by, which is not the
     same as the pair DRC reports. Adjacency is not connectivity.

METHOD: build the component graph, then for every PAIR of components find their nearest approach
on a shared layer. A bridge at that point is the only one that can merge them. Then test the
candidate and check the count DROPS -- the count is the only stable signal on this board.
"""
import math
import pcbnew as p
from collections import defaultdict

UM = 1e6
b = p.LoadBoard("/tmp/refilltest/b.kicad_pcb")
NET = "/W2_SOLAR_N"
SNAP = 0.150

items = []
for t in b.GetTracks():
    if t.GetNetname() != NET:
        continue
    s, e = t.GetStart(), t.GetEnd()
    if t.Type() == p.PCB_VIA_T:
        pos = t.GetPosition()
        items.append(("VIA", {p.F_Cu, p.B_Cu, p.In1_Cu, p.In2_Cu},
                      (pos.x / UM, pos.y / UM), (pos.x / UM, pos.y / UM)))
    else:
        items.append(("TRACK", {t.GetLayer()}, (s.x / UM, s.y / UM), (e.x / UM, e.y / UM)))

# pads on this net, as zero-length items
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetname() != NET:
            continue
        lays = {l for l in pad.GetLayerSet().Seq()
                if b.GetLayerName(l) in ("F.Cu", "B.Cu")}
        pos = pad.GetPosition()
        items.append(("PAD %s.%s" % (fp.GetReference(), pad.GetNumber()), lays,
                      (pos.x / UM, pos.y / UM), (pos.x / UM, pos.y / UM)))

parent = list(range(len(items)))


def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


def union(a, c):
    ra, rc = find(a), find(c)
    if ra != rc:
        parent[ra] = rc


def touch(i, j):
    if not (items[i][1] & items[j][1]):
        return False
    for (ax, ay) in (items[i][2], items[i][3]):
        for (bx, by) in (items[j][2], items[j][3]):
            if (ax - bx) ** 2 + (ay - by) ** 2 <= SNAP ** 2:
                return True
    return False


for i in range(len(items)):
    for j in range(i + 1, len(items)):
        if touch(i, j):
            union(i, j)

comps = defaultdict(list)
for i in range(len(items)):
    comps[find(i)].append(i)
sizes = sorted(((len(v), k) for k, v in comps.items()), reverse=True)
print("components: %s" % [s for s, _ in sizes])
print()

# nearest approach between the two smallest comps and the main one
main = comps[sizes[0][1]]
print("=== nearest shared-layer approach, small comps -> main ===")
cands = []
for n, k in sizes[1:]:
    mem = comps[k]
    best = None
    for i in mem:
        for j in main:
            if not (items[i][1] & items[j][1]):
                continue
            for (ax, ay) in (items[i][2], items[i][3]):
                for (bx, by) in (items[j][2], items[j][3]):
                    d = math.hypot(ax - bx, ay - by)
                    if best is None or d < best[0]:
                        best = (d, (ax, ay), (bx, by),
                                items[i][1] & items[j][1])
    if best:
        d, pa, pb, lyr = best
        lay = ",".join(sorted(b.GetLayerName(l) for l in lyr))
        print("  %d-item comp %.3f mm : (%.3f,%.3f) -> (%.3f,%.3f) on %s"
              % (n, d, pa[0], pa[1], pb[0], pb[1], lay))
        cands.append((d, pa, pb, lay, n))

print()
print("=== ALL pairwise near-approaches under 2 mm (any two components) ===")
for a_i in range(len(sizes)):
    for b_i in range(a_i + 1, len(sizes)):
        na, ka = sizes[a_i]
        nb, kb = sizes[b_i]
        best = None
        for i in comps[ka]:
            for j in comps[kb]:
                if not (items[i][1] & items[j][1]):
                    continue
                for (ax, ay) in (items[i][2], items[i][3]):
                    for (bx, by) in (items[j][2], items[j][3]):
                        d = math.hypot(ax - bx, ay - by)
                        if best is None or d < best[0]:
                            best = (d, (ax, ay), (bx, by), items[i][1] & items[j][1])
        if best and best[0] < 2.0:
            d, pa, pb, lyr = best
            lay = ",".join(sorted(b.GetLayerName(l) for l in lyr))
            print("  comp(%d) <-> comp(%d) : %.3f mm  (%.3f,%.3f)->(%.3f,%.3f) %s"
                  % (na, nb, d, pa[0], pa[1], pb[0], pb[1], lay))
