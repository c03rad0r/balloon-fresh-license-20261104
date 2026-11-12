"""Decision visuals, take 2 — fixed after vision review of take 1.

Take 1 problems, all real:
  - the two coincident pad rectangles blended to grey, so "two separate objects" was NOT visible
  - F.Cu / B.Cu labels printed over one another
  - the 0.250 mm gap arrow was too small to read

Fix: draw the two faces of each pad as SIDE-BY-SIDE slabs with a visible split, offset outward
from the pad centre, so the two-object fact is the thing you see. Widen the gap callout and
label each track END explicitly.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
import pcbnew as p

UM = 1e6
b = p.LoadBoard("/tmp/refilltest/b.kicad_pcb")

fig, (axL, axR) = plt.subplots(1, 2, figsize=(20, 10))

# ---------------------------------------------------------------- PANEL A
ref, padnum = "J_W3", "4"
fp = b.FindFootprintByReference(ref)
faces = [q for q in fp.Pads() if q.GetNumber() == padnum]
pos = faces[0].GetPosition()
CX, CY = pos.x / UM, pos.y / UM
R = 4.6

# cavity
cav = [(g.GetStart(), g.GetEnd()) for g in fp.GraphicalItems() if g.GetLayer() == p.Edge_Cuts]
for s, e in cav:
    axL.plot([s.x / UM, e.x / UM], [s.y / UM, e.y / UM], color="k", lw=2.6, zorder=8)
xs = [pt.x / UM for seg in cav for pt in seg]
ys = [pt.y / UM for seg in cav for pt in seg]
axL.add_patch(Rectangle((min(xs), min(ys)), max(xs) - min(xs), max(ys) - min(ys),
                        facecolor="#dfe6e9", edgecolor="none", zorder=1))
axL.text((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
         "SOCKET CAVITY\nEdge.Cuts — no track may cross",
         fontsize=9.5, ha="center", va="center", zorder=12, fontweight="bold",
         bbox=dict(fc="white", ec="black", lw=1.3, pad=4, alpha=0.95))

# pads: draw F.Cu and B.Cu as two adjacent slabs, split visible
for pad in fp.Pads():
    ppos, sz = pad.GetPosition(), pad.GetSize()
    lays = [b.GetLayerName(l) for l in pad.GetLayerSet().Seq()
            if b.GetLayerName(l) in ("F.Cu", "B.Cu")]
    if not lays:
        continue
    w, h = sz.x / UM, sz.y / UM
    x0, y0 = ppos.x / UM - w / 2, ppos.y / UM - h / 2
    lay = lays[0]
    if lay == "F.Cu":
        axL.add_patch(Rectangle((x0, y0), w, h * 0.47, facecolor="#e74c3c",
                                alpha=0.62, edgecolor="#a93226", lw=1.4, zorder=5))
        axL.add_patch(Rectangle((x0, y0 + h * 0.53), w, h * 0.47, facecolor="#2980b9",
                                alpha=0.62, edgecolor="#1f618d", lw=1.4, zorder=5))
        axL.text(ppos.x / UM - w / 2 - 0.15, ppos.y / UM,
                 "pad %s\n%s" % (pad.GetNumber(), pad.GetNetname()),
                 fontsize=7.6, ha="right", va="center", zorder=9)

axL.text(CX, CY - 0.95, "F.Cu face", fontsize=8.6, color="#a93226", ha="center",
         zorder=10, fontweight="bold")
axL.text(CX, CY + 0.95, "B.Cu face", fontsize=8.6, color="#1f618d", ha="center",
         zorder=10, fontweight="bold")
axL.text(CX + 2.35, CY, "ONE pad number\nTWO pad objects\n→ they are the\nassembly tab",
         fontsize=9, color="#c0392b", va="center", ha="left", zorder=15,
         fontweight="bold",
         bbox=dict(fc="#fdf2f2", ec="#c0392b", lw=1.4, pad=4, alpha=0.96))
axL.annotate("", xy=(CX + 2.2, CY), xytext=(CX + 1.0, CY),
             arrowprops=dict(arrowstyle="->", color="#c0392b", lw=2.2), zorder=14)

for t in b.GetTracks():
    if t.Type() == p.PCB_VIA_T:
        continue
    s, e = t.GetStart(), t.GetEnd()
    axL.plot([s.x / UM, e.x / UM], [s.y / UM, e.y / UM],
             color="#e74c3c" if t.GetLayer() == p.F_Cu else "#2980b9",
             lw=max(t.GetWidth() / UM * 2.2, 0.8), alpha=0.9,
             solid_capstyle="round", zorder=4)

axL.set_title("A.  Two-face wing pad  —  %s pad %s\n"
              "DRC item 7: 'Pad 4 of J_W3 on F.Cu' vs 'Pad 4 of J_W3 on B.Cu'"
              % (ref, padnum), fontsize=11.5)
axL.set_xlim(CX - R, CX + R)
axL.set_ylim(CY + R, CY - R)
axL.set_aspect("equal")
axL.grid(alpha=0.15)

# ---------------------------------------------------------------- PANEL B
BX, BY, BR = 67.9, 41.4, 3.6

fp3 = b.FindFootprintByReference("J_W3")
cav3 = [(g.GetStart(), g.GetEnd()) for g in fp3.GraphicalItems() if g.GetLayer() == p.Edge_Cuts]
for s, e in cav3:
    axR.plot([s.x / UM, e.x / UM], [s.y / UM, e.y / UM], color="k", lw=2.4, zorder=8)
xs3 = [pt.x / UM for seg in cav3 for pt in seg]
ys3 = [pt.y / UM for seg in cav3 for pt in seg]
if xs3:
    axR.add_patch(Rectangle((min(xs3), min(ys3)), max(xs3) - min(xs3), max(ys3) - min(ys3),
                            facecolor="#dfe6e9", edgecolor="none", zorder=1))

for pad in fp3.Pads():
    ppos, sz = pad.GetPosition(), pad.GetSize()
    w, h = sz.x / UM, sz.y / UM
    axR.add_patch(Rectangle((ppos.x / UM - w / 2, ppos.y / UM - h / 2), w, h,
                            facecolor="#2980b9", alpha=0.30, edgecolor="#1f618d",
                            lw=1.5, zorder=3))
    axR.text(ppos.x / UM, ppos.y / UM, "%s" % pad.GetNetname(),
             fontsize=6.8, ha="center", va="center", zorder=9, color="#1a5276")

for t in b.GetTracks():
    if t.GetNetname() != "/W2_SOLAR_N" or t.Type() == p.PCB_VIA_T or t.GetLayer() != p.B_Cu:
        continue
    s, e = t.GetStart(), t.GetEnd()
    axR.plot([s.x / UM, e.x / UM], [s.y / UM, e.y / UM], color="#2471a3", lw=3.8,
             alpha=0.95, solid_capstyle="round", zorder=5)

# explicit endpoints of the gap
G1 = (67.300, 42.700)   # isolated island end
G2 = (67.150, 42.900)   # main run end
axR.plot(*G1, "o", ms=9, mfc="#2471a3", mec="black", mew=1.4, zorder=12)
axR.plot(*G2, "o", ms=9, mfc="#2471a3", mec="black", mew=1.4, zorder=12)
axR.add_patch(FancyArrowPatch(G1, G2, arrowstyle="<|-|>", mutation_scale=15,
                              color="#8e44ad", lw=1.7, shrinkA=3, shrinkB=3, zorder=13))
axR.text(65.35, 44.15, "0.250 mm between the two track ENDS\n"
                       "a 0.200 mm track needs 0.400 mm\n→ short by 0.150 mm",
         fontsize=9, color="#8e44ad", fontweight="bold", zorder=16,
         ha="left", va="top",
         bbox=dict(fc="white", ec="#8e44ad", lw=1.5, pad=4, alpha=0.97))

axR.plot(69.000, 42.700, "o", ms=17, mfc="none", mec="#27ae60", mew=3.0, zorder=16)
axR.text(69.000, 41.95, "J_W3 pad 1\n(/W2_SOLAR_N, B.Cu face)",
         fontsize=8.6, color="#1e8449", ha="center", va="bottom",
         zorder=17, fontweight="bold",
         bbox=dict(fc="white", ec="#1e8449", lw=1.0, pad=2, alpha=0.94))

axR.text(69.0, 39.5, "cavity edge\n(tracks ≥0.500 mm away)",
         fontsize=8.6, color="#c0392b", ha="center", zorder=17, fontweight="bold",
         bbox=dict(fc="white", ec="#c0392b", lw=1.1, pad=2.5, alpha=0.94))

axR.set_title("B.  /W2_SOLAR_N  —  the one remaining closable open\n"
              "the pad's own B.Cu island stops 0.250 mm from the main run", fontsize=11.5)
axR.set_xlim(BX - BR, BX + BR)
axR.set_ylim(BY + BR, BY - BR)
axR.set_aspect("equal")
axR.grid(alpha=0.15)

plt.tight_layout(rect=(0, 0, 1, 0.94))
out = ("/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/"
       "bulk-route-20261107/DECISION-two-face-and-w2.png")
plt.savefig(out, dpi=118, facecolor="white")
print("saved %s" % out)
