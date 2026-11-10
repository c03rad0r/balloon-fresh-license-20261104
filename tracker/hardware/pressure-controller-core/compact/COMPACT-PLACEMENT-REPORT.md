# 65 × 50 mm compact placement study — DESIGN CANDIDATE, UNROUTED

Operator request: a concrete, measured compact-placement feasibility answer for the pressure
controller core — *partsdenser / bothsides / no waste* — using the real schematic, not a
theoretical report. This directory is the whole study. **The candidate is not routed and is not
approved.** No pump, motor, valve actuation, order, flash or fabrication claim is made anywhere here.

| Input | Value |
|---|---|
| Base commit | `08fdfc4a` (PR #542 `pr-pressure-core-placement`, `felixfelix-bot/balloon-fresh`) |
| Schematic | `../core.kicad_sch` — **actual 26-part / 125-endpoint** source, unchanged |
| Netlist | fresh native `kicad-cli sch export netlist --format kicadxml` → `core.xml` |
| ERC | `kicad-cli sch erc --exit-code-violations` → **0 violations** (`erc.json`) |
| Source board (read only) | `../placement/core-placement.kicad_pcb`, sha256 `3d422fa0…8fbc8f` |
| Candidate board | `compact.kicad_pcb`, sha256 `2cc927b1…7f47e7` (byte-identical on rebuild) |
| Outline | 65 × 50 mm (baseline 80 × 60 mm), 2 copper layers, all 26 parts on **top only** |

## What was done, mechanically

`study.py` runs six stages, each in its **own process** (pcbnew invalidates SWIG handles after
any collection mutation; a chained script was measured to segfault):

1. `copy` — **byte-copy** the source board into this directory and record its hash. The source
   checkpoint in `../placement/` is never opened for writing, never moved, never re-saved.
2. `strip` — on the copy only: remove the **2 inherited candidate copper zones** and the
   **5 inherited tracks** (partial routing from the previous milestone). Recorded in
   `stripped.json` (`{tracks_and_vias: 5, copper_zones: 2} → {0, 0}`). No inherited copper is
   carried into the candidate and no preserved routing is claimed.
3. `place` — move footprints, move the single board-level rule area to the new motor
   reservation rectangle, and set the 65 × 50 outline.
4. `annotate` — three `Dwgs.User` text notes. **No added components, no fake parts.**
5. `space` — measure free area and the largest empty rectangle on a 0.25 mm grid.
6. `verify` — ERC, netlist, full audit, native DRC, top/bottom SVG+PNG.

## Measured result

`proof.json` (candidate), `baseline.json` (committed 80 × 60 checkpoint, same kernels),
`space.json`, `dimensions.svg/png`.

| Metric | Baseline 80 × 60 | Candidate 65 × 50 |
|---|---|---|
| Board area | 4800 mm² | **3250 mm²** (−32.29 %) |
| Parts / sides | 26 · 26 top / 0 bottom | **26 · 26 top / 0 bottom** |
| Exported endpoints / nets | 125 / 51 | **125 / 51** |
| Footprint courtyards measured | 26 | **26** |
| Courtyard area, all 26 polygons | 1809.821 mm² | 1809.821 mm² |
| Courtyard area clipped to outline | 785.010 mm² | 785.010 mm² |
| Courtyard occupancy (÷ own board area) | 16.35 % of 4800 | **24.15 % of 3250** |
| Courtyard-to-board-edge minimum | — | **1.27 mm** |
| Largest empty rectangle (parts + antenna keepout blocked) | 1752.0 mm² (54.75 × 32.0) | **953.4 mm² (33.75 × 28.25 at 31.25, 21.75)** |
| Largest empty rectangle **outside** the motor reservation | — | **197.6 mm² (27.25 × 7.25 at 37.75, 0)** |
| Placement extents | — | x 2.75…61.90, y 1.27…46.73 |
| Tracks / vias in candidate | 5 tracks / 2 filled zones (partial route) | **0 / 0** |
| Native DRC | — | 1 record: `lib_footprint_mismatch` on U1 (declared silk→Fab move, inherited) |
| Native DRC unconnected | 77 (`routing/batch0`, unrouted 80×60) | **77** (expected: unrouted board) |
| Per-net opens vs unrouted baseline | 15 nets | **identical, all 15 nets** (`opens_by_net_parity_with_unrouted_baseline: true`) |

Per-net unconnected records on the candidate (DRC spanning-edge accounting, **not** endpoint
connectivity — the split moves with placement geometry and does not mean a pair broke):
`/+3V3` 19, `/GND` 30, `/EN` 4, `/USB5V` 4, `/BOOT` 3, `/I2C_SCL` 3, `/I2C_SDA` 3, `/BUCK_FB` 2,
`/USB_DN_CONN` 2, `/USB_DP_CONN` 2, `/BUCK_SW` 1, `/CC1` 1, `/CC2` 1, `/USB_DN` 1, `/USB_DP` 1.
Total 77 records, **zero records spanning different nets** — the verifier refuses on a cross-net one.
This per-net split is **byte-for-byte the same as the unrouted 80×60 placement** (`routing/batch0`):
moving seven parts and shrinking the outline changed no net's unconnected structure, and the single
non-electrical DRC record is the same inherited U1 `lib_footprint_mismatch` on both boards.

**Denominators are stated where they matter.** Courtyard total `1809.821 mm²` is the sum of all 26
courtyard polygons *including the U1 antenna bar that hangs above the north edge*; occupancy uses
the clipped figure `785.010 mm² ÷ 3250 mm²`. The largest empty rectangle is measured on a 0.25 mm
grid with parts and the antenna keepout blocked; it sits mostly **inside** the empty motor
reservation, which is why the honest headroom figure outside the reservation is only 197.6 mm².

## Invariants, each machine-checked on the saved candidate

Enforced in `study.audit()`, which **re-loads the board from disk** and aborts on any failure:

- **Netlist parity** — every numbered pad's net equals the fresh XML export; the pad map is
  compared as a set, so a missing *or* extra endpoint fails. 125 endpoints, 51 nets.
- **Qualified footprints** — footprint IDs equal the schematic's, and each part's
  `library-sha256.json` hash is re-verified against the actual library file. Zero drift.
- **Footprint geometry parity** — a position-independent pad signature (number, offset, size,
  drill, shape, layer set, net) is compared per reference against the source board: all 26
  identical. Nothing was re-footprinted, re-padded or substituted.
- **Courtyard collisions** — real courtyard polygons via `shapely` (`polygonize` of the courtyard
  lines, `Rect` handled explicitly), all 26 pairs, zero intersection.
- **Pad collisions** — every individual transformed pad bounding box against every other
  footprint's, zero intersections.
- **Antenna manufacturer keepout** — `x 4…52, y −21.025…0`, i.e. the stock U1 courtyard bar
  (48 mm wide, 21 mm deep above the module seam). Only U1 itself may intersect it.
- **USB edge access** — J1 at 270°, shell protruding to x = −1.58 mm (west of the outline),
  courtyard right edge at 7.36 mm < 8 mm, mouth facing west.
- **Buck compact loop** — the U2/L1/C4–C6/R7/R8 cell is translated as a **rigid body**
  (−5 mm in y); its six internal pad-centre metrics are asserted bit-identical to baseline:
  CIN→VIN 2.35, CIN→PGND 3.40, SW→L 2.28, L→COUT 3.33, COUT→VOS 9.66, FB divider→FB 4.91 mm.
- **Sensor port access** — U3 and U4 keep orientation 0° and their footprint-local port keepout
  zones, and **no other courtyard may intersect either port box**
  (U3 x 46.5…49.5 y 7.5…12.5; U4 x 58.5…61.5 y 7.5…12.5).
- **Motor reservation** — exactly one board-level rule area, tracks/vias/pours/footprints
  forbidden, **30 × 24 mm, kept at full size**, now at `x 33…63, y 24…48`; no courtyard
  intersects it (`motor_reservation_fully_empty: true`).
- **Single-sidedness** — every footprint is on `F.Cu`; `side_counts = {top: 26, bottom: 0}`.
- **Unrouted** — zero tracks and vias; zero copper zones (rule areas excluded).

## The motor-reservation question, answered with geometry

The 30 × 24 mm reservation was **not** shrunk. It fits: the candidate keeps it at exactly
720 mm² (22.2 % of the 3250 mm² board) and it is completely empty of parts. There is **no measured
conflict** to report and therefore **no reduced reservation is proposed**. Any future suggestion to
shrink it would be **unqualified pending actual motor parts** — this study does not make one.

The tight geometry is elsewhere, and it is stated as a measurement rather than a plan:

- Only **1.27 mm** separates a courtyard from the nearest board edge (C2's north courtyard edge at
  y = 1.27 to the y = 0 outline). No assembly edge margin is claimed here; the point is that the
  placement is edge-tight and a routing pass has almost no room to spare at that edge.
- Outside the reservation, the single largest contiguous free rectangle is **27.25 × 7.25 mm**
  (197.6 mm²) at the top-right. Everything else free is a sliver between parts.
- The U1 antenna bar forces a 48 mm-wide dead band above y = 0, so the top edge can never carry
  parts even though 65 mm of outline is available.

## What this study does NOT establish

1. **No routing.** 77 native unconnected records remain by construction. Nothing here says the
   65 × 50 placement routes on 2 layers; that requires a route-completion trial on a copy, per
   ADR-140 §78–85, after placement signoff. The prior milestone measured that the in-house router
   is unsafe on this board (unmodelled footprint-local keepouts, filled zones not obstacles), so
   routing is a separate, gated step.
2. **No fabrication or mechanical fit.** 65 × 50 is an electrical-placement envelope; enclosure,
   mounting holes, board thickness/stackup and the motor's real footprint are all absent.
3. **No thermal or analog qualification.** Moving the sensors from x 57/69 to x 48/60 shortens
   sensor→inductor distance by 9.85 mm (49.68 → 39.83) and sensor→S3-shield by 9.0 mm
   (30.80 → 21.80). Distance is not thermal isolation; this needs hardware measurement.
4. **No power-integrity change claimed.** The compact buck cell is rigidly translated, so its
   loop geometry is unchanged, and the unresolved SLVSAM2E §11.1 warning about the 0.20 mm
   SW trace is untouched.
5. **Deterministic output.** Annotation texts mint random UUIDs, which made two builds differ in
   exactly 3 UUID lines. `stage_stabilise` rewrites UUIDs to name-based values after placement;
   two consecutive full builds are now byte-identical (`2cc927b1…7f47e7`), and geometry is untouched.
6. **The single intentional DRC record stays.** `lib_footprint_mismatch` on U1 is the inherited,
   declared silk→Fab move (the antenna overhangs the edge, so the stock silk rectangle would be
   clipped). It is reported, not suppressed.

## Reproduce

```sh
D=tracker/hardware/pressure-controller-core/compact
/usr/bin/python3 "$D/study.py"            # copy → strip → place → annotate → space → verify
/usr/bin/python3 "$D/baseline.py"         # same kernels on the committed 80x60 checkpoint
/usr/bin/python3 "$D/make_dimensions.py" && rsvg-convert -w 1900 -o "$D/dimensions.png" "$D/dimensions.svg"
/usr/bin/python3 "$D/test_compact.py"     # 4 state controls + 9 negative controls
```

`test_compact.py` (13 tests, all passing) is the regression gate: 4 state controls (clean
placement, 30 × 24 reservation empty, source checkpoint byte-identical to `git show HEAD:`, zero
tracks) plus 9 negative controls. Every negative control poisons a copy and requires **the same
audit** to refuse:

| Control | Required refusal |
|---|---|
| duplicate placement (U4 onto U3) | `pad overlap` / `courtyard overlap` |
| part inside the motor reservation | `motor reservation` |
| part inside the antenna keepout | `antenna keepout` |
| part over a sensor port | `sensor port access` |
| part off the board (U4 at x 64) | `outside board` |
| wrong net (U3 pad 1 → no net) | `net parity` |
| added copper segment | `unrouted` |
| second-side part (R9 flipped) | `single-sided` |
| real short C1.1→C1.2 | native `kicad-cli pcb drc` reports `shorting_items` |
| source checkpoint vs `git show HEAD:` | byte-identical |

The clean control asserts 26 references, 125 endpoints, 51 nets, 26 top / 0 bottom, 0 courtyard
and 0 pad overlaps, a 65.000 × 50.000 mm outline, a 30 × 24 mm empty reservation, and a
byte-identical source checkpoint.

## Decisions and evidence

1. **Copy-then-strip, not edit-in-place.** The previous milestone's board carries 5 tracks and 2
   filled GND zones. Re-placing on top of that copper would silently keep routing that no longer
   matches the new geometry. Stripping is done first, on the copy, and recorded as a count.
2. **Sensor block moved to x 48/60, y 10.** The 80 mm board used x 57/69; 11.9 mm of the right edge
   was empty. Moving the two sensors left by 9 mm is what makes 65 mm possible without touching any
   other rule — the buck cell, USB, S3 and motor reservation stay in their own bands.
3. **Buck cell translated rigidly (−5 mm y).** Chosen over re-placing its parts individually so the
   TI §11 loop metrics are provably unchanged (asserted, not asserted-by-eye). Rejected:
   re-optimising the loop for a smaller footprint — that is a schematic/layout decision this study
   has no mandate for.
4. **Motor reservation kept 30 × 24 and only moved.** It fits, so shrinking it would be an
   unqualified change to a reservation whose real part is unknown.
5. **Two copper layers, all parts on top.** Single-sided assembly was an explicit constraint
   ("partsdenser"); a second side would need its own stencil/paste decision and is out of scope.
7. **Six processes instead of one script.** Measured: holding a zone list across a
   `SaveBoard`/`LoadBoard` pair makes the next pcbnew call fail with `SwigPyObject has no attribute
   'GetTracks'`, and a longer chain segfaulted (exit 139). One mutation class per process is the
   only reliable pattern here.

**Gate status: PLACEMENT CANDIDATE — PENDING OPERATOR SIGNOFF. NOT ROUTED. NOT FAB READY.**
It is an incomplete controller; it is not safety-qualified and must not be ordered.
