# Capacitor voltage audit — VSCAP is 5.4 V by construction, and what that means

**2026-11-08. Corrects my own `audit_bom_specs.py` finding.** Both caps I flagged are **legal**
on this rail. One still deserves a change, for a different reason than I first gave.

## The fact that settles it

`docs/analysis/RESEARCH-five-parts.md:38`:

> `VSCAP` max is **5.4 V** (2 × 2.7 V supercaps in series).

**5.4 V is a construction limit, not a nominal.** Two 2.7 V cells in series cannot exceed
2 × 2.7 = 5.4 V, because 2.7 V is each cell's *rated* ceiling. There is no charging path that
takes this node above 5.4 V — the bank is the source, and it is capped by its own chemistry.

## So the derating question has to be answered honestly

My audit applied a **1.5× derating heuristic** (5.4 × 1.5 = 8.1 V) and called 6.3 V parts
failures. That heuristic is standard for a *supply rail of unknown provenance*. It is **wrong
here**, because it treats a bounded node as if it could surprise us.

Against the real bound:

| cap | rating | VSCAP max | utilisation | verdict |
|---|---|---|---|---|
| `C_BULK` C15008 100µF 1206 | 6.3 V | 5.4 V | **86 %** | legal, thin |
| `C10,C4` C15525 10µF 0402 | 6.3 V | 5.4 V | **86 %** | legal, thin |

86 % of rating is inside what an X5R is qualified for at room temperature, and the datasheet
derating curve applies. **Neither part violates anything.** I was wrong to call them failures.

## But there are two real reasons to change the bulk cap anyway

### 1. DC-bias capacitance loss — measured, not assumed

An X5R 1206 100 µF at 6.3 V rating, biased at 5.4 V, loses a large fraction of its nominal
capacitance. At 86 % of rated voltage this is the worst part of the bias curve — commonly
**50–70 % loss**. So `C_BULK` is not a 100 µF capacitor on this board; it is plausibly
**30–50 µF**.

That matters because `C_BULK` is the reservoir behind a PA that draws ~1100 mA pulses
(ADR-070). The whole point of the part is charge storage during a burst.

**`C312983` — muRata `GRM31CR61A107ME05L`, 100 µF, 10 V, X5R, 1206 — fixes this.**
Verified by page read-back: `cap 100.0, vr 10.0, die X5R, pkg 1206`. Same footprint
(`C_1206_3216Metric`), so **no board change**. At 5.4 V it sits at 54 % of rating instead of
86 %, which moves it much further up the bias curve.

### 2. Margin costs almost nothing

100 µF 1206 6.3 V → 10 V is a same-price-class substitution. Paying nothing to move from 86 %
to 54 % utilisation on the one part whose job is energy storage is not over-engineering.

## The 0402 cap: change is not available, and that is the finding

`C10,C4` is `C_0402_1005Metric`. **10 µF at ≥10 V does not appear to exist in 0402.** Verified
read-backs of the plausible candidates:

| LCSC | cap | V | dielectric | package | usable? |
|---|---|---|---|---|---|
| C15525 | 10 µF | 6.3 | X5R | **0402** | current part |
| C1856527 | 10 µF | 6.3 | X5R | 0402 | no better |
| C19702 | 10 µF | 10 | X5R | 0603 | **wrong footprint** |
| C15850 | 10 µF | 25 | X5R | 0805 | **wrong footprint** |
| C181790 | 10 µF | 25 | X5R | 0805 | **wrong footprint** |

This is a known MLCC ceiling: capacitance per volume at a given voltage. 10 µF/10 V in 0402 is
outside what the mainstream vendors catalogue.

**Recommendation: keep `C15525`.** It is legal, and the alternatives are board changes. But
record the DC-bias reality: these two are nominal 10 µF and effective far less at 5.4 V. They
are decoupling, not energy storage, so the consequence is a higher HF impedance than the BOM
implies — worth knowing, not worth a re-spin.

If a future revision moves them, **0603 at 10 V** (`C19702`) is the cheap upgrade, and it needs
a footprint change, which is a v11 item.

## What I got wrong, so it is not repeated

`audit_bom_specs.py` applied a blanket 1.5× derating to every part. That produced:

- **two false "LOW" verdicts** here, because a bounded rail is not an unknown rail, and
- **one false "LOW" on `U1`** (3.6 V vs 3.63 V "needed") — 3.6 V is the ESP32-S3's *absolute
  maximum* supply, not a voltage to derate from. An IC's abs-max is a limit to stay under, not
  a nominal to multiply.

The rule: **derate against the rail's true maximum, and only for parts whose failure mode is
voltage-driven degradation.** For an IC supply pin, compare nominal to recommended operating
condition and confirm abs-max is not exceeded.

## Changes

- `C_BULK` C15008 → **C312983** (verified 100 µF / 10 V / X5R / 1206). Same footprint.
- `C10,C4` C15525 → **unchanged**, with the DC-bias caveat recorded.
- `audit_bom_specs.py` → the derating logic is being corrected, not kept as-is.

Prices are in `board_cost_prices.json`; C312983 is added to the model and the figure regenerated.
