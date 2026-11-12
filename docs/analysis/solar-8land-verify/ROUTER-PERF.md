# The scoped router ran 50× faster and closed nothing — four bugs deep

**Result: 42 unconnected, unchanged. Zero pairs closed.** That is the honest outcome, and the value of
this work is in *why*, because every intermediate result before the fixes was wrong in a way that
looked like success.

## The hang was never memory

Four runs died `rc=137`/`rc=143` and I concluded a 4 GB memory ceiling. There was none — 4.7 GB was
free throughout. Four independent defects were hiding each other:

| # | Defect | Measured cost | Masked by |
|---|--------|---------------|-----------|
| 1 | `blocked()` scanned all 1105 segments, all vias, all pads | **1.364 ms/call** → ~2.4M calls → **~54 min/pair** | #2, #3 |
| 2 | `blocked()` **ignored layer** — F.Cu copper blocked B.Cu routing | 228 of 4000 probes wrong, **all** other-layer-only | #1 |
| 3 | `via_ok()` unindexed — `seg_pt` called **8.7M times** | **14.7 s of a 21.5 s search** | #1 |
| 4 | **Ring seeding made `came[]` cyclic** — `while cur in came` spun forever | infinite loop, A* itself finished in 21 s | — |

Defect 4 is the one that actually hung the process. `faulthandler` put the thread on the path-tracer
line while a standalone `astar()` completed in 21 s. **I had been killing working searches.**

Defect 2 is a correctness bug, not a performance one: `F.Cu=0, B.Cu=2`, and the router treated copper
on the far side of a 4-layer board as an obstacle. Legal B.Cu escapes were refused.

Fixed: uniform 2 mm bucket grid (`blocked_fast`, `via_ok` indexed, `in_any_pad` indexed), seeds become
chain roots, hop cap on the trace.

**Verified agreement:** `blocked` vs `blocked_fast` **0 mismatches / 6000 probes**; `via_ok` vs
reference **0 / 3000**; `in_any_pad` boolean **0 / 4000** (one apparent mismatch was two overlapping
pads reporting different nets — both correctly "in a pad").

## Then it laid a short

First route that completed (C10.1→U1.2, 42→41) produced **3 `shorting_items`** from a **7.9257 mm
`+3V3` leg** cutting straight across `/SPI2_MOSI`.

Cause: the A* validates **cells**. It never validated the segment *between* two path points, and
endpoint re-attachment joined a seed cell to a pad 7.9 mm away.

Fixed with `sweep_ok()`, sampling every leg at 0.05 mm — well under the 0.20 mm clearance rule, so it
cannot step over a violation. The path is now validated **before** copper is written, not after.

## The gate let a defect through, twice

| Run | Route | DRC | Old gate | Correct verdict |
|-----|-------|-----|----------|-----------------|
| C10.1→U1.2 | 42→41 | 3 shorts | REFUSED (hard class) | refuse ✓ |
| U1.19→U3.15 | **42→42** | `via_dangling` 2→**3** | **"KEPT"** | **refuse** ✗ |

`set(after) - set(before)` cannot see a class that **already existed** getting worse. And "unconnected
not worse" is the wrong bar: that route laid copper and a via, closed **nothing**, and added a
dangling via — yet passed.

Corrected gate:
- compare **counts per class** — any class growing is a refusal
- require `uafter < ubefore` — a route must actually connect something

Replayed on the same input: **`REFUSING: violation counts grew {'via_dangling': (2, 3)}`**, exit 3.

## Why 11 pairs closed zero

Every one of the 11 failed `swept leg not clear`, i.e. there is copper within 0.20 mm of the straight
line from pad to pad, and the search could not escape within its window. These pads are boxed by
neighbouring copper, not by a rule. `pair_escape_map.py` is the tool that distinguishes "boxed" from
"search failed" — and after four backend bugs, its verdict on these 11 is not yet trustworthy either.

## Tests

`tests/test_route_gate.py` (5) and `tests/test_scoped_router.py` (6) — **11 passed**. Each pins a
measured bug, including an AST-level assertion that `1 - layer` arithmetic cannot reappear, and one
that reads the gate's own source to require per-class counting.

## FreeRouting is closed out

2.2.4 dies with `StackOverflowError` in `PolylineTrace.combine` → `Polyline.offset_shapes`. Survived
both collinear merging (1105→984 segments, DRC identical) and `-Xss512m`. Board-data-independent, so
not tunable from here.

## Not done

- 42 unconnected stands. 8 of those are two-face wing tabs joined in assembly (ADR-046 l.280), not
  defects — so the real electrical count is lower.
- 7 dead ends (`/GNSS_PPS`×2, `/USB_DN`×2, `/E28_BUSY`×2, `/SPI1_SCK`) are invisible to DRC.
- 19 library warnings + 3 silk are untouched and unrelated to routing.

**No candidate here may be called frozen-rule-approved.** No purchases, no uploads, no rule change.
