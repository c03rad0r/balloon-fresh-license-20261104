# Bulk routing — hub v10, branch `pr/bulk-route-20261107`

**Not orderable. No master merge.** Cumulative on this branch: **38 → 28 native opens.**

Input: O35 repair candidate `fe11ee72c1206fb0715a9cee701961b8a1de37c0c7aaef663172bcf7bf9264c9`
at `pr/o35-ground-repair-20261106` `824df0ba`. All work in the isolated worktree
`~/worktrees/pr-bulk-route-20261107`, on copies. C10 neighbourhood never touched.

## Per-batch numbers

Rows are the actual chain: each batch starts from the previous accepted board. `before` is the
input board's own DRC count. Two rows carry a correction — `U3IRQ` and `SPI1SCK_UC` were
proved against a stale batch-A baseline, so their `proof.json` labels read `35 → 33` and
`35 → 32` when their true inputs were 34 and 33. The deltas and the final count are unaffected;
the cumulative 28 is confirmed by direct DRC on `latest.kicad_pcb`, not by those files.

| batch | pair | opens | violations | via-in-pad Δ | broken |
|---|---|---|---|---|---|
| A | `/HUB_PV_P` `U_HUB_CVT.1→D_HUB1.1` · 21 seg / 2 via / 5.6 mm | | | | |
| A | `/F33_VSENSE` `R_MON2.1→R_MON1.2` · 7 seg / 2 via / 13.1 mm | | | | |
| A | `/HUB_PV_MID1` `D_HUB1.2→D_HUB2.1` · 19 seg / 2 via / 14.0 mm | **38 → 35** | 24 → 24 | **+4** | 0 |
| D | `/F33_IRQ` `U2.18→U1.17` · 30 seg / 6 via / 61.6 mm | **35 → 34** | 24 → 24 | **+0** | 0 |
| U3IRQ | `/U3_IRQ` `U3.15→U1.19` · 119 seg / 5 via / 52.0 mm | **34 → 33** | 24 → 24 | **+0** | 0 |
| SPI1SCK | `/SPI1_SCK` `U3.5→U_C.5` · 16 seg / 2 via / 42.8 mm | **33 → 32** | 24 → 24 | **+0** | 0 |
| HUBPVP2 | `/HUB_PV_P` `D_HUB1.1→J_HUB_PV.1` · 28 seg / 2 via / 41.6 mm | **32 → 31** | 24 → 24 | **+0** | 0 |
| HUBPVN2 | `/HUB_PV_N` `D_HUB2.2→J_HUB_PV.4` · 22 seg / 2 via / 52.7 mm | **31 → 30** | 24 → 24 | **+0** | 0 |
| HUBPVMID3 | `/HUB_PV_MID1` `D_HUB2.1→J_HUB_PV.2` · 50 seg / 4 via / 43.8 mm | **30 → 29** | 24 → 24 | **+0** | 0 |
| P3V3 | `+3V3` `R_F1.1→J_PROG.2` · 9 seg / 2 via / 17.7 mm | **29 → 28** | 24 → 24 | **+0** | 0 |

Batch A predates the via-in-pad gate; its +4 is measured, not estimated — baseline carries
**16** same-net via-in-pads, batch A carries **20**. Every batch after the gate was added shows
**+0** and **0 foreign-net**. `/U3_IRQ` closed **two** records: the DRC pairs `U3_IRQ` items
against two different neighbours, so closing the net cleared both.

Each post-gate batch is verified three ways, all read back from the boards: native
`kicad-cli pcb drc`; graph proof over **ALL NETS** (0 previously-connected pairs broken, named
pair `False → True`); and `verify_via_in_pad.py` for the constraint DRC cannot see.

Board hashes: batch A `824b8a2a54df03a8b72b8472ce26b5ca9b68deb0d5023c84baa0c560e1d3417b`,
`latest.kicad_pcb` after `/U3_IRQ` `9a9c6c12edb72839…` (full hash in the commit).

## Nets closed

`/HUB_PV_P` ×2, `/HUB_PV_MID1` ×2, `/HUB_PV_N`, `/F33_VSENSE`, `/F33_IRQ`, `/U3_IRQ`,
`/SPI1_SCK`, `+3V3`. **Ten records across nine nets.**

## Attempted and UNROUTED — with the CORRECTED reason

