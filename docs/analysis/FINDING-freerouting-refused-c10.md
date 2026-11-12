# Freerouting candidate REFUSED at the adoption gate: it routes through the C10 freeze

**2026-11-08, board `e00b98e7`. Supersedes the "REJECTED" verdict in
`FINDING-freerouting-rejected.md`, whose stated reason was wrong, though its conclusion was right.**

## The corrected story

`FINDING-freerouting-rejected.md` said freerouting "routed signal into the power planes", implying that
shorts the plane. **That reasoning was wrong.** The live board already carries six signal tracks on
inner layers (`+3V3` on In1; `/F33_BUSY` and `/GNSS_PPS` on In2) and DRC flags none of them — a KiCad
zone refills *around* foreign copper, leaving a clearance cutout. Signal on an inner layer is normal.

The real cause of the 40 clearance/hole violations was that **`ImportSpecctraSES` adds tracks without
refilling zones**, so old fill sat on top of new copper. Measured:

```
freerouted raw     10 opens   63 violations  (30 clearance, 10 hole_clearance, 6 track_width)
after zone refill  10 opens   23 violations  (clearance 30 -> 0, hole_clearance 10 -> 0)
```

So refill rescued most of it. Then the 6 remaining `track_width` violations turned out to be **my own
patching gap**: `fr_prepare.py` rewrote `(clearance 50)` to `(clearance 200)` but left
`(width 150)`, so freerouting obediently laid 0.150 mm tracks. Widening those 6 segments to 0.200 mm
and refilling again gave:

```
widened + refilled  10 opens   17 violations   0 hard electrical items
live reference      15 opens   16 violations   0 hard electrical items
```

**10 opens, every S1 rule held, zero clearance / hole / width / short items.** That looked adoptable,
and it would have been the best result of the campaign. Which is exactly why the gate ran.

## The adoption gate refused it on all four checks

```
1 open set          FAIL   closed /CUT_SENSE_W1, /W1_SOLAR_N, /W1_SOLAR_P, /W3_SOLAR_N
                           but newly OPENED /F33_VCC
2 connected pairs   FAIL   one new open = one pair broken
3 C10 frozen        FAIL   +6 copper items inside x 8.00-11.20, y 41.00-44.20
4 plane area        FAIL   In1 5345.51 -> 5339.70 (-5.81), In2 5122.21 -> 5101.18 (-21.03)
```

### Check 3 is the disqualifying one

The C10 area is a **standing freeze**: no copper, placement or geometry changes inside it. Freerouting
had no knowledge of that constraint and routed straight through it:

```
ADDED copper inside the frozen window:
  +3V3         F.Cu  0.660 mm
  +3V3         F.Cu  0.283 mm
  /SPI1_MISO   F.Cu  1.269 mm
  /SPI1_MISO   F.Cu  0.101 mm
  /SPI1_MISO   F.Cu  1.126 mm
  /SPI1_MOSI   F.Cu  0.030 mm
```

Six new copper objects where the instruction is that no copper may change. This is not a
close-call — the freeze is an absolute constraint the campaign has honoured for 60+ commits, and the
candidate violates it in the exact region the user named at the start of the work.

## What this cost and what it bought

Cost: one 14-minute route, three scripts, several DRC passes.

Bought, and worth more than the 5 opens:

1. **A correct explanation of the clearance violations**, replacing an analogy that was wrong.
2. **A measured confirmation that the C10 freeze is load-bearing** — a capable router that ignores it
   will route through it immediately. Any future batch must gate on C10 explicitly, not assume.
3. **10 opens is achievable at full S1**, if the copper that closes them respects the freeze. The
   routes exist; this particular router's routes are unusable.
4. **`fr_prepare.py` has a real bug**: it patches `(clearance ...)` but not `(width ...)`. Fix that
   before any future freerouting run, or every run will produce sub-S1 tracks.

## Where the board actually is

`e00b98e7`, 15 opens, silk 0, zero electrical errors, DRC 16 violations (11 `lib_footprint_mismatch` +
4 `lib_footprint_issues` = KiCad footprint-file version artefact; 1 cosmetic 0.1414 mm
`track_dangling` stub). **Unchanged. Nothing adopted.**

The four trapped pads remain the only real blockers and they still need a decision: a scoped
0.150 mm clearance rule, a nudge to `/SPI2_MISO`, or acceptance for a rev-1 first article.

## Files

- `fr_refill_test.py` — refill after SES import; clearance 30 -> 0
- `fr_widen.py` — widen 0.150 -> 0.200 mm tracks; track_width 6 -> 0
- `fr_adopt_gate.py` — the four-check adoption gate (open set, pairs, C10 freeze, plane area)
- `batches/FREEROUTING_REFILL/`, `batches/FREEROUTING_WIDE/` — refused candidates
- `FINDING-freerouting-rejected.md` — superseded on reasoning, conclusion stands
