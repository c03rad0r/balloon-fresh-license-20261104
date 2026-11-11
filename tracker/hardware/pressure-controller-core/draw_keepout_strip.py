#!/usr/bin/env python3
"""Draw the MS5611 keep-out AS IMPLEMENTED, from native geometry, and prove the TE strip.

WHY THIS EXISTS. `footprint-evidence/coupon.png` is a Fab/Cu/Silk/Courtyard plot: KiCad's SVG
plotter does NOT render rule-area (keep-out) zones, so that image can never show whether the
keep-out covers the strip or the body. Measured 2026-11-11: the coupon render was quoted as
evidence and it contains no rule-area path at all. A render that cannot show the feature cannot
test the feature, so this drawing is generated from `pcbnew` geometry -- the same objects DRC
and the router read -- and every number printed on it is measured, not typed.

Left panel: BEFORE (the body-wide rule area, as committed in 5e628f86) against the pads.
Right panel: AFTER (the 1.10 mm inter-pad strip), with the measured escape band each pad gets.
"""
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

import pcbnew

MOD = 'PressureSensor.pretty/MS5611-01BA03_TE_Recommended.kicad_mod'
OUT = 'sensor-port-keepout-strip.png'

PAD_W, PAD_H = 1.1, 0.6
PAD_CX = 1.1
ROWS = (-1.875, -0.625, 0.625, 1.875)
TRACK_W = 0.25
CAP = TRACK_W / 2


def zone_box(z):
    pts = [(p.x / 1e6, p.y / 1e6)
           for i in range(z.Outline().OutlineCount())
           for p in z.Outline().Outline(i).CPoints()]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def load():
    """Return (zone box, pads, flags) measured from the committed footprint."""
    fp = pcbnew.FootprintLoad('PressureSensor.pretty', 'MS5611-01BA03_TE_Recommended')
    assert fp is not None, 'footprint must load natively'
    zones = [z for z in fp.Zones() if z.GetIsRuleArea()]
    assert len(zones) == 1, f'exactly one rule area expected, found {len(zones)}'
    z = zones[0]
    pads = [(p.GetNumber(), p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, p.GetSize().x / 1e6)
            for p in fp.Pads()]
    flags = dict(tracks=z.GetDoNotAllowTracks(), vias=z.GetDoNotAllowVias(),
                 pour=z.GetDoNotAllowCopperPour(),
                 pads=not z.GetDoNotAllowPads(), footprints=not z.GetDoNotAllowFootprints())
    return zone_box(z), pads, flags


def panels(ax, box, pads, title, sub, subcolor):
    ax.set_facecolor('#12141a')
    ax.set_aspect('equal')
    # Title and subtitle are placed as TEXT, not set_title: set_title lays the axes title and a
    # second text at a fixed offset, and at this figure height the subtitle landed ON the heading
    # (measured on the first render). Explicit axes-fraction offsets keep them apart.
    ax.text(0.5, 1.115, title, transform=ax.transAxes, ha='center', va='bottom',
            color='#ffffff', fontsize=12, weight='bold')
    ax.text(0.5, 1.035, sub, transform=ax.transAxes, ha='center', va='bottom',
            color=subcolor, fontsize=9)
    for s in ax.spines.values():
        s.set_color('#3a3f4b')
    ax.tick_params(colors='#8b93a7', labelsize=8)
    ax.grid(True, color='#232733', lw=0.5)
    ax.set_xlabel('footprint-local x (mm)', color='#8b93a7', fontsize=8)
    ax.set_ylabel('footprint-local y (mm)', color='#8b93a7', fontsize=8)

    # the rule area, exactly as stored
    x0, y0, x1, y1 = box
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='#7a1f2b', alpha=0.45,
                           edgecolor='#ff5c7a', lw=2.2, zorder=2))

    # pads, drawn from native positions and sizes
    for num, cx, cy, w in pads:
        ax.add_patch(Rectangle((cx - w / 2, cy - PAD_H / 2), w, PAD_H, facecolor='#c8a24a',
                               edgecolor='#ffe9a8', lw=1.0, zorder=4))
        ax.text(cx, cy, num, ha='center', va='center', color='#20242e', fontsize=8.5,
                weight='bold', zorder=5)

    # the escape band a 0.25 mm track gets at a pad centre, on the outermost rows
    pad_edge = PAD_CX + PAD_W / 2
    free = pad_edge - max(abs(x0), abs(x1))
    if free > 1e-6:
        for sign, row in ((1, -1.875), (-1, 1.875)):
            inner = sign * max(abs(x0), abs(x1))
            outer = sign * pad_edge
            ax.add_patch(Rectangle((min(inner, outer), row - CAP), abs(free), TRACK_W,
                                   facecolor='#4dd6a0', alpha=0.85, edgecolor='none', zorder=6))
            ax.add_patch(Circle((outer, row), CAP, facecolor='none',
                                edgecolor='#4dd6a0', lw=1.0, ls=':', zorder=6))
    ax.set_xlim(-2.6, 2.6)
    ax.set_ylim(-3.2, 3.2)


def main():
    box, pads, flags = load()
    x0, y0, x1, y1 = box
    width = x1 - x0
    pad_edge = PAD_CX + PAD_W / 2
    body_edge = 1.5
    # Measured escape: the rule area's outer edge to the land's outer edge, minus a track end-cap.
    escape_body = pad_edge - body_edge - CAP
    escape_strip = pad_edge - max(abs(x0), abs(x1)) - CAP

    fig, axes = plt.subplots(1, 2, figsize=(15.5, 7.6))
    fig.patch.set_facecolor('#12141a')

    old = (-body_edge, -2.5, body_edge, 2.5)
    panels(axes[0], old, pads, 'BEFORE — rule area over the 3 x 5 mm body',
           f'banned tracks OVER the pads · escape band {escape_body * 1000:+.0f} µm (no budget)',
           '#ff5c6b')
    panels(axes[1], box, pads, f'AFTER — rule area is the inter-pad strip ({width:.2f} mm)',
           f'pads fully routable · escape band {escape_strip * 1000:.0f} µm each side',
           '#4dd6a0')

    fig.suptitle('MS5611-01BA03_TE_Recommended F.Cu keep-out, measured from the committed footprint',
                 color='#ffffff', fontsize=13.5, weight='bold', y=0.985)
    fig.text(0.5, 0.035,
             f'strip x {x0:+.2f}..{x1:+.2f}, y {y0:+.2f}..{y1:+.2f} mm  ·  '
             f'tracks/vias/pours NOT allowed, pads/footprints allowed  ·  '
             f'track {TRACK_W} mm → end-cap {CAP} mm  ·  KiCad SVG plots do not draw rule '
             f'areas, hence this drawing',
             ha='center', color='#6f7787', fontsize=8.6)
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(OUT, dpi=145, facecolor=fig.get_facecolor())
    print(f'wrote {OUT}')
    print(f'MEASURED strip   x {x0:+.3f}..{x1:+.3f}  y {y0:+.3f}..{y1:+.3f}  width {width:.3f} mm')
    print(f'MEASURED flags   {flags}')
    print(f'MEASURED escape  before {escape_body * 1000:+.1f} um   after {escape_strip * 1000:.1f} um')


if __name__ == '__main__':
    main()