The sections below were written while I was still measuring single pads. Two of their
conclusions were later refuted by `reachability.py` (free-space flood fill) and are marked.

**`/EN` `U1.3 → J_PROG.3`** — a pocket. `U1.3` is F.Cu-only in a 0.82 mm pin field, boxed on all
four sides: north 0.55 mm → `U1.4`, south 0.55 → `U1.2`, east 0.85 → `/SPI2_MISO`,
west 1.15 → `/SPI2_MOSI`. A 0.6/0.3 via needs centre ≥ 0.50 mm clear of foreign copper →
x ≤ 9.80, i.e. **1.25 mm** west of pad centre; best F.Cu corridor reaches **1.15 mm**.
**Shortfall 0.10 mm.** Fails at 0.1 mm and 0.05 mm pitch. `J_PROG.3` side is clear past
3.0 mm, so the block is one-sided. Escapes: move a neighbour, reroute `/SPI2_MOSI` in the same
pass, or a smaller via — each changes placement or a rule, so none was taken unilaterally.

**`/SPI2_SCK` `U1.4 → U2.12`** — same pin field as `/EN`, one pin over. `U1.4` is F.Cu-only and
boxed on **all eight** directions tested: 0° 0.85 → `/SPI2_MISO`; 90° **0.40** → `/SPI2_MOSI`;
180° 0.85 → `/SPI2_MOSI`; 45° 0.75 / 135° 0.50 / 225° 0.75 / 270° 0.55 / 315° 0.75 → `U1.5`,
`U1.3`. Longest corridor **0.85 mm** against **1.25 mm** needed for a 0.6/0.3 via.
**Shortfall 0.40 mm.** `U2.12` is clear past 3.0 mm in five of eight directions, so the block
is entirely on the `U1` side. Same three escapes as `/EN`, same reason none was taken.

**`/U3_IRQ`, `/F33_IRQ`** — closed (batches U3IRQ, D). See the table.

**`/VSCAP` `C_CAP1.1 → R_BAL1.1`** — UNROUTED after 800 s, then re-tried at an enforced 120 s
deadline and returned at 121.17 s. Obstacle **not yet measured**, so no number is claimed here.
Listed as attempted-with-cause.

## SPI1 bus: same-layer pairing wins, then runs out of room

`/SPI1_SCK` islands: `U3.5` and `U_C.5` on **B.Cu**, `U1.22` on F.Cu. The obvious pair
`U3.5 → U1.22` needs a via at both ends into a fine-pitch field and failed at 304.75 s. The
**same-layer** pair `U3.5 → U_C.5` needs **no via** and closed three DRC records
(35 → 32) at 266.88 s. Rule that follows: prefer the pair needing the fewest layer changes.

`/SPI1_MISO` is the same shape and still **fails** on its same-layer pair, and the measurement
says why. Free corridor per pin on B.Cu (0° / 90° / 180° / 270°):

| pad | free distance |
|---|---|
| `U3.5` (`/SPI1_SCK`) | >2, 0.65, >2, 0.65 mm |
| `U3.3` (`/SPI1_MISO`) | >2, 0.65, >2, 0.65 mm |
| `U_C.5` (`/SPI1_SCK`) | >2, 0.65, **1.7**, 0.65 mm |
| `U_C.3` (`/SPI1_MISO`) | **1.1**, 0.65, **1.15**, 0.65 mm |

`U3.5` and `U3.3` are identical, so the difference is entirely at `U_C`. `U_C.5` has 1.7–2 mm
along x; `U_C.3` has 1.1–1.15 mm — because `/SPI1_SCK`'s new path now occupies that corridor.
So `/SPI1_MISO` did not fail on its own geometry: it failed on **congestion created by the
previous accepted route**. That is the expected cost of routing adjacently and it is not a
reason to relax anything — it is a reason to sequence the SPI1 nets together rather than one at
a time, or to route them in the opposite order.

`/SPI1_MOSI` `U3.4 → U_C.4` (both B.Cu, no via needed) also **fails** at 290.86 s, and a joint
pass routing `/SPI1_MOSI` + `/SPI1_MISO` together with a 450 s each **also fails both**
(450.92 s / 456.65 s). So it is not ordering. The joint pass was the right experiment and it
settled the question the other way.

The measurement at the `U_C` end, free corridor per direction:

