# Independent gerber render: outline closed, copper correct, wing slots proper

**2026-11-07, gerbers from `latest.kicad_pcb` `ec2a7af8`, rendered with `gerbv` — not KiCad's plotter.**

## Why this check exists

Every previous look at the board used KiCad's own renderer or its own DRC. If the plotter had a
fault, both would agree with each other and both would be wrong. `gerbv` is a separate
implementation that parses the emitted RS-274X files directly, so it can catch a plotting error
KiCad would not report.

## Render

```
gerbv --export=png --dpi=600 --background=#000000 \
      --foreground=#00FF00 board-F_Cu.gtl \
      --foreground=#FF0000 board-B_Cu.gbl \
      --foreground=#FFFF00 board-Edge_Cuts.gm1
```

gerbv logged `Unknown RS-274X extension found %TD%/%TO%` — it does not implement the newer
attribute extensions KiCad emits. Attributes carry metadata only, not geometry, so the render is
still faithful; JLCPCB's parser handles them.

## Findings

**Outline: complete, closed, and more than a rectangle.** The render shows the outer rectangle
closed on all four sides with all corners joined, **plus four narrow inward-projecting features
at the side midpoints**.

That last point is real geometry, and I initially missed it. `GetDrawings()` reports only **one**
Edge.Cuts item — a `SHAPE_T_RECT` spanning (−0.05, −0.05) to (72.05, 80.05), 72.10 x 80.10 mm.
The four projections are **footprint graphics on Edge.Cuts**, which `GetDrawings()` does not
return:

```
Footprint graphics on Edge.Cuts: 16
```

Verified as exactly the wing-socket slots, each a closed contour:

| ref | segments | endpoints | odd-degree | verdict |
|---|---|---|---|---|
| J_W1 | 4 | 4 | 0 | **CLOSED** |
| J_W2 | 4 | 4 | 0 | **CLOSED** |
| J_W3 | 4 | 4 | 0 | **CLOSED** |
| J_W4 | 4 | 4 | 0 | **CLOSED** |

Zero odd-degree endpoints means no dangling edge anywhere in the outline. A slot with an open
end is a fab question; these have none.

**Copper: both outer layers present and coherent.** Green F.Cu and red B.Cu both visible across
the board with identifiable tracks, pads and clearances. No large missing-copper region, no
truncated pour.

**Nothing outside the outline.** No copper crosses the rectangle.

## What this does not verify

- inner layers In1/In2 were not rendered (the composite covered F.Cu, B.Cu and Edge.Cuts only)
- drill registration, mask openings, annular rings, minimum track/space, copper-to-edge distance
- contour closure of the *rectangle itself* by graph method — it is a `SHAPE_T_RECT` primitive, so
  it is closed by construction rather than by joined segments
- electrical connectivity: 18 opens remain

## Reproduce

```
gerbv --export=png --dpi=600 --background=#000000 --foreground=#FFFF00 <Edge_Cuts>.gm1
```
