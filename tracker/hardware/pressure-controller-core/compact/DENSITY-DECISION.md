# Density decision — both sides measured, single-sided adopted

Operator request (2026-11-10): *"are we using both sides of the boards? Lets not waste space"*, then,
after the measurement, *"keep the parts on one side, but make sure AGENTS.md puts parts on both sides
if that saves space."*

`AGENTS.md` §1b requires the **smallest outline to be computed both single-sided and two-sided**, and
adopted when the two-sided one earns **≥10 % of board area**. This file records both numbers so the
single-sided choice is an audited decision rather than a default.

## Measured pair

- **Single-sided, adopted:** `compact/compact.kicad_pcb` — **65 × 50 mm = 3250 mm²**, 26 top / 0
  bottom. −32.3 % vs the 80 × 60 mm original. Native DRC: 1 inherited U1 `lib_footprint_mismatch`,
  77 expected unrouted opens, zero clearance/short/edge records.
- **Two-sided, measured and not adopted:** `../twosided/twosided.kicad_pcb` — **52 × 46 mm =
  2392 mm²**, 12 top / 14 bottom. A further −26.4 % vs the single-sided candidate, which is past the
  ≥10 % threshold. Native DRC: the same single inherited U1 record, 77 expected opens.

## Decision

**Single-sided 65 × 50 mm is adopted on the operator's explicit instruction**, against the threshold.
The stated reasons: one stencil/paste setup, one assembly side, no bottom-side CPL mirroring, and a
simpler enclosure. Per §1b this is a permitted, recorded exception — the rule obliges the *measurement*
on every board, not the smaller outline when the operator has weighed assembly cost and declined.

## Why the first analysis said the opposite, and was wrong

The earlier claim was that two sides "would have bought almost nothing" because, once the
single-sided board was packed, its largest empty area **outside the motor reservation** was only
197.6 mm².

That measured the wrong quantity. "Is the single-sided board packed?" and "would a second side buy a
smaller outline?" are different questions, and only the second decides the board. The 197.6 mm² figure
answered the first, and a packed board can still collapse substantially in outline when its parts are
redistributed over two faces.

Two facts confirm the second reading: the two-sided candidate is **858 mm² smaller**, and it packs
14 parts onto the bottom that could not previously share a face with anything.

## What does not change

- The **30 × 24 mm / 720 mm² motor reservation** is kept at full size and empty on both candidates.
  On the 52 × 46 board it is 30 % of the area, so it — not the parts — is the dominant consumer.
  Sizing it needs the real motor/protection circuit; it must not be shrunk to win area (§1b point 4).
- **Neither board is routed.** The 44-open checkpoint belongs to the 80 × 60 layout and does not
  transfer. No fab release, no flash, no actuation, no purchase.

## If the decision is revisited

Change the answer by re-running `twosided/twosided.py` (deterministic; board sha256
`15a93234…46d2`) and comparing against `compact/proof.json`. What would flip the recommendation:
an enclosure limit that makes 46 mm of depth unacceptable anyway, a bottom-side assembly quote that
removes the cost premise, or a motor reservation that shrinks once its circuit is defined — in which
case both candidates shrink and the pair must be re-measured together.