| pad | 0° (east) | 90° | 180° (west) | 270° |
|---|---|---|---|---|
| `U_C.3` `/SPI1_MISO` | **1.10** → `/SPI1_SCK` | 0.65 → `U_C.4` | **1.15** → `/U3_RESET_N` | 0.65 → `U_C.2` |
| `U_C.4` `/SPI1_MOSI` | **1.10** → `/SPI1_SCK` | **0.45** → `/SPI1_SCK` | **1.15** → `/U3_RESET_N` | 0.65 → `U_C.3` |
| `U_C.5` `/SPI1_SCK` | **>2.0 CLEAR** | 0.65 → `U_C.6` | **1.70** | 0.65 → `U_C.4` |

Blocker on the east side is **my own `/SPI1_SCK` route**; on the west it is `/U3_RESET_N`. A
0.6/0.3 via needs 1.25 mm. `U_C.3` has 1.10 mm east and 1.15 mm west — **0.10–0.15 mm short**.
`U_C.4` is worse: 0.45 mm north, so **0.80 mm short**. `U_C.5` was routable because it had the
only >2 mm corridor, and `/SPI1_SCK` took it.

**This is a self-inflicted order dependency, stated plainly.** `/SPI1_SCK` was accepted first
and consumed the one >2 mm corridor at `U_C`. The two parallel SPI1 nets behind it now sit in a
pocket whose best exit is 1.10–1.15 mm against 1.25 mm required.

**The revert experiment was run, and it refutes the order hypothesis.** From the verified
pre-`/SPI1_SCK` board (`9a9c6c12…`, 33 opens) all three SPI1 nets were solved in ONE pass:
`/SPI1_SCK` routed again identically (16 seg / 2 via / 42.8 mm), `/SPI1_MISO` **UNROUTED**
(402.58 s), `/SPI1_MOSI` **UNROUTED** (407.32 s). So the two are blocked by their own geometry —
`U_C.3`/`U_C.4` have no 1.25 mm corridor in any direction and `/U3_RESET_N` walls the west side
even with `/SPI1_SCK` absent. Sequencing was never the problem; reverting `/SPI1_SCK` would
have cost a verified −3 opens and bought nothing.

~~The real fix for these two is a **smaller via** (0.45/0.25 needs ~1.10 mm, which is exactly
what the east corridor offers) or a placement nudge at `U_C` — both are rule/placement changes,~~
**CORRECTED: a smaller via does NOT fix these.** That was my inference while measuring single
pads. `reachability.py` later found `U_C.3` and `U_C.4` **UNREACHABLE in free space** — no path
exists at 0.1 mm pitch on either layer, via size irrelevant, and they failed identically from the
pre-`/SPI1_SCK` board. Only the **placement nudge at `U_C`** remains a real option; both are
rule/placement changes,
not routing choices, so neither was taken unilaterally.

**`/HUB_PV_N` — LATER CLOSED, and it corrects the lesson below.** The `U_HUB_CVT.3` pocket is
real, but routing from the OTHER island (`D_HUB2.2 → J_HUB_PV.4`) sidesteps it entirely and
closed at 31 → 30. A net is not blocked because its tightest pad is. The measurement that
follows is accurate; the conclusion I drew from it was not.

~~**`/HUB_PV_N` `U_HUB_CVT.3 → J_HUB_PV.4`** — the tightest of the three.~~ `U_HUB_CVT.3` is
F.Cu-only and boxed on **all eight** directions: 0° 0.65 → `U_HUB_CVT.17`; 90° **0.10** and
270° **0.10** → `U_HUB_CVT.4` / `.2`; the four diagonals 0.15; 180° 0.60 → `GND`. Longest
corridor **0.65 mm** against **1.25 mm** needed. **Shortfall 0.60 mm.** `J_HUB_PV.4` (PTH,
1.0 mm drill) is clear past 3.0 mm in six of eight directions, so the block is entirely at the
converter pin.

All three blocks share one shape — an F.Cu-only 0.2 mm pad inside a fine-pitch field with no
room for a 0.6 mm via — so one decision covers all three, not three separate ones.

## Three predicate bugs, one class: search permitted what validation refused

1. **Via centre vs disc.** `via_ok` tested the centre point, so a via 0.05 mm outside a pad
   passed while its 0.6 mm body sat 0.2 mm inside. Shipped on the `/EN` canary; retracted in
   `CANARY-EN.md`. `kicad-cli` is blind to this — KiCad has no via-in-pad rule.
