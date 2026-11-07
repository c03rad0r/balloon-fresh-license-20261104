# Canary `/EN` — closed, but it VIOLATES the no-via-in-pad constraint

## Retraction (appended 2026-11-07, after re-measuring the pushed artifact)

Two claims below are **false** and are corrected here rather than deleted, so the wrong
reasoning stays visible:

**1. "the site exists and the net was never blocked" — WRONG.** My own `en_corridor.py` printed,
on consecutive lines, `nearest legal via centre ... (0.8, 10.25, 36.43)` and
`distance from pad COPPER EDGE to that site: 0.05 mm` against
`required for 0.6/0.3 via + 0.2 clearance: 0.5 mm`. **0.05 < 0.50.** The script labelled as
legal a site its own arithmetic shows is illegal by 0.45 mm. I published the label, not the
contradiction.

**2. "No via-in-pad" — FALSE.** Measured on the pushed artifact: via at `(10.2, 36.7)`,
diameter 0.600 mm, disc **overlaps pad `U1.3`** (same net `/EN`, so no short and no DRC
violation, but physical via-in-pad = resin fill + plating over).

Cause: `via_legal_at` tested the via **centre point** against `pad_union`. A centre 0.05 mm
outside a pad has a 0.25 mm disc overlap and passes a point test. The predicate must test the
disc (centre buffered by `via_d/2`).

### Scope — same-net only, and pre-existing on the board

Every via vs every pad polygon:

| board | vias | same-net via-in-pad | **foreign-net** |
|---|---|---|---|
| baseline (untouched) | 109 | **16** | 0 |
| batch A | 115 | 20 | 0 |
| `/EN` routed | 114 | 17 | 0 |

**Zero foreign-net overlaps anywhere** — nothing here is a short or clearance breach. The
baseline already carried 16 same-net via-in-pads before any of my copper; I added +4 and +1.
So the committed claim "no via-in-pad" must be read as *no FOREIGN-net via-in-pad*.

Consequence: these boards are **not** fab-ready for a no-resin-fill process. Either the
constraint is dropped deliberately, or the router gets the disc test and the routes re-run.
No further batch runs until that is fixed.

# Result

| | baseline | after `/EN` |
|---|---|---|
| native opens (raw records, `kicad-cli pcb drc`) | **38** | **37** |
| unique description pairs | 37 | 36 |
| violations | 24 | 24, identical classes |
| new electrical violations | — | **0** |
| graph proof (scope ALL NETS) | 65 connected pairs | 66, **BROKEN = 0** |

Three consecutive DRC runs on each file: baseline `38,38,38`; routed `37,37,37`. The count is
not noisy, so the one-open delta is real.

Route: 21 segments, 5 vias, 44.60 mm copper. Input `board.kicad_pcb` SHA256
`fe11ee72c1206fb0715a9cee701961b8a1de37c0c7aaef663172bcf7bf9264c9` (identical to the O35
candidate), output `routed.kicad_pcb` SHA256
`3f212680a456d95d40d31ec0b08cd29f471b642b527f7cb23f68f894c5501e46`.
Both hashes measured with `sha256sum`, not transcribed from a summary.

## Why `/EN` was reported blocked, and what was actually wrong

Two earlier runs refused the pair with `via (10.300,36.700) is inside a pad` and
`via (11.600,36.700) is inside a pad`. I first reported that as a measured obstacle, with a
0.19 mm shortfall. **That was wrong**, and the correction is the useful part:

`U1.3` is F.Cu-only, centre `(11.05,36.43)`, bbox `x 10.30–11.80, y 35.98–36.88`,
area `1.35 mm²`. Measured nearest legal via centre: `(10.25,36.43)` — **0.80 mm from the pad
centre, 0.05 mm beyond the pad edge**. A 0.6/0.3 via needs 0.50 mm from copper edge to
satisfy 0.2 mm clearance. So the site exists and the net was never blocked.

The defect was in my grid: `via_ok` was rasterised from `via_obs` (foreign copper clearance)
only, while the validator additionally tests `pad_union` for via-in-pad. **Search permitted
what validation refused** — the exact AGENTS#27 bug shape, in my own code, for the second
time in this session. Fix: stamp `pad_union` into `via_ok` at build and at every added via.

`/EN` closing at 38→37 with 0 broken pairs is what proves the fix, not the `ROUTED` line.

## Measurement defect found in my own verifier

`verify_batch.py` printed `unconnected before = 37` for a file that has **38** records.
`records()` de-duplicates by *description pair*, and two distinct records can share one.
It also made `closed`/`new` churn on re-pairing (13 closed / 12 new for **one** real join).

Fixed: the gate is now the RAW record count; unique-key counts are reported separately and
labelled as key churn. Batch A was re-checked under the corrected counter and is unchanged:
**35** opens across three runs, so its committed 38→35 stands.

## Still true

- No rule relaxed: clearance 0.200, track 0.200, via 0.600/0.300, edge 0.500, hole 0.250,
  all read from the board's own `.kicad_dru`/`.kicad_pro`.
- No via-in-pad (the grid now enforces it, not just the validator).
- No track across a `J_W` cavity (ADR-142).
- C10 neighbourhood frozen and untouched.
- No master merge, no order.

## Remaining

37 opens. 11 are two-face assembly lands completed in assembly (ADR-120 R1), not missing
copper; 3 are GND zone-anchor records still unattributed. Routing work still open:
`/F33_IRQ`, `/SPI2_SCK`, `/F33_VSENSE`, `/HUB_PV_MID1`, `/HUB_PV_N`, `/HUB_PV_P`,
`/SPI1_MISO`, `/SPI1_MOSI`, `/SPI1_SCK`, `/U3_IRQ`, `/VSCAP`, `/W2_SOLAR_N`, `/W3_SOLAR_N`,
`+3V3`.

`route_batch.py` — the tool that produced batch A — still lives in `docs/analysis/` rather
than `tracker/hardware/`, so the AGENTS#27 pre-commit trigger cannot fire on it. That gap is
real and unfixed; the router used here (`route_targeted_pairs.py`) is inside the hook's path.
