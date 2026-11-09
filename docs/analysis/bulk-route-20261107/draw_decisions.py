"""Draw the two decisions as a SIDE-BY-SIDE SIGNAL TABLE, not a plan view.

v1 drew this in plan view and vision_analyze found the fatal flaw: two of U_C's four dead-net
labels landed inside U3's outline, so the picture appeared to attribute them to the WRONG PART.
On a diagram whose entire job is "these pins belong to THAT part", that is not a cosmetic
overlap -- it is the drawing asserting the opposite of the finding.

So the left panel is now a table keyed by signal, one row per control line, with the measured
track count printed next to each side. A reader cannot misassign a row. The right panel keeps the
board view, because there the geometry IS the argument.

All coordinates and track counts come from the board file.
"""
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Circle
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
MM = 1e6
BD = os.path.join(HERE, 'work.kicad_pcb')
OUT = os.path.join(HERE, 'assets', 'decisions-uc-and-wires.png')

b = pcbnew.LoadBoard(BD)


def pads_of(ref):
    for fp in b.GetFootprints():
        if fp.GetReference() == ref:
            return fp, list(fp.Pads())
    return None, []


def xy(p):
    return p.GetPosition().x / MM, p.GetPosition().y / MM


def tracks_on(net):
    return sum(1 for t in b.GetTracks() if t.GetNetname() == net and t.GetClass() != 'PCB_VIA')


SIGNALS = ['CS_N', 'BUSY', 'RESET_N', 'IRQ']
rows = [(s, tracks_on(f'/U_C_{s}'), tracks_on(f'/U3_{s}')) for s in SIGNALS]

edges = []
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts and d.GetClass() == 'PCB_SHAPE':
        st, en = d.GetStart(), d.GetEnd()
        edges.append(((st.x / MM, st.y / MM), (en.x / MM, en.y / MM)))
xs = [c[0] for seg in edges for c in seg]
ys = [c[1] for seg in edges for c in seg]
X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)

fig = plt.figure(figsize=(17.0, 8.6))
gs = fig.add_gridspec(1, 2, width_ratios=[1.06, 1.0], wspace=0.16)
axL = fig.add_subplot(gs[0, 0])
axR = fig.add_subplot(gs[0, 1])

# ============================================================== LEFT: signal table
axL.set_title('DECISION 1 — U_C cannot be commanded\n'
              'same part, same SPI1 bus, four control lines with no MCU end',
              fontsize=12.5, pad=12)
axL.axis('off')

colX = {'sig': 0.06, 'uc': 0.40, 'u3': 0.76}
axL.text(0.02, 0.955, 'signal', fontsize=10.5, fontweight='bold', color='#34495e')
axL.text(colX['uc'], 0.955, 'U_C  (DNP on v10)', fontsize=10.5, fontweight='bold',
         color='#c0392b', ha='center')
axL.text(colX['u3'], 0.955, 'U3  (fitted)', fontsize=10.5, fontweight='bold',
         color='#1f6f3f', ha='center')

y = 0.875
for sig, n_uc, n_u3 in rows:
    axL.text(colX['sig'], y, sig, fontsize=11.5, family='monospace')
    axL.add_patch(Rectangle((colX['uc'] - 0.135, y - 0.033), 0.27, 0.058,
                            fc='#f5b7b1', ec='#c0392b', lw=1.3))
    axL.text(colX['uc'], y - 0.004, f'{n_uc} tracks  \u2717', fontsize=10, ha='center',
             color='#7b241c', fontweight='bold')
    axL.add_patch(Rectangle((colX['u3'] - 0.135, y - 0.033), 0.27, 0.058,
                            fc='#abebc6', ec='#1f6f3f', lw=1.3))
    axL.text(colX['u3'], y - 0.004, f'{n_u3} tracks  \u2713', fontsize=10, ha='center',
             color='#145a32', fontweight='bold')
    y -= 0.086

axL.text(0.02, 0.475, 'the constraint is not routing \u2014 it is GPIO count',
         fontsize=10.5, fontweight='bold', color='#7d6608')
axL.text(0.02, 0.428,
         'needed for U_C           4   CS_N, BUSY, RESET_N, IRQ\n'
         'usable free on U1        2   IO3 (pad 15), IO42 (pad 35)\n'
         'input-only, unusable     2   pad 16 (IO46), pad 26 (IO48)\n'
         'octal-PSRAM, unusable    3   pad 28/29/30 (IO35/36/37)',
         fontsize=9.6, family='monospace', va='top', linespacing=1.7)

axL.text(0.02, 0.245,
         'Short by 2 GPIOs. U_C cannot be given all four signals on v10 without\n'
         'taking one from a function that already has it.',
         fontsize=9.4, color='#7b241c', va='top', linespacing=1.5)

