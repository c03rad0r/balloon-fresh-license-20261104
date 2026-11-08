# opens 18 -> 17: the /W3_SOLAR_N track-to-track open is closed

**2026-11-07, board `dcac7ead`, 17 opens, silk 0, 0 electrical errors.**

## What was wrong with my earlier claim

`/W3_SOLAR_N` had been on my "needs drill-in-pad, unroutable" list. Re-measuring on the current
board found a 46.04 mm path, and the DRC records showed the actual open was **track-to-track**,
not pad-to-pad.

**Decisive evidence that a board-side track is the correct repair, not an assembly one:**
`/W1_SOLAR_N` joins `J_W1.4` to `J_W2.1` across two wing connectors with **70.24 mm of board
track** and is **not** an open. So this board carries inter-wing solar links on copper. The same
is required for `/W3_SOLAR_N`.

## Two stages, both needed

**Stage 1 — W3BRIDGE.** Bridged the real 41 mm gap between the two substantial fragments
(`frag0` 10 segs / 20.40 mm, `frag1` 5 segs / 4.75 mm): **41.54 mm, 306 segments, 1 via, 2.6 s**.
First run reported 16 `copper_edge_clearance` errors — the known missing-`.kicad_dru` sidecar
artefact, not geometry. With sidecars copied: **0 errors**.

But opens stayed at 18. The reason is measured, not guessed: the bridge **terminated at
(38.550, 6.950)** while the fragment it was joining ends at **(38.350, 6.750)** — exactly
**0.2828 mm** apart (sqrt(0.2^2 + 0.2^2)). The router stopped one grid step short of its target
and DRC correctly reported the leftover gap.

**Stage 2 — W3STUB.** Added **one** 0.200 mm F.Cu track across that 0.2828 mm gap. Guards, because
a bare "add a track" has burned this campaign before:

- refuses if the endpoints are more than 1 mm apart (then it is not a stub gap)
- refuses if either endpoint is not `/W3_SOLAR_N` copper (verified by `Collide`, both were)
- refuses if the connector would violate S1 clearance against foreign copper
  (measured: no collision)

Result: **errors 0, unconnected 18 -> 17.**

## Adoption gate

```
violation type               before    after delta
lib_footprint_issues              4        4       +0
lib_footprint_mismatch           11       11       +0
unconnected_items                18       17       -1
failing total: 15 -> 15   regressions: 0
VERDICT: PASS
```

The gate refused this batch **once, correctly**, on `lib_footprint_issues 4 -> 8`: the new batch
directory had no `fp-lib-table`, so library registration dropped. Same defect class as the
SILKTEXT refusal. Fixed by copying the table into the batch dir. The per-type gate earned its
keep again.

## What remains on /W3_SOLAR_N

Two records, both the two-face wing pads:

```
Pad 1 [/W3_SOLAR_N] of J_W4 on B.Cu   <->  Pad 1 ... on F.Cu    (38.70, 3.00)
Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu   <->  Track on B.Cu len 3.3004  (69.00, 37.30)
```

The first is the assembly land (WING_TAB_4P / ADR-120 R1). The second is a pad-to-track gap
across layers and is a **real remaining connection**, not closed by this batch.

## Gate suite on the new board

```
check_drc.py                  FAIL   (15 library-load items, 0 electrical)
check_schematic_parity.py     PASS
check_socket_edge_tracks.py   PASS
check_hv_lanes.py             PASS   (report-only)
check_silk.py                 PASS   LEGIBLE, 0 violations
```

## Honest accounting

Three tool defects surfaced getting here, and all three were mine: the mm/nm units error and the
wrong-net-nesting error in `current_routability.py` (each produced confident wrong verdicts
silently), and the missing `fp-lib-table` in the batch dir. The routability probe's `ROUTABLE_NOW`
verdict was right in kind — a path existed — but its stated target was wrong (pad-to-pad when the
real gap was track-to-track).