2. **Own-net drills as obstacles.** `holes` carried no net, so every PTH pad was sealed by its
   own barrel. Measured: `J_PROG.3` blocked in all four cardinal directions at 0.05 mm by
   "*hole J_PROG*". Fixed; escapes clear past 3.0 mm at 135°/180°/225°.
3. **Pad-edge boundary** (`contains` vs `intersects`): via accepted by search, refused by
   validator.

Gate after each fix, both directions: legal stub accepted; through `U1.27`, inside the C10
guard, same-net via-in-pad at `U5.6`, across the `J_W2` cavity all rejected; 2-D sweep around
`U1.3` → 92 legal sites, **0** accepted with disc overlap; 1500 sampled free cells accepted.

## Two process defects, both now mechanical

- **A four-pair batch lost three routed nets.** It hit its outer `timeout` during the fourth
  pair and wrote neither board nor report. `route_one.sh` now routes **one pair per process**
  and promotes each accepted board to `latest.kicad_pcb`, so the unit of saving equals the unit
  of work. It also refuses on a bad path rather than saving a partial board (measured: first
  `/U3_IRQ` attempt exited 2, tree untouched).
- **`check_lane_crossing.py:126`** labels every non-`F.Cu` track `"B"`, so inner-layer copper
  reads as back copper. `/GNSS_PPS` (on **In2.Cu**) shows 3 CROSSING + 4 TOUCH while native DRC
  finds **zero** shorts. Identical on the untouched baseline — pre-existing false positive,
  not fixed here.

## Rules held (none relaxed)

Clearance 0.200, track 0.200, via 0.600/0.300, copper-edge 0.500, copper-hole 0.250 — read
from the board's own `.kicad_dru`/`.kicad_pro`, never edited. No **foreign-net** via-in-pad
(same-net via-in-pad is pre-existing on the board and gated to Δ0 per batch). No track across a
`J_W` cavity (ADR-142). C10 frozen: candidate copper inside `x 8.00–11.20, y 41.00–44.20` is
rejected, not merely avoided.

## Remaining: 28 opens — all classified by measurement

**18 are not missing copper**
- 15 **two-face assembly lands**: `W1_SOLAR_N`, `W1_SOLAR_P`, `W2_SOLAR_N` ×4, `W3_SOLAR_N` ×4,
  `CUT_SENSE_W1–W4`. These are SMD lands present on both faces with no barrel; they complete in
  the wing-tab assembly (ADR-120 R1). Routing them would be wrong.
- 3 **GND zone-anchor** records (zone-to-zone pairs), not copper gaps.

**6 are free-space UNREACHABLE** — proven by `tracker/hardware/reachability.py`, which flood-fills
the router's own raster with `via_ok` as the layer gate, so it measures connectivity rather than
one pad's corridor:

| net | pair | verdict |
|---|---|---|
| `/EN` | `U1.3→J_PROG.3` | UNREACHABLE |
| `/SPI2_SCK` | `U1.4→U2.12` | UNREACHABLE |
| `/SPI1_MISO` | `U3.3→U_C.3` | UNREACHABLE |
| `/SPI1_MOSI` | `U3.4→U_C.4` | UNREACHABLE |
| `/VSCAP` | `C_CAP1.1→R_BAL1.1` | UNREACHABLE |
| `/F33_VSENSE` | `U1.21→R_MON1.2` | UNREACHABLE |

**Every pair the precheck called REACHABLE is now routed** — `+3V3`, `/HUB_PV_N`,
`/HUB_PV_MID1`. Nothing routable remains at this placement.

Tightest object measured: `R_BAL1.1`, pad **0.54 × 0.64 mm**, 0.30 mm to `/SCAP_MID` on one
side. A 0.20 mm track needs its centre 0.30 mm clear of foreign copper, so there is no legal exit.

Closing these six needs **placement movement, pin reassignment, or accepted topology change** at
`U1`, `U_C` and `R_BAL1`. All three touch a board under Astra CHANGES_REQUESTED, so none was done.

Source acceptance (ERC/parity), the Astra C10 CHANGES_REQUESTED concerns, strict U_LORA1280
silkscreen failures and stackup/process qualification all remain **open and unaccepted**.
Nothing here is fabrication readiness. No order placed.
