#!/usr/bin/env python3
"""Draw the U3 sensor-port keep-out conflict and the real fix options, to scale.

DECISION DRAWING, not a board render. Every coordinate is measured from the project-local
footprint `PressureSensor:MS5611-01BA03_TE_Recommended` as placed at U3 in compact.kicad_pcb.
No board, footprint or routing was altered to produce this drawing.

CORRECTED CLAIM (v1 of this drawing overstated it). An escape DOES exist: a track whose centre
starts at local x = 1.63 mm is DRC-clean and electrically connected to pad 8 (verified with
kicad-cli and BOARD::GetConnectivity). What is true is narrower and still damning:
  * every track anchored at a PAD CENTRE is flagged items_not_allowed (3 of 3 probes);
  * the only legal anchor band is 1.625 .. 1.650 mm = 25 um wide, i.e. 1/8 of a single 0.20 mm
    net clearance, and it exists only because the lands protrude 0.15 mm past the nominal body.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
from matplotlib.gridspec import GridSpec
import pcbnew

BOARD = 'compact/compact.kicad_pcb'
b = pcbnew.LoadBoard(BOARD)
fp = [f for f in b.GetFootprints() if f.GetReference() == 'U3'][0]
origin = fp.GetPosition()

BODY = 1.5          # nominal body half-width  (3.0 mm wide)
BODY_H = 2.5        # nominal body half-height (5.0 mm tall)
PAD_W, PAD_H = 1.1, 0.6
PAD_CX = 1.1        # pad centre, local x
PAD_INNER = PAD_CX - PAD_W / 2      # 0.55  -> inner edge of the pad column
PAD_OUTER = PAD_CX + PAD_W / 2      # 1.65  -> outer edge of the land
TRACK_W = 0.25
CAP = TRACK_W / 2                   # 0.125 rounded end-cap radius
LEGAL_MIN = BODY + CAP              # 1.625 first legal track centre
WINDOW = PAD_OUTER - LEGAL_MIN      # 0.025 mm
NETCLEAR = 0.20
ROWS = (-1.875, -0.625, 0.625, 1.875)

BG, INK, MUTED = '#12141a', '#ffffff', '#8b93a7'
KO_FILL, KO_EDGE, KO_TXT = '#7a1f2b', '#ff5c7a', '#ff8fa3'
PAD_FILL, PAD_EDGE = '#c8a24a', '#ffe9a8'
OK, WARN, BAD = '#4dd6a0', '#ffb366', '#ff5c6b'

fig = plt.figure(figsize=(19.5, 12.6))
fig.patch.set_facecolor(BG)
gs = GridSpec(2, 3, figure=fig, height_ratios=[1.28, 1.0], hspace=0.42, wspace=0.26,
              left=0.045, right=0.975, top=0.885, bottom=0.085)


def frame(ax, title, sub, sub_color=OK):
    ax.set_facecolor(BG)
    ax.set_aspect('equal')
    ax.set_title('', pad=0)
    ax.text(0.5, 1.135, title, transform=ax.transAxes, ha='center', va='bottom',
            color=INK, fontsize=12.5, weight='bold')
    ax.text(0.5, 1.045, sub, transform=ax.transAxes, ha='center', va='bottom',
            color=sub_color, fontsize=9.5)
    for s in ax.spines.values():
        s.set_color('#3a3f4b')
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color='#232733', lw=0.5)


def draw_pads(ax, labels=True, color=PAD_FILL, alpha=1.0):
    for i, ly in enumerate(ROWS):
        for side, cx, nums in ((-1, -PAD_CX, ('1', '2', '3', '4')),
                               (1, PAD_CX, ('8', '7', '6', '5'))):
            n = nums[i]
            ax.add_patch(Rectangle((cx - PAD_W / 2, ly - PAD_H / 2), PAD_W, PAD_H,
                                   facecolor=color, edgecolor=PAD_EDGE, lw=1.0,
                                   alpha=alpha, zorder=4))
            if labels:
                ax.text(cx, ly, n, ha='center', va='center', color='#20242e',
                        fontsize=8.5, weight='bold', zorder=5)


def draw_body(ax, ls='-', alpha=0.30):
    ax.add_patch(Rectangle((-BODY, -BODY_H), 2 * BODY, 2 * BODY_H, facecolor=KO_FILL,
                           alpha=alpha, edgecolor=KO_EDGE, lw=2.0, ls=ls, zorder=2))


# ============================================================ panel 1: as built
ax = fig.add_subplot(gs[0, 0])
frame(ax, '1 — AS BUILT: keep-out covers the whole body',
      'all 8 pad CENTRES lie inside it · pads protrude 0.15 mm past each edge')
draw_body(ax)
draw_pads(ax)
ax.annotate('F.Cu rule area · no tracks / vias / pours',
            xy=(0, 0), xytext=(-3.5, 2.95), color=KO_TXT, fontsize=10.5, weight='bold',
            arrowprops=dict(arrowstyle='->', color=KO_TXT, lw=1.5))
ax.annotate('pad 7 = /I2C_SDA\ncentre +1.10 = 0.40 mm inside',
            xy=(PAD_CX, -0.625), xytext=(3.05, -1.15), color=WARN, fontsize=9.5, weight='bold',
            arrowprops=dict(arrowstyle='->', color=WARN, lw=1.4))
ax.annotate('', xy=(PAD_OUTER, 2.05), xytext=(BODY, 2.05),
            arrowprops=dict(arrowstyle='<->', color=PAD_EDGE, lw=1.6))
ax.text((BODY + PAD_OUTER) / 2, 2.16, '0.15', ha='center', va='bottom',
        color=PAD_EDGE, fontsize=8.5)
ax.text(0, -3.45, 'probe: 3 of 3 escapes anchored at pad centres\n'
                  'flagged items_not_allowed by native DRC',
        ha='center', va='top', color=BAD, fontsize=9, family='monospace')
ax.set_xlim(-4.6, 6.2)
ax.set_ylim(-4.4, 3.5)

# ============================================================ panel 2: the zoom
ax = fig.add_subplot(gs[0, 1])
frame(ax, '2 — ZOOM: the legal anchor band', 'a legal escape exists, but it is 25 µm wide',
      sub_color=WARN)
ax.add_patch(Rectangle((-10, -10), BODY + 10, 20, facecolor=KO_FILL, alpha=0.45,
                       edgecolor=KO_EDGE, lw=2.0, zorder=1))
ax.add_patch(Rectangle((PAD_INNER, -2.2), PAD_W, 3.6, facecolor=PAD_FILL,
                       edgecolor=PAD_EDGE, lw=1.2, zorder=3))
ax.add_patch(Rectangle((LEGAL_MIN, -2.2), WINDOW, 3.6, facecolor=OK, edgecolor='none',
                       alpha=0.95, zorder=6))
# a track anchored at the first legal centre, drawn with its round cap
ax.add_patch(Rectangle((LEGAL_MIN, -1.875 - CAP), 0.9, TRACK_W, facecolor=OK,
                       edgecolor='none', zorder=5))
ax.add_patch(Circle((LEGAL_MIN, -1.875), CAP, facecolor=OK, edgecolor='none', zorder=5))
ax.axvline(BODY, color=KO_EDGE, lw=2.2, zorder=7)
ax.axvline(PAD_OUTER, color=PAD_EDGE, lw=1.8, ls=':', zorder=7)
# Three dimensions, each on its own row, with the text placed to the RIGHT of the plot so the
# 25 um axis never has to hold a sentence. Leaders keep each label attached to its span.
for y, x0, x1, lab, col in (
        (0.66, BODY, PAD_OUTER, '150 µm  keep-out edge → pad edge', PAD_EDGE),
        (0.28, BODY, LEGAL_MIN, '125 µm  track cap radius', KO_TXT),
        (-0.10, LEGAL_MIN, PAD_OUTER, '25 µm  usable for a track centre', OK)):
    ax.annotate('', xy=(x1, y), xytext=(x0, y),
                arrowprops=dict(arrowstyle='<->', color=col, lw=2.2))
    ax.annotate(lab, xy=((x0 + x1) / 2, y), xytext=(1.055, y),
                textcoords=('axes fraction', 'data'), ha='left', va='center',
                color=col, fontsize=8.8, weight='bold',
                arrowprops=dict(arrowstyle='-', color=col, lw=0.8, alpha=0.7))
ax.text((LEGAL_MIN + PAD_OUTER) / 2, -0.52, '25 µm', ha='center', va='top',
        color=OK, fontsize=15, weight='bold')
ax.text(BODY - 0.015, 1.55, 'keep-out\nedge 1.500', ha='right', va='center',
        color=KO_TXT, fontsize=9, weight='bold')
ax.text(PAD_OUTER + 0.012, 1.55, 'pad edge\n1.650', ha='left', va='center',
        color=PAD_EDGE, fontsize=9, weight='bold')
ax.annotate('first legal track centre\n1.625 mm', xy=(LEGAL_MIN, -1.875), xytext=(0.035, 0.30),
            textcoords='axes fraction', ha='left', va='center', color=OK,
            fontsize=8.6, weight='bold',
            arrowprops=dict(arrowstyle='->', color=OK, lw=1.2))
ax.text(0.5, -0.075, 'the round cap radius alone consumes 0.125 mm of the 0.150 mm overhang',
        transform=ax.transAxes, ha='center', va='top', color=WARN, fontsize=8.4)
ax.text(0.5, -0.175, f'one {NETCLEAR*1000:.0f} µm net clearance is 8× this whole band',
        transform=ax.transAxes, ha='center', va='top', color=WARN,
        fontsize=9, weight='bold')
ax.set_xlim(1.34, 1.74)
ax.set_ylim(-3.4, 2.3)
ax.set_xticks([])
ax.set_yticks([-2, 0, 2])
ax.set_ylabel('')

# ============================================================ panel 3: why it happened
ax = fig.add_subplot(gs[0, 2])
frame(ax, '3 — ROOT CAUSE: rule area wider than the free strip',
      'the body is only free of copper between the pad columns')
draw_body(ax, alpha=0.18)
draw_pads(ax, labels=False)
ax.add_patch(Rectangle((-PAD_INNER, -BODY_H), 2 * PAD_INNER, 2 * BODY_H,
                       facecolor=OK, alpha=0.30, edgecolor=OK, lw=1.8, zorder=3))
ax.text(0, 0.05, 'intended\ncopper-free', ha='center', va='center', color=INK,
        fontsize=9.5, weight='bold', zorder=8)
ax.text(0, -0.72, '1.10 mm wide', ha='center', va='center', color='#bfe9d2',
        fontsize=8.5, zorder=8)
ax.annotate('', xy=(PAD_INNER, 2.05), xytext=(-PAD_INNER, 2.05),
            arrowprops=dict(arrowstyle='<->', color=OK, lw=1.8))
ax.text(0, 2.16, '±0.55', ha='center', va='bottom', color=OK, fontsize=9, weight='bold')
ax.text(0, -3.42, 'TE p16 forbids tracks BETWEEN pads.\n'
                  'The rule area also banned them over the pads.',
        ha='center', va='top', color=MUTED, fontsize=9.5)
ax.set_xlim(-3.9, 3.9)
ax.set_ylim(-4.2, 3.0)

# ============================================================ options row
def option(ax, title, verdict, vcolor, fn):
    frame(ax, title, verdict, sub_color=vcolor)
    fn(ax)
    ax.set_xlim(-3.1, 3.1)
    ax.set_ylim(-4.3, 2.9)


# ---- option A: between-pads strip
ax = fig.add_subplot(gs[1, 0])
def opt_a(a):
    draw_pads(a, labels=False)
    a.add_patch(Rectangle((-PAD_INNER, -BODY_H), 2 * PAD_INNER, 2 * BODY_H,
                          facecolor=KO_FILL, alpha=0.45, edgecolor=KO_EDGE, lw=2.0, zorder=2))
    for ly, cx in ((-1.875, PAD_CX), (-0.625, PAD_CX), (1.875, -PAD_CX)):
        a.add_patch(Rectangle((cx, ly - CAP), 1.15 * (1 if cx > 0 else -1), TRACK_W,
                              facecolor=OK, edgecolor='none', zorder=6))
    a.text(0, 0, 'keep-out\n1.10 mm', ha='center', va='center', color=INK,
           fontsize=9.5, weight='bold', zorder=8)
    a.text(0, -3.15, 'unblocks all 8 pads · matches the TE wording\n'
                     'single-line footprint edit · needs its own DRC proof',
           ha='center', va='top', color=OK, fontsize=9)
option(ax, 'OPTION A — keep-out = between the pads',
       'recommended: matches the cited constraint', OK, opt_a)

# ---- option B: pad-edge escape (status quo)
ax = fig.add_subplot(gs[1, 1])
def opt_b(a):
    draw_pads(a, labels=False)
    draw_body(a, ls='--', alpha=0.28)
    a.add_patch(Rectangle((LEGAL_MIN, -2.3), WINDOW, 4.6, facecolor=OK, edgecolor='none',
                          alpha=0.9, zorder=6))
    a.annotate('25 µm', xy=((LEGAL_MIN + PAD_OUTER) / 2, 1.95), xytext=(1.05, 2.35),
               color=OK, fontsize=10.5, weight='bold', ha='center',
               arrowprops=dict(arrowstyle='->', color=OK, lw=1.5))
    a.annotate('', xy=(PAD_OUTER, 1.95), xytext=(LEGAL_MIN, 1.95),
               arrowprops=dict(arrowstyle='<->', color=OK, lw=2.2))
    a.text(0, -3.15, 'no footprint change · legal today\n'
                     'but 25 µm leaves no tolerance budget',
           ha='center', va='top', color=BAD, fontsize=9)
option(ax, 'OPTION B — escape at the 25 µm band',
       'works in CAD; 25 µm leaves no tolerance', BAD, opt_b)

# ---- option C: lengthen lands
ax = fig.add_subplot(gs[1, 2])
def opt_c(a):
    draw_body(a, alpha=0.28)
    for ly in ROWS:
        for cx in (-PAD_CX, PAD_CX):
            a.add_patch(Rectangle((cx - 0.55, ly - PAD_H / 2), PAD_W, PAD_H,
                                  facecolor=PAD_FILL, edgecolor=PAD_EDGE, lw=1.0, zorder=4))
    for ly in ROWS:                      # one extension PER PAD -- a single bar would short them
        a.add_patch(Rectangle((PAD_OUTER, ly - PAD_H / 2), 0.45, PAD_H,
                              facecolor=WARN, alpha=0.5, edgecolor=WARN, lw=1.3, zorder=5))
    a.text(PAD_OUTER + 0.225, 2.62, '+0.45 mm per pad', ha='center', va='bottom',
           color=WARN, fontsize=8.5, weight='bold')
    a.text(0, -3.15, 'widens escape to ~0.45 mm comfortably\n'
                     'but lands no longer TE p16 → requalify',
           ha='center', va='top', color=WARN, fontsize=9)
option(ax, 'OPTION C — lengthen the lands outward',
       'comfortable margin, departs from the cited lands', WARN, opt_c)

fig.text(0.5, 0.028,
         'Measured from PressureSensor:MS5611-01BA03_TE_Recommended at U3, compact.kicad_pcb · '
         'DRC: 3/3 centre-anchored probes flagged; edge probe at x=1.63 mm clean and connected · '
         'no board, footprint or routing changed to make this drawing',
         ha='center', color='#6f7787', fontsize=9)

out = 'sensor-port-keepout-conflict.png'
plt.savefig(out, dpi=150, facecolor=fig.get_facecolor())
print('wrote', out)
print(f'window {WINDOW*1000:.0f} µm · legal min {LEGAL_MIN:.3f} · pad outer {PAD_OUTER:.3f}'
      f' · copper-free strip {2*PAD_INNER:.2f} mm')
