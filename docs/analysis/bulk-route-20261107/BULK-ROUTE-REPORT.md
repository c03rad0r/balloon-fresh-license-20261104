# Bulk routing — hub v10, branch `pr/bulk-route-20261107`

**Not orderable. No master merge.** Cumulative on this branch: **38 → 32 native opens.**

Input: O35 repair candidate `fe11ee72c1206fb0715a9cee701961b8a1de37c0c7aaef663172bcf7bf9264c9`
at `pr/o35-ground-repair-20261106` `824df0ba`. All work in the isolated worktree
`~/worktrees/pr-bulk-route-20261107`, on copies. C10 neighbourhood never touched.

## Per-batch numbers

| batch | pair | opens | violations | via-in-pad Δ | broken |
|---|---|---|---|---|---|
| A | `/HUB_PV_P` `U_HUB_CVT.1→D_HUB1.1` · 21 seg / 2 via / 5.6 mm | | | | |
| A | `/F33_VSENSE` `R_MON2.1→R_MON1.2` · 7 seg / 2 via / 13.1 mm | | | | |
| A | `/HUB_PV_MID1` `D_HUB1.2→D_HUB2.1` · 19 seg / 2 via / 14.0 mm | **38 → 35** | 24 → 24 | **+4** | 0 |
| D | `/F33_IRQ` `U2.18→U1.17` · 30 seg / 6 via / 61.6 mm | **35 → 34** | 24 → 24 | **+0** | 0 |
| U3IRQ | `/U3_IRQ` `U3.15→U1.19` · 119 seg / 5 via / 52.0 mm | **35 → 33** | 24 → 24 | **+0** | 0 |
| SPI1SCK | `/SPI1_SCK` `U3.5→U_C.5` · 16 seg / 2 via / 42.8 mm | **35 → 32** | 24 → 24 | **+0** | 0 |

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

`/HUB_PV_P`, `/F33_VSENSE`, `/HUB_PV_MID1` (batch A), `/F33_IRQ` (D), `/U3_IRQ` (U3IRQ),
`/SPI1_SCK` (SPI1SCK_UC). Six nets.

## Attempted and UNROUTED — measured obstacle, not a verdict of impossibility

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
pocket whose best exit is 1.10–1.15 mm against 1.25 mm required. Reverting `/SPI1_SCK` and
routing the three together might fit all three; that is a real option and it trades a verified
−3 opens for a maybe. I did not take it unilaterally, because it discards working copper on a
guess about a denser joint solve.

**`/HUB_PV_N` `U_HUB_CVT.3 → J_HUB_PV.4`** — the tightest of the three. `U_HUB_CVT.3` is
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

## Remaining: 32 opens

11 are **two-face assembly lands** completed in assembly (ADR-120 R1) and 3 are **GND
zone-anchor** records — 14 that are not missing copper. Still to attempt: `/HUB_PV_N`,
`/HUB_PV_P`, `/HUB_PV_MID1` (remaining islands), `/SPI1_MISO`, `/SPI1_MOSI`, `/SPI1_SCK`,
`/VSCAP`, `/W2_SOLAR_N`, `/W3_SOLAR_N`, `+3V3`, plus `/EN` and `/SPI2_SCK`.

Source acceptance (ERC/parity), the Astra C10 CHANGES_REQUESTED concerns, strict U_LORA1280
silkscreen failures and stackup/process qualification all remain **open and unaccepted**.
Nothing here is fabrication readiness. No order placed.
