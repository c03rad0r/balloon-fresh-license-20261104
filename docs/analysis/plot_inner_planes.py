"""Render why the freerouting candidate was rejected: signal copper on the inner GND plane.

One picture, two facts that are hard to hold together in prose:
  - the freerouted board has FEWER opens (10 vs 15), which looks like progress
  - it also has 60 clearance violations, 20 hole_clearance and 6 track_width, which is disqualifying

The most legible single cause is the inner layers. In1.Cu is a solid GND pour and In2.Cu is +3V3.
Freerouting logged all four layers as "power plane ... configured for plane routing" and then laid
signal tracks onto them. This renders, for the rejected candidate:

  red    = non-plane signal tracks on In1.Cu   (copper that must not exist there)
  grey   = the In1 GND pour outline
  yellow = board outline

and, for comparison, the same view of the live board where those tracks do not exist.
"""

import sys
import pcbnew as p
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

UM = 1_000_000.0
BASE = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = BASE + '/latest.kicad_pcb'
NEW = BASE + '/batches/FREEROUTING/routed.kicad_pcb'
OUT = BASE + '/DECISION-freerouting-inner-planes.png'


def inner_signal(board):
    """Tracks and vias on In1.Cu/In2.Cu whose net is not the plane's own net."""
    b = p.LoadBoard(board)
    plane_net = {}
    for lay, name in ((p.In1_Cu, 'In1.Cu'), (p.In2_Cu, 'In2.Cu')):
        counts = {}
        for z in b.Zones():
            if z.IsOnLayer(lay):
                try:
                    a = abs(z.GetFilledPolysList(lay).Area()) / (UM * UM)
                except Exception:
                    a = 0.0
                counts[z.GetNetname()] = max(counts.get(z.GetNetname(), 0.0), a)
        plane_net[name] = max(counts, key=counts.get) if counts else None

    out = []
    for t in b.GetTracks():
        lay = b.GetLayerName(t.GetLayer())
        if lay not in plane_net:
            continue
        if t.GetNetname() == plane_net[lay]:
            continue
        s, e = t.GetStart(), t.GetEnd()
        out.append((lay, str(t.GetNetname()), s.x / UM, s.y / UM, e.x / UM, e.y / UM,
                    t.Type() == p.PCB_VIA_T))
    return out, plane_net, b


def zones_outline(b, lay):
    segs = []
    for z in b.Zones():
        if not z.IsOnLayer(lay):
            continue
        try:
            poly = z.GetFilledPolysList(lay)
        except Exception:
            continue
        if poly is None:
            continue
        for i in range(poly.OutlineCount()):
            ch = poly.Outline(i)
            n = ch.PointCount()
            pts = [(ch.CPoint(k).x / UM, ch.CPoint(k).y / UM) for k in range(n)]
            segs.append(pts)
    return segs


def draw(ax, board, title):
    bad, plane_net, b = inner_signal(board)
    for lay, col in ((p.In1_Cu, '#666666'),):
        for pts in zones_outline(b, lay):
            xs = [q[0] for q in pts]
            ys = [q[1] for q in pts]
            ax.plot(xs, ys, color='#3a3a3a', lw=0.6, zorder=1)

    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetLeft() / UM, bb.GetTop() / UM
    ax.add_patch(Rectangle((x0, y0), bb.GetWidth() / UM, bb.GetHeight() / UM,
                           fill=False, edgecolor='#d8c040', lw=1.2, zorder=4))

    n_tr = n_vi = 0
    for lay, net, sx, sy, ex, ey, isvia in bad:
        if isvia:
            ax.plot([sx], [sy], 'o', color='#ff4040', ms=5, zorder=6)
            n_vi += 1
        else:
            ax.plot([sx, ex], [sy, ey], color='#ff4040', lw=1.4, zorder=5,
                    solid_capstyle='round')
            n_tr += 1

    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set_title(title, color='#e8e8e8', fontsize=10, loc='left')
    ax.set_facecolor('#101010')
    for s in ax.spines.values():
        s.set_color('#444444')
    ax.tick_params(colors='#999999', labelsize=7)
    return n_tr, n_vi, plane_net


fig, axes = plt.subplots(1, 2, figsize=(15, 8.4), facecolor='#101010')
r1 = draw(axes[0], LIVE, 'LIVE board  e00b98e7  --  15 opens')
r2 = draw(axes[1], NEW, 'FREEROUTED candidate  --  10 opens, 63 violations  REJECTED')

fig.suptitle('Signal copper on the inner GND plane (In1.Cu):  red = must not be there',
             color='#f0f0f0', fontsize=12, x=0.012, ha='left')
fig.text(0.012, 0.028,
         'left: %d track(s), %d via(s) on In1/In2 -- plane nets %s\n'
         'right: %d track(s), %d via(s) on In1/In2 -- plane nets %s\n'
         'Freerouting logged all four layers as "power plane ... configured for plane routing", then '
         'routed signal into them.'
         % (r1[0], r1[1], r1[2], r2[0], r2[1], r2[2]),
         color='#b8b8b8', fontsize=8.4, ha='left', va='bottom')
fig.tight_layout(rect=[0, 0.075, 1, 0.945])
fig.savefig(OUT, dpi=125, facecolor='#101010')
print('saved %s' % OUT)
print('live  : %d tracks, %d vias on inner layers, plane nets %s' % (r1[0], r1[1], r1[2]))
print('new   : %d tracks, %d vias on inner layers, plane nets %s' % (r2[0], r2[1], r2[2]))
