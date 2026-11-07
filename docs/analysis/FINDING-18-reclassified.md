# Reclassification of the 18 opens: 5 assembly lands, 4 pour artefacts, 9 real

**Measured 2026-11-07 on `latest.kicad_pcb` (18 opens / 19 library-drift violations / 0 electrical).**

This corrects my own classifications from earlier in the campaign. Two of them were wrong.

## The corrected breakdown

| class | count | what it is |
|---|---|---|
| Assembly lands (by design) | **5** | two-face wing pads: SMD copper both faces, no barrel, joined when the tab is soldered |
| Pour / thermal artefacts | **4** | 3 GND zone records (pours joined by 61 stitches) + 1 `/VSCAP` thermal-relief pad at its declared 0.500 mm gap |
| Real unrouted connections | **9** | trapped terminals + wing-area track/pad transitions |

## What changed and why

**`/CUT_SENSE_W1` was misclassified as a trapped terminal.** It is an assembly land. Its copper:

```
PAD J_W1.3  (3.000,40.900)  F.Cu  4.00 x 1.20
PAD J_W1.3  (3.000,40.900)  B.Cu  4.00 x 1.20     <- same position, both faces, no drill
F.Cu run  J_W1.3 -> (3.280,45.350)
VIA       (3.280,45.350)                          <- joins F.Cu run to B.Cu
B.Cu run  (3.280,45.350) -> (6.350,46.050)  ==  U_CUT1.3 at (6.362,46.050)
```

The F.Cu face is fully routed, crosses to B.Cu through a legal via, and the B.Cu run reaches
`U_CUT1.3`. The only unjoined thing is **F.Cu pad face to B.Cu pad face** — the same connector
land on two faces with no barrel. That is WING_TAB_4P / ADR-120 R1 territory: it joins in
assembly, and routing or via-ing there is wrong. The router's 424-step refusal was correct.

**`CUT_SENSE_W2/W3/W4` were also misclassified** — as assembly lands — when they were in fact
pad-to-track gaps. Those three were routable and were closed (CUTSENSE2, opens 21 -> 18).

So the same four `CUT_SENSE` opens contained both kinds: three real pad-to-track gaps and one
two-face assembly land. My original lumping of all four as assembly lands hid three routable
opens; my correction then assumed all four were routable and the last one refused.

## Honest state

18 opens reported by DRC. Nine are real unrouted copper. The other nine are by-design or
artefact, and none of the nine is improved by routing at S1.

Nothing here changes what DRC says or what should be reported: **18 opens**. The value of the
classification is in what an order decision should weigh — 9 real connections rather than 18.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/zone_pair_verify.py
/usr/bin/python3 -B docs/analysis/bulk-route-20261107/remain1_batch.py
```
