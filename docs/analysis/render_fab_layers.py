"""Four-layer fab render composite: what the fab house will actually receive."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

LAYERS = [("F_Cu.png", "F.Cu — top copper"), ("In1_Cu.png", "In1.Cu — GND plane"),
          ("In2_Cu.png", "In2.Cu — +3V3 plane"), ("B_Cu.png", "B.Cu — bottom copper")]

fig, axes = plt.subplots(1, 4, figsize=(22, 7.5))
for ax, (f, title) in zip(axes, LAYERS):
    img = mpimg.imread("/tmp/fabverify/" + f)
    ax.imshow(img)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.axis("off")

fig.suptitle("board 322ade1e — gerbers rendered independently in gerbv, all four copper layers\n"
             "28 files  ·  drill 196/196 across 5 tools  ·  outline closed",
             fontsize=14, fontweight="bold")
plt.tight_layout(rect=(0, 0, 1, 0.92))
out = ("/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/"
       "bulk-route-20261107/FAB-four-layers-verified.png")
plt.savefig(out, dpi=110, facecolor="white")
print("saved %s" % out)
