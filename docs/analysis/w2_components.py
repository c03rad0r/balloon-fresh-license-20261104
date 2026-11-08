"""Where exactly does /W2_SOLAR_N B.Cu disconnect? List the isolated component's members.

Correction to an earlier claim: the B.Cu chain DOES reach J_W3 pad 1 -- there is a 1.700 mm
track from (67.300, 42.700) to the pad at (69.000, 42.700), and 7 same-net B.Cu tracks touch
that pad. So "stops 1.7 mm short of the pad" was wrong.

The real question is where the pad's own chain ends and stops connecting to the main run.
"""
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

main = comps[sizes[0][1]]
print("=== isolated component member(s) ===")
for n, k in sizes[1:]:
    print("  --- %d item(s) ---" % n)
    mem = comps[k]
    for i in mem:
        kind, lays, a, c = items[i]
        lyr = ",".join(sorted(b.GetLayerName(l) for l in lays))
        print("    %-5s %-10s (%.3f,%.3f)->(%.3f,%.3f)" % (kind, lyr[:10], a[0], a[1], c[0], c[1]))

# What are the nearest points between the isolated component and the main one?
print()
print("=== nearest approach: isolated <-> main, per layer ===")
for n, k in sizes[1:]:
    mem = comps[k]
    best = None
    for i in mem:
        for j in main:
            if not (items[i][1] & items[j][1]):
                continue
            for (ax, ay) in (items[i][2], items[i][3]):
                for (bx, by) in (items[j][2], items[j][3]):
                    d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                    if best is None or d < best[0]:
                        best = (d, (ax, ay), (bx, by), items[i][1] & items[j][1])
    if best:
        d, pa, pb, lyr = best
        print("  %d-item comp: %.3f mm gap" % (n, d))
        print("    from (%.3f, %.3f) [isolated] to (%.3f, %.3f) [main] on %s"
              % (pa[0], pa[1], pb[0], pb[1],
                 ",".join(b.GetLayerName(l) for l in sorted(lyr))))