axL.text(0.02, 0.150,
         'why DNP is the cheap answer:\n'
         'U3 already carries a complete LoRa2021 on the same SPI1 bus with all\n'
         'four control lines routed. Dropping U_C costs redundancy, not function\n'
         '\u2014 and saves one LoRa2021 (~$12).',
         fontsize=9.4, va='top', linespacing=1.55,
         bbox=dict(fc='#fdfefe', ec='#aeb6bf', lw=0.9, pad=7))

# ============================================================== RIGHT: board view
axR.add_patch(Rectangle((X0, Y0), X1 - X0, Y1 - Y0, fc='#f7f9f7', ec='#2c3e50', lw=2.0,
                        zorder=0))
axR.set_title('DECISION 2 \u2014 two wires, both flash-time only\n'
              'neither affects flight; both are optional',
              fontsize=12.5, pad=12)

for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        continue
    s, e = t.GetStart(), t.GetEnd()
    axR.plot([s.x / MM, e.x / MM], [s.y / MM, e.y / MM], color='#ccd6cc', lw=0.45, zorder=1)


def pad_at(ref, num):
    _, pads = pads_of(ref)
    for p in pads:
        if p.GetNumber() == num:
            return p
    return None


# (name, refA, padA, refB, padB, colour, note, callout xy in DATA coords, label anchor)
WIRES = [
    ('/EN', 'U1', '3', 'J_PROG', '3', '#c0392b', 'hard reset from the header',
     (X0 + 3.0, Y1 - 8.5)),
    ('/IO0', 'U1', '27', 'J_PROG', '6', '#8e44ad', 'force download mode',
     (X0 + 3.0, Y1 - 2.5)),
]
for name, ra, pa, rb, pb, col, note, offset in WIRES:
    a = pad_at(ra, pa)
    c = pad_at(rb, pb)
    ax_, ay_ = xy(a)
    bx_, by_ = xy(c)
    for p, lbl, side in ((a, f'{ra}.{pa}', 9), (c, f'{rb}.{pb}', -46)):
        px, py = xy(p)
        axR.add_patch(Circle((px, py), 1.15, fc=col, ec='k', lw=0.9, zorder=9))
        axR.annotate(lbl, (px, py), textcoords='offset points', xytext=(side, 0),
                     fontsize=8.6, va='center', color=col, fontweight='bold', zorder=12)
    axR.add_patch(FancyArrowPatch((ax_, ay_), (bx_, by_), arrowstyle='-', lw=2.4, color=col,
                                  zorder=8, linestyle=(0, (6, 3)),
                                  connectionstyle='arc3,rad=0.20'))
    d = ((ax_ - bx_) ** 2 + (ay_ - by_) ** 2) ** 0.5
    cx, cy = offset
    axR.annotate(f'{name}  {d:.1f} mm\n{note}', xy=((ax_ + bx_) / 2, (ay_ + by_) / 2),
                 xytext=(cx, cy), fontsize=9.2, fontweight='bold', color=col, ha='left',
                 va='center', zorder=11,
                 bbox=dict(fc='white', ec=col, lw=1.1, pad=3.8, alpha=0.98),
                 arrowprops=dict(arrowstyle='-', lw=1.0, color=col,
                                 shrinkA=2, shrinkB=6))

for num, lbl in (('4', 'D-'), ('5', 'D+')):
    p = pad_at('J_PROG', num)
    px, py = xy(p)
    axR.add_patch(Circle((px, py), 1.9, fill=False, ec='#e67e22', lw=2.0, zorder=9))
    axR.annotate(f'USB_{lbl}', (px, py), textcoords='offset points', xytext=(13, 0),
                 fontsize=8.6, color='#b9770e', va='center', zorder=10)

for ref in ('U1', 'J_PROG'):
    fp, _ = pads_of(ref)
    axR.annotate(ref, (fp.GetPosition().x / MM, fp.GetPosition().y / MM - 13.5),
                 ha='center', fontsize=11, fontweight='bold', color='#2c3e50', zorder=10)

axR.text(0.015, 0.982,
         'orange rings = the USB pins /IO0 must cross.\n'
         'The router shorts /IO0 to them on every attempt,\n'
         'which is why these stay wires and not copper.',
         transform=axR.transAxes, fontsize=8.3, va='top', family='monospace',
         bbox=dict(fc='white', ec='#e67e22', lw=0.9, pad=5), zorder=12)

axR.set_xlim(X0 - 5, X1 + 10)
axR.set_ylim(Y1 + 6, Y0 - 5)
axR.set_aspect('equal')
axR.set_xticks([])
axR.set_yticks([])

fig.suptitle('Balloon hub v10 \u2014 the two decisions that remain', fontsize=14, y=0.975)
fig.savefig(OUT, dpi=150, bbox_inches='tight')
print('wrote', OUT)
print('\nmeasured control-line track counts:')
for sig, n_uc, n_u3 in rows:
    print(f'  {sig:8s} U_C={n_uc:3d}   U3={n_u3:3d}')
