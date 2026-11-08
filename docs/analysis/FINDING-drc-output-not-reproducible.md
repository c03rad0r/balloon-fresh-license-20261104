# FINDING: kicad-cli's unconnected_items output is not reproducible; count is, identity is not

Measured 2026-11-08 on board `322ade1e`, six consecutive DRC runs of **the same unmodified
file**, then four more on each of two boards.

## The measurement

```
record count   : [11, 11, 11, 11, 11, 11]                       STABLE
descriptions   : 8 of 14 distinct variants did not appear
                 in every run                                   UNSTABLE
net-name sets  : identical in all runs                          STABLE
```

The same defect is described two different ways across runs:

```
"Pad 4 [/W3_SOLAR_N] of J_W3 on B.Cu || Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu"        (x3)
"Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu || Track [/W3_SOLAR_N] on B.Cu, 3.3004 mm"    (x3)

"Track [/W2_SOLAR_N] on B.Cu || Track [/W2_SOLAR_N] on F.Cu, 2.2000 mm"            (x5)
"Track [/W2_SOLAR_N] on B.Cu || Track [/W2_SOLAR_N] on F.Cu, 1.2000 mm"            (x1)

"Pad 1 [/VSCAP] of R_BAL1 on F.Cu || Track [/VSCAP] on F.Cu, 1.0687 mm"            (x3)
"Pad 1 [/VSCAP] of R_BAL1 on F.Cu || Via [/VSCAP] on F.Cu - B.Cu"                  (x3)
```

That last pair is not two defects — it is one defect, and KiCad chose a different member of the
net's connected cluster to name each time.

## Why this matters more than it looks

Every before/after gate in this campaign compared **descriptions**. That is a comparison of an
unstable field. It produces phantom changes on an unchanged board:

- A diff keyed on descriptions reported "CLOSED 2 / NEW 2" for a board that had changed by one
  via, and the two boards' **net-key multisets were identical across all 8 runs**.
- The `/VSCAP` "Pad ↔ Track" → "Pad ↔ Via" transition, which I read as evidence the via changed
  the topology, is one of the two descriptions the same defect produces anyway.

**Conclusion: a description-keyed open diff cannot distinguish a board change from noise.**
All such claims made earlier in this campaign are suspect for that reason, including the
"closed 4 nets" attribution in FR3NETS. The count-based gate (`opens decreasing`) is sound;
the identity-based claims are not.

## The reliable comparator

Key on **the set of net names in each record**, which is stable:

```
baseline, 4 runs:  {(): 3, ('/EN',): 1, ('/F33_VSENSE',): 1, ('/SPI2_SCK',): 1,
                    ('/VSCAP',): 2, ('/W2_SOLAR_N',): 1, ('/W3_SOLAR_N',): 2}
via board, 4 runs: identical
```

`docs/analysis/open_diff_relable.py` prints this view. Use it, and compare multisets across
several runs of each board rather than single runs.

Note `(): 3` — three records carry **no bracketed net name at all**. Those are the GND
zone-to-zone records, which name `Zone 'GND_FCu' [GND]` in a form the regex does not capture as
a net path. They are stable in count but invisible to a net-key comparison; treat them
separately (see FINDING-10-pairs-not-11.md: they are zone bookkeeping, not defects).

## The VSCAP via closed nothing

An isolated via was placed 0.900 mm from `C_CAP1` pad 1 after a measured search that required
BOTH copper clearance (0.271 mm guard band) AND hole-to-hole (0.250 mm). It passed every check,
produced no new violations (16 → 16), and **closed nothing**: the open signature is identical to
baseline in 4 runs of each board.

A first attempt at r=0.750 mm failed differently and instructively: it passed every *copper*
check and produced TWO `hole_to_hole` violations, because drill-to-drill was
`0.750 - 0.500 - 0.150 = 0.100 mm` against a 0.250 mm rule. A via has two keep-outs, copper and
drill. Checking one and reporting "no foreign copper within the guard band" was theatre.

The antipad-retreat hypothesis for why the second via did not connect was **tested and
disproved**: `HitTestFilledArea` at the via site reads `True` before and after the refill, and
8 of 24 land-perimeter samples sit on poured copper. The fill does not retreat.

So the `VSCAP_BCu` zone genuinely does not reach `C_CAP1` pad 1, and the fix is not a bare via.
It needs either a 0.200 mm track from the pad into the pour, or the pour extended to the pad —
both real routing work at S1, neither of which I completed.

## Board state

Unchanged: `322ade1e`, 11 records / 10 distinct pairs, silk 0, 0 electrical errors. Nothing from
these experiments was applied to `latest.kicad_pcb`.
