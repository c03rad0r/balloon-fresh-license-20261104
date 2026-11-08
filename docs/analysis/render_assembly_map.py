"""Visual: which parts get assembled and which stay off, on the actual board outline."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pcbnew as p

b = p.LoadBoard("asm.kicad_pcb")
UM = 1e6
bb = b.GetBoardEdgesBoundingBox()
x0, x1 = bb.GetLeft() / UM, bb.GetRight() / UM
y0, y1 = bb.GetTop() / UM, bb.GetBottom() / UM

fig, ax = plt.subplots(figsize=(11.5, 12))
ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#f7f9fa", ec="#2c3e50", lw=2, zorder=1))

asm, dnp = [], []
for f in b.GetFootprints():
    ref = str(f.GetReference())
    if str(f.GetFPID().GetLibItemName()).startswith("MountingHole"):
        continue
    pos = f.GetPosition()
    px, py = pos.x / UM, pos.y / UM
    (dnp if f.GetAttributes() & p.FP_EXCLUDE_FROM_BOM else asm).append((ref, px, py, f))

for ref, px, py, f in dnp:
    ax.plot(px, py, "X", ms=11, mec="#c0392b", mfc="#f9e79f", mew=2.0, zorder=4)
    ax.annotate(ref, (px, py), textcoords="offset points", xytext=(7, -3),
                fontsize=6.4, color="#c0392b")
for ref, px, py, f in asm:
    ax.plot(px, py, "o", ms=7.5, mec="#1a5276", mfc="#5dade2", mew=1.5, zorder=5)
    ax.annotate(ref, (px, py), textcoords="offset points", xytext=(6, 2),
                fontsize=6.4, color="#1a5276")

ax.set_xlim(x0 - 3, x1 + 3)
ax.set_ylim(y1 + 3, y0 - 3)
ax.set_aspect("equal")
ax.set_title("Partial assembly: %d placements fitted, %d sites left empty\n"
             "board 72.10 x 80.10 mm — population from RECOMMENDATIONS-ON-OPEN-DECISIONS D1/D3/D4/D6"
             % (len(asm), len(dnp)), fontsize=11.5, fontweight="bold", pad=14)

ax.plot([], [], "o", ms=8, mec="#1a5276", mfc="#5dade2", label="assembled (%d)" % len(asm))
ax.plot([], [], "X", ms=10, mec="#c0392b", mfc="#f9e79f", mew=2, label="DNP (%d)" % len(dnp))
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.035), ncol=2, frameon=False, fontsize=10)
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)
plt.tight_layout()
out = ("/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/"
       "bulk-route-20261107/ASSEMBLY-partial-map.png")
plt.savefig(out, dpi=140, facecolor="white", bbox_inches="tight")
print("saved %s  (%d assembled, %d DNP)" % (out, len(asm), len(dnp)))
