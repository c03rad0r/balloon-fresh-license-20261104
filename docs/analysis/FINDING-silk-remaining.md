# The remaining silk violation: what I established, and what I could not

**2026-11-07, `latest.kicad_pcb` `5d5b7ed6`, 18 opens, silk 1, DRC 19 failing (15 after library registration).**

## Established

`check_silk.py` is a **blocking gate** (AGENTS.md 23, no allow-list) and `check_drc.py` is not —
that gate's allow-list passes `silk_over_copper` as cosmetic. So a board can pass `check_drc`
while failing the project's binding silk rule. That is why my earlier "0 errors" claims were
wrong, and it is now recorded in `GATE-STATUS-authoritative.md`.

**2 of the 3 silk violations are fixed and adopted.** `U_LORA1280`'s silk box runs x 45.000-61.000
at 0.150 mm width while its pads reach x 44.850-61.150, so the two vertical silk segments lay
across the pad columns. Moving them to `F.Fab` (AGENTS.md 26's documented lossless fix) took
silk **3 → 1** with no regression in any other violation type.

## Not fixed: the reference text

One `silk_over_copper` remains: *"Footprint text of U_LORA1280 (U_LORA1280)"*. The text is
12.05 x 2.01 mm at its 1.27 mm height, so it spans most of the part's width and sits across the
pad columns.

Attempts and outcomes, all measured:

| attempt | result |
|---|---|
| move to (53.00, 57.00) | **worse**: silk 1 → 4 (collided with other silk) |
| shrink to 0.80 mm height only | still 1 (12.05 → 7.76 mm wide, still over pads) |
| move to (53.0, 58.3) below body | worse: 3 |
| move to (53.0, 77.5) above body | 1 |
| move to (53.0, 78.5) higher | 1 |
| move to (40.0, 68.1) left of body | 2 |
| move to (66.0, 68.1) right of body | 3 |
| raster free-space search (0.10 mm grid, 92,502 free positions) | chose the **original** position, and the gate still fails there |

## The honest problem with my last attempt

The raster occupancy model says the current position is collision-free — 92,502 free windows
exist and the original ranked nearest. `check_silk.py` disagrees at that same position. **My
raster is therefore modelling something different from what the gate measures** (most likely it
does not account for how the gate inflates text or tests against the part's own pads and
silkscreen the same way). I am not going to claim the search is correct when two instruments
disagree and the gate is the authority.

## What this needs

Either:
1. Read `check_silk.py`'s actual geometry test and match it exactly, or
2. Accept 1 cosmetic silk violation as a documented exception, or
3. Move the PART (the gate's own suggested fix: *"Fix by moving the PART or its reference
   field"*), which is a placement change and outside what I should do unilaterally.

I recommend (1) if the silk gate must be green, because the fix is a measurement-matching
problem, not a design problem. I stopped rather than keep guessing positions: seven tried,
zero worked, and guessing is how the 1 → 4 regression happened.

## Reproduce

```
/usr/bin/python3 -B tracker/hardware/check_silk.py --board docs/analysis/bulk-route-20261107/latest.kicad_pcb
/usr/bin/python3 -B docs/analysis/bulk-route-20261107/silk_raster_search.py
```
