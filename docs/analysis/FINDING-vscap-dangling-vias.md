# /VSCAP dangling vias: what is real, what my probes got wrong, and the one open question

**Measured 2026-11-07, `latest.kicad_pcb` (22 opens / 24 warnings / project gate 21 failing).**

## What DRC reports

```
via_dangling: Via [/VSCAP] on F.Cu - B.Cu  @(36.0000, 40.0000)
via_dangling: Via [/VSCAP] on F.Cu - B.Cu  @(6.6000, 58.5997)
```

Two, not six. Six `/VSCAP` vias exist on the board.

## My probe said six. My probe was wrong — twice.

Version 1 counted a via as touched only when a copper object's shape collided with a 2 um
disc at the via centre. It reported **6 of 6 dangling**. Version 2 widened the tolerance to
0.30 mm (the actual land radius) and still reported 6 of 6, because **it only looked at
tracks and pads and never at zone fills.** `/VSCAP` has a B.Cu pour of 4207.09 mm2 in two
islands; the pour is the copper those vias land on.

Version 3 tests zone fill directly: **all six vias sit inside the B.Cu `VSCAP` pour.**

    via (46.5287, 54.7197)  in pour: B.Cu   connected
    via (36.0000, 40.0000)  in pour: B.Cu   connected
    via ( 6.6000, 58.5997)  in pour: B.Cu   connected
    via (41.8394, 42.6522)  in pour: B.Cu   connected
    via ( 3.3329, 46.2611)  in pour: B.Cu   connected
    via (48.7963, 56.6197)  in pour: B.Cu   connected

So there is no via sitting in bare laminate. Any "dangling via" story that says these barrels
lead nowhere is wrong.

## The open question, stated as a question

If all six land in a pour, why does DRC call exactly two of them dangling? The pour has
**two islands**. The consistent hypothesis is that those two vias land in the island that is
**not** connected to the rest of the net -- i.e. the same split-pour condition that produces
the `/VSCAP` zone-pair open. That would make the two `via_dangling` warnings and the
`/VSCAP` zone open **one defect, not three**, and it would mean `/VSCAP` is genuinely split
across a pour island boundary.

I have not proven which island each via is in. That is the measurement to do next, and it is
worth doing because if the hypothesis holds, fixing the pour connection closes a zone-pair
open and removes two warnings at once.

## What is certainly true

- The project's own gate `tracker/hardware/check_drc.py --board <live>` **FAILS**: 21 failing
  violations, 25 allowed, 22 unconnected. The board is not gate-clean by the repo's own
  standard (AGENTS.md §21 requires DRC 0 before a board commit is legitimate).
- My earlier statement that the board had "0 errors" referred to *error-severity* items in
  `kicad-cli` JSON. The repo's gate counts differently and is stricter. Both are accurate
  about different things, and the stricter one is the one that governs ordering.

## Reproduce

```
/usr/bin/python3 -B tracker/hardware/check_drc.py --board docs/analysis/bulk-route-20261107/latest.kicad_pcb
```
