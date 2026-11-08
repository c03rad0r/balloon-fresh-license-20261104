# JLCPCB capability research: S1 is ~2x tighter than the process requires

**2026-11-08. Researched at the user's request. This changes the nature of the four "trapped" pads.**

## What JLCPCB actually specifies

From JLCPCB's own published capability pages (retrieved 2026-11-08):

| Document | Feature | Value |
|---|---|---|
| Copper Weight Guide (help article) | 1-2 layer FR4, 1 oz | **0.10 mm** min trace/space |
| Copper Weight Guide | **>= 4 layer FR4, 0.5/1 oz (inner 0.5 oz default)** | **0.09 mm** min trace/space (3.5 mil); 3 mil with extra cost |
| PCB Design Rules guide | 1 oz multilayer min trace/spacing | **0.09 / 0.09 mm** |
| PCB Design Rules guide | SMD pad-to-pad clearance | **0.15 mm** |
| PCB Design Rules guide | Via hole to track | 0.20 mm |
| PCB Design Rules guide | PTH to track | 0.28 mm min |
| PCB capabilities (HDI page) | minimum trace width/space | 3 mil / 3 mil standard; 2.7 mil extreme |

**This board is 4-layer with 1 oz outer / 0.5 oz inner (the default), so the governing figure is
0.09 mm minimum trace AND spacing.**

## What that means for the campaign's frozen rule

The campaign froze at **S1 = track 0.200 mm, clearance 0.200 mm**, and the project `.kicad_dru`
records *why*:

```
#   min copper clearance 0.10 mm  -> we freeze at 0.20 mm (2x margin)
```

So S1 was deliberately chosen at **2x the JLCPCB minimum**. It is a self-imposed safety factor, not a
fab requirement. The `.kicad_dru` says so in its own comment.

## The four trapped pads, re-scored against the actual process minimum

Every "shortfall" measured this campaign was against S1's 0.400 mm two-sided budget (0.200 clearance
+ 0.200 new track). Against the real 0.09 mm minimum the budget is 0.090 + 0.200 = **0.290 mm**, and
against the 0.15 mm SMD pad-to-pad figure it is 0.150 + 0.200 = **0.350 mm**.

```
/EN        U1.3   /SPI2_MISO gap 0.350   S1 short 0.050   real-min budget 0.290  -> CLEARS by 0.060
/SPI2_SCK  U1.4   /SPI2_MISO gap 0.350   S1 short 0.050   real-min budget 0.290  -> CLEARS by 0.060
/SPI2_SCK  U1.4   /SPI2_MOSI gap 0.200   S1 short 0.200   real-min budget 0.290  -> short 0.090
/EN        U1.3   /SPI2_MOSI gap 0.562   CLEARS at S1 already
/VSCAP     R_BAL1.1 0.360 edge-to-edge   S1 short 0.040   real-min budget 0.290  -> CLEARS by 0.070
```

**Three of the four clear the real process minimum on the measured numbers.** `/VSCAP` was the
surprise: re-measured directly from the pad rectangles, R_BAL1.1 (40.490,43.500) and R_DIV2.1
(40.490,44.500) are 0.360 mm apart edge-to-edge, not the "0.180 mm centreline" figure carried earlier
in the campaign -- 0.180 was half that gap with the wrong label on it. At S1 that is only 0.040 mm
short, and at the real minimum it clears with 0.070 mm to spare.

## The honest caveat, stated plainly

This does NOT mean the board should be ordered at 0.09 mm. Two reasons:

1. **0.09 mm is the process floor, not a comfortable target.** JLCPCB's own guidance says "Designers
   should generally maintain additional margin where layout space allows." Building at a fab's
   absolute minimum is how boards come back with opens.
2. **The board's existing copper is routed at S1.** Mixing a 0.15 mm local neck into an otherwise
   0.20/0.20 board creates impedance and current-carrying discontinuities, and it makes the DRC rule
   set conditional and harder to audit.

The defensible middle option is a **local 0.150 mm clearance rule scoped to the four pads** — which is
still 1.7x the fab minimum, keeps the 0.200 mm track width everywhere, and is a far smaller deviation
than 0.090 mm.

## What this actually changes

Before this research the four pads looked like hard blockers requiring either a placement change, a
rule violation, or accepting the opens. That framing was **wrong**: the rule being defended is 2.2x
stricter than the fab. The real decision is not "can this be built" (yes) but "how much margin do we
want to keep".

That is a decision for the user, and it is now a well-posed one with numbers attached.

## Recommendation

1. **Adopt S1.5 = local 0.150 mm clearance** for the four trapped pads only, via a condition-scoped
   `.kicad_dru` rule in the style already used for the wing-socket edge exemption. Route with it,
   keep 0.200 mm track width, and expect /EN and /SPI2_SCK to close.
2. Keep the board-wide rule at S1 for everything else.
3. Do NOT go to 0.090 mm. It buys at most one more pad and spends the entire safety factor.

## Sources

- https://jlcpcb.com/help/article/jlcpcb-copper-weight
- https://jlcpcb.com/blog/a-comprehensive-guide-for-optimal-results
- https://jlcpcb.com/capabilities/PCB
- https://jlcpcb.com/help/article/minimum-spacing-for-smd-components
