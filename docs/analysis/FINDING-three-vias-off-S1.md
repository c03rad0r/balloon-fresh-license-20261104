# Three vias were non-compliant AND off-S1 — fixed before ordering

**2026-11-08, board `322ade1e` → `31efa2da`.** Found while checking the fab package against
JLCPCB's drill rules, which was the last pre-order check.

## The finding

The board carried **two** via drill sizes:

```
land 0.600 / drill 0.300 : 158 vias  annulus 0.150 mm
land 0.600 / drill 0.360 :   3 vias  annulus 0.120 mm
```

The three 0.360 mm vias are the ones the **FR3NETS batch** added. They have three problems, each
independently sufficient to fix them:

1. **They violate the project's own frozen rule.** `latest.kicad_dru` records S1 as
   *"min via diameter 0.45 → we freeze at 0.60"* and *"min via hole 0.20 → we freeze at 0.30"*,
   and enforces it:
   ```
   (rule "S1 frozen JLCPCB via diameter" (constraint via_diameter (min 0.60mm)))
   (rule "S1 frozen JLCPCB via hole" (condition "A.Type == 'Via'") ...)
   ```
   0.360 is not S1. It came in with freerouting's geometry and was never normalised when adopted.

2. **They are below JLCPCB's minimum via annular ring.** JLCPCB publishes **0.13 mm** minimum
   annular ring for vias. At 0.600 land / 0.360 drill the annulus is **0.120 mm — non-compliant
   as built.**

3. **0.360 is not a stocked drill.** JLCPCB's own via-design note: *"drill bit specifications
   increase or decrease by a minimum of 0.05 mm"*. So 0.360 becomes **0.35** (annulus 0.125) or
   **0.40** (annulus **0.100**, worse than today). Either way the board as submitted does not
   produce what the file specifies, and rounding up puts the annulus at exactly the limit with
   zero margin for drill tolerance.

## The fix

Drill reduction on the same land, same position, same net: **0.360 → 0.300**, giving
0.600 / 0.300 and an annulus of **0.150 mm**, identical to the other 158 vias.

This is a rule-conformance fix, not a design change: it restores the frozen S1 numbers the board is
supposed to carry. It cannot make clearance worse (the land is unchanged), it increases the
annulus, and it increases the hole-to-hole margins.

## Verified

```
vias after      : 161, ALL at 0.600 / 0.300, annulus 0.150
drill tools     : 4 — 0.200 / 0.300 / 1.000 / 2.500  (no non-standard sizes left)
drill hits      : 12 + 161 + 15 + 8 = 196   (unchanged; 0.300 went 158 → 161)
opens           : 11 records / 10 pairs   (unchanged)
violations      : 16, same type mix       (unchanged)
REAL opens      : 5                        (unchanged, exclusion gate PASS)
```

## Why this mattered for the order

A fab house normalising 0.360 to 0.400 would have produced boards with a 0.100 mm annular ring on
three vias — at or below the published minimum, with the drill tolerance unbudgeted. That is the
kind of defect that passes visual inspection and fails in the field. It is now impossible: there is
one via geometry on the whole board, it is S1, and every drill it needs is a stocked size.

## Reproduce

    /usr/bin/python3 -B docs/analysis/drill_rule_check.py
