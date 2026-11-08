# ADR-144 — Two-face wing lands and GND zone anchors are excluded from the unconnected count

**Status:** ACCEPTED — operator decision 2026-11-08: *"sounds good, lets go with these
recommendations"*, following the measurement and the two figures sent for review.
**Date:** 2026-11-08
**Supersedes:** nothing. Amends AGENTS.md §21's reading of "DRC 0".
**Board under test:** `docs/analysis/bulk-route-20261107/latest.kicad_pcb`, DRC
`drc-live.json` — 16 violations, 11 unconnected records.

## 1. The problem

AGENTS.md §21 asks for "DRC 0". On this board that is unreachable **by construction**, and
not because of bad routing:

- **16 of 16 pads** on the wing sockets (`J_W1`–`J_W4`) are each backed by **two SMD pad
  objects** with the same pad number, identical bounding box, and **disjoint copper layers**
  (one F.Cu, one B.Cu). There is no barrel, no via, no copper path between them.
  ADR-120 R1 and AGENTS §13a already say these complete **in assembly** via the two-face tab.
- **Three GND zone-to-zone records** are the stitcher's accounting inside one pour. 46 of 48
  GND vias sit on filled copper on all three layers, so the pour is stitched.

A gate that counts either of these can never pass, and a gate that can never pass is not a
gate — it is a formality people learn to override.

## 2. Measured facts behind the decision

```
two-face pad numbers derived from the board ... 16   (J_W1..J_W4, pads 1-4)
same bounding box in every case ............... True
any PTH among them ............................ none
```

`/W2_SOLAR_N` is the clearest single case, and it corrects two earlier wrong claims of mine:

```
B.Cu track ends landing INSIDE the J_W3.1 pad ... 10   (incl. the exact centre 69.000,42.700)
F.Cu track ends reaching the front object ....... 0
```

An earlier report said the B.Cu chain "stops 1.7 mm short" and that closing it "means drawing
copper near the socket cavity". Both were wrong. The net is **already routed on B.Cu**; it
cannot close because the front object has no copper. There is no cavity rule in play and
nothing to route.

## 3. Decision

Excluded from the unconnected count, **derived from the board, never listed by hand**:

1. **TWO_FACE** — a pad number backed by 2+ SMD pad objects, identical bbox, disjoint copper
   layers, no PTH. Completes in assembly (ADR-120 R1).
2. **GND_ANCHOR** — a zone-to-zone record where both items are GND zones.
3. **DUPLICATE** — the same pair reported twice, reversed. Counted once.

Everything else is **REAL** and counts against the release gate.

The classifier is `tracker/hardware/check_unconnected_exclusions.py`. It is deliberately
**conservative**: anything it cannot prove is two-face or a GND anchor is reported REAL. Its
failure mode is "asks a human", never "silently passes". It prints **every** exclusion with
its reason on **every** run — a silent exclusion is indistinguishable from a bug.

## 4. Result on the board

```
REAL         5      <- counts against the gate
TWO_FACE     3
GND_ANCHOR   2
DUPLICATE    1
```

The 5 REAL opens are `/SPI2_SCK`, `/F33_VSENSE`, `/VSCAP` ×2 and `/EN` — the genuine traps.
They are NOT excluded and NOT excused. They remain open work.

## 5. Why this is not a relaxation

A relaxation hides a defect. This names one and refuses to hide it:

- The excluded set is derived from geometry, so a connector change re-derives it
  automatically and a **stale allowlist cannot hide a new defect**.
- A test (`test_check_unconnected_exclusions.py`, 6 tests) asserts that `/EN`, `/SPI2_SCK`,
  `/F33_VSENSE` and `/VSCAP` are **never** classified as excludable. If a real trap ever gets
  swallowed, that test fails.
- The gate FAILS when asked to expect the wrong number — verified: `--expect-real 6` returns
  exit 1 on a board with 5.

## 6. For future sessions

- Count opens with `check_unconnected_exclusions.py`, not with a raw
  `grep unconnected` on the DRC output.
- Reproduce:
  ```
  kicad-cli pcb drc --format json --severity-all --units mm --output drc-live.json BOARD.kicad_pcb
  python3 tracker/hardware/check_unconnected_exclusions.py BOARD.kicad_pcb \
      --drc drc-live.json --expect-real 5
  ```
- Expected on this board: **5 REAL**. A different number means copper changed — investigate
  before updating the expectation. Never update the expectation to make the gate pass.
- The 16-pad pattern is a property of the **connector**, not of this board. Any future board
  using `J_W*` will match it, and needs no new allowlist.
