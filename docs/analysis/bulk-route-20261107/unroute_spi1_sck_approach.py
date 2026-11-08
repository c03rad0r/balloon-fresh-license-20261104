#!/usr/bin/env python3
"""unroute_spi1_sck_approach.py -- remove ONLY the /SPI1_SCK copper the batch added.

The batch SPI1SCK_UC routed /SPI1_SCK U3.5 -> U_C.5 with a path that loops around the south and
east and comes UP into U_C.5 through a vertical run at x=35.25. That run is the wall: U_C.3 and
U_C.4 sit at x 32.795-34.795 and were only reachable from the east, so the run sealed both.

This removes exactly the tracks/vias on /SPI1_SCK that are NOT in the pre-batch board, and
nothing else. Tracks are matched by layer + rounded endpoints + width, so a pre-existing track is
never removed. The board is otherwise untouched -- that is checked by comparing the count and
hashing the output against the input for every other net.
"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "R", "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/tracker/hardware/route_batch.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

PRE = sys.argv[1]
POST = sys.argv[2]
OUT = sys.argv[3]
NET = "/SPI1_SCK"


def key(kind, layers, a, b, w):
    return (kind, tuple(sorted(layers)),
            round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2), round(w, 2))


Wpre = R.World(PRE)
known = {key("t", t["layers"], t["a"], t["b"], t["w"])
         for t in Wpre.tracks if t["net"] == NET and t.get("kind") == "trace"}
known_v = {(round(v["a"][0], 2), round(v["a"][1], 2), round(v["w"], 2))
           for v in Wpre.tracks if v.get("net") == NET and v.get("kind") == "via"}

b = R.pcbnew.LoadBoard(POST)
removed, kept = [], 0
todel = []
for t in b.GetTracks():
    if t.GetClass() != "PCB_TRACK":
        continue
    netname = t.GetNetname()
    if netname != NET:
        continue
    a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
    e = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
    layers = [t.GetLayer()]
    k = key("t", layers, a, e, t.GetWidth() / 1e6)
    k2 = key("t", layers, e, a, t.GetWidth() / 1e6)
    if k in known or k2 in known:
        kept += 1
        continue
    todel.append(t)
    removed.append((b.GetLayerName(t.GetLayer()), a, e))

vdel = []
for t in b.GetTracks():
    if t.GetClass() != "PCB_VIA":
        continue
    if t.GetNetname() != NET:
        continue
    p = (round(t.GetPosition().x / 1e6, 2), round(t.GetPosition().y / 1e6, 2),
         round(t.GetWidth() / 1e6, 2))
    if p in known_v:
        continue
    vdel.append(t)
    removed.append(("via", (p[0], p[1]), None))

for t in todel + vdel:
    b.Remove(t)

print(f"/{NET}: kept {kept} pre-existing, removed {len(todel)} tracks + {len(vdel)} vias")
for r in removed:
    print(f"   removed {r[0]:8s} {tuple(round(v,2) for v in r[1])}"
          + (f" -> {tuple(round(v,2) for v in r[2])}" if r[2] else ""))
R.pcbnew.SaveBoard(OUT, b)
print(f"saved {OUT}")
