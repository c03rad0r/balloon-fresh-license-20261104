# The `/SPI1_SCK` wall is REAL — I refuted it, then reproduced it, and the refutation was mine

**Status:** the claim in `e382f2c4` / `1ed9cf9d` is **CONFIRMED**. My earlier
`CORRECTION-reach-attribution.md` in the reports tree was **WRONG** and is withdrawn.

## What I got wrong

I "refuted" the claim by flooding the BEFORE board and reporting that `/SPI1_MISO` and
`/SPI1_MOSI` were already disconnected — so, I argued, the batch could not have caused
it.

The refutation was an artifact of **how I seeded the flood**. I seeded both F.Cu and
B.Cu at every terminal. Both pads are **B.Cu SMD pads with no F.Cu copper**, so seeding
F.Cu at their XY silently assumed a **via inside the pad** — drill-in-pad, which the
frozen rules forbid. That illegal seed put the flood on the open F.Cu plane and let it
reach the other pad, so everything looked "reachable" and no regression could be seen.

This is the **same defect** that made open 31 `/W3_SOLAR_N` look connected earlier in
this workstream, and I fixed it there and then reintroduced it here.

## What the corrected tool shows

Seeding **only the layers the pad actually has copper on**
(`batches/SPI1SCK_UC`, 0.200 mm + guard, board-wide flood):

| pair | BEFORE | AFTER | delta |
|---|---|---|---|
| `/SPI1_MOSI` U3.4 ↔ U_C.4 | reachable, 872 459 cells | **unreachable, 259 cells** | **LOST** |
| `/SPI1_MISO` U3.3 ↔ U_C.3 | reachable, 879 727 cells | **unreachable, 286 cells** | **LOST** |
| `+3V3` J_VCC.3 ↔ U_C.1 | unreachable | unreachable | unchanged |
| `+3V3` U3.1 ↔ U_C.1 | reachable | reachable | unchanged |

The AFTER counts are the tell: **259 and 286 cells** is a pad sitting in a tiny pocket.
Both nets are walled in, exactly as reported.

The alleged wall track is present and exactly as described —
`B.Cu (35.250, 13.650) → (35.250, 16.250)`, 2.60 mm, net `/SPI1_SCK`
(`forensic_wall_track.py`), and it is **absent from the BEFORE board**, so it was
introduced by that batch.

## Consequence for the campaign

- `SPI1SCK_UC` was a **net loss**: −3 opens, −2 reachable pairs. It should not be
  adopted, and the other session's decision to gate on reachability is correct.
- My batch-1 result in `rdiv2-local-clearance` was verified with **all five
  reachability checks passing** as a *contiguity* test, but my campaign pipeline never
  ran a before/after reachability gate. It has the same class of blind spot.
- The lesson is not "the reviewer was wrong". It is that **a flood whose seed rule is
  wrong produces confident, wrong answers in both directions** — it can invent a wall
  or hide one.

## Reproduce

```
cd docs/analysis
BATCH_DIR=batches/SPI1SCK_UC /usr/bin/python3 -B independent_reach_check.py
/usr/bin/python3 -B forensic_wall_track.py
```
