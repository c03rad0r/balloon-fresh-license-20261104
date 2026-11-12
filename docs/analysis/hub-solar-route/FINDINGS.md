# Solar-return routing on the hub v10 candidate — 5 of 8 pairs routed, 3 measured blocked

> ## CORRECTION (2026-11-03, added on top — this document is not rewritten)
>
> **Two of the three "BLOCKED" verdicts below are WRONG, and the cause is this
> report's own router, not the board.**
>
> The router applied the 0.50 mm board-edge rule to the **whole** board. The
> `J_W` lands are edge-launched by design (ADR-046/048) and sit on `Edge.Cuts`,
> so that rule walls off the very pads the routes must reach. The correct
> treatment — the one that is both in the repo's DRC allow-list *and* used by
> `docs/analysis/solar-8land-verify/route_solar_bitmap.py` (merged as #438) — is
> to lift the edge rule **only under each endpoint pad's own body** and leave the
> clearance rule in force everywhere.
>
> Corrected verdicts for the three rows marked BLOCKED:
>
> | pair | this doc said | corrected |
> |---|---|---|
> | `/W1_SOLAR_N` `D_BP2.1` ↔ `J_W2.1` | BLOCKED by siblings' copper | **ROUTED** (2 segs, 3.43 mm) |
> | `/W2_SOLAR_N` `D_BP2.2` ↔ `J_W2.4` | BLOCKED | **geometry exists, but see below** |
> | `/W3_SOLAR_N` `J_W4.1` ↔ `D_BP4.1` | BLOCKED | **geometry exists, but see below** |
>
> **"Geometry exists" is not "it should be routed".** Applying those two as real
> copper and grading with native DRC produces `copper_edge_clearance` errors: each
> `J_W` footprint carries four `Edge.Cuts` graphics forming a 6 × 0.5 mm slot cut
> into the board edge, and those two lands sit ~0.05 mm from it. There is no
> landing point on the pad that is also 0.50 mm from the slot, so a track cannot
> serve them under the rule as DRC measures it. The final applied set is therefore
> **5 pairs**, which is what actually ships (see `solar-8land-verify/APPLIED.md`,
> merged as #440) — the count in the title holds, but *two of the three reasons
> were wrong*.
>
> The lesson is recorded rather than removed: **a router result is not evidence
> until a negative control shows the router refusing.** That control is
> `solar-8land-verify/negative_control.py`; this report's router has no such
> control, and its "corridor closed" verdicts were an artefact of an over-strict
> keep-out. Read `§4` below as *"this router found no path"*, never as
> *"no path exists"*.

**Date:** 2026-11-03
**Source board (read-only):** `hub_board_v10_lora1280_7of9.kicad_pcb`,
sha256 `94038dd0c4608f28181017599cb7b623dcb85d81f619ec66947fdec2406c1155`
(the hub-repair milestone-2 candidate; sha unchanged after this work — it was never written)
**Output board:** `output/after/hub_board_v10_lora1280_7of9.kicad_pcb`,
sha256 `84bad0dd8f35647bc51105cc21ec8ec8d40f57282b05383a2cea0920afc33a4d`
(superseded `894274a0…fb162`, produced by the router this CORRECTION describes;
see `REG-RADE.md` for the independent re-grade)
**Native DRC:** KiCad 9.0.9, `kicad-cli pcb drc --severity-all`, refilled copy.

---

## 1. Result

```
violations            38 -> 38      multiset IDENTICAL, zero new identities
  errors              18 -> 18
  warnings            20 -> 20
unconnected items     86 -> 82       (4 items closed)
```

Five of the eight board-fixable diode↔wing-land pairs now carry B.Cu copper.
Three do not — and per the CORRECTION above, the reasons originally given for two
of them were wrong: pair 3 has a corridor but no legal landing, and pair 2
(`D_BP2.1`↔`J_W2.1`) routes outright. Only pair 6 has a genuinely closed
corridor. See `REG-RADE.md` for the measurement that separates them.

| net | pair | copper on the output board |
|---|---|---|
| `/W1_SOLAR_N` | `J_W1.4` ↔ `D_BP1.2` | **ROUTED** — 4 segs, 9.190 mm |
| `/W1_SOLAR_N` | `J_W1.4` ↔ `D_BP2.1` | **ROUTED** — 8 segs, 50.946 mm |
| `/W1_SOLAR_N` | `J_W2.1` ↔ `D_BP2.1` | **ROUTED** — 2 segs, 3.428 mm |
| `/W2_SOLAR_N` | `J_W3.1` ↔ `D_BP3.1` | **ROUTED** — 4 segs, 9.132 mm |
| `/W3_SOLAR_N` | `J_W3.4` ↔ `D_BP3.2` | **ROUTED** — 2 segs, 3.054 mm |
| `/W2_SOLAR_N` | `J_W2.4` ↔ `D_BP2.2` | not routed — geometry exists, landing illegal at the slot |
| `/W3_SOLAR_N` | `J_W4.1` ↔ `D_BP4.1` | not routed — geometry exists, landing illegal at the slot |
| `/W3_SOLAR_N` | `D_BP3.2` ↔ `J_W4.1` | not routed — no B.Cu corridor at these rules |

Plus the 9th record, which is *not* board-fixable at all:
`GND` `D_BP4.2` (B.Cu) ↔ `U2.4` (F.Cu) — no shared copper layer. Left untouched.

**Why the unconnected count moves by 4, not 5:** unconnected items are counted per
*equipotential group dimension*, not per pair. Closing a pair can merge two nets and
therefore re-partition the remaining records of that net (KiCad re-pairs them). The
multiset diff in `output/after/drc-summary.json` shows this explicitly: 14 records
disappear, 11 appear, 3 net. Every disappearing record involves a pad the new copper
touches; every appearing record is a different pairing of the same pads. **No record
that was connected became unconnected** — the netlist is unchanged and the copper is
additive.

## 2. Why the earlier "no shared layer" reading was wrong

`docs/analysis/hub-solar-gaps/solar_layers.py` keys pads by **pad number** in a dict:

```python
def pad(ref, num):
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p
```

Every `J_W*` landing is a **double-sided stacked land**: two separate `SMD` pads in
the footprint, same number, same net, same XY, one on F.Cu and one on B.Cu (measured;
`WING-TO-HUB-SOCKET-SPEC` §2 / ADR-120 R1 as cited by the merged audit #433). The
dict keeps only whichever was iterated last, so the B.Cu face was silently dropped and
every pair looked layer-disjoint.

Measured directly on the board (all four sockets, all four pads):

```
J_W1 pad 1 [/W1_SOLAR_P]  F.Cu+B.Mask+Paste   and   B.Cu+B.Mask+Paste   (2 pads)
J_W1 pad 2 [GND]          ... same shape ...
J_W1 pad 3 [/CUT_SENSE_W1] ... same shape ...
J_W1 pad 4 [/W1_SOLAR_N]  ... same shape ...
```

So **all 12 diode↔J_W pairs share B.Cu** (consistent with the merged #433 finding),
and 8 of 9 records in the earlier list are closable by a plain B.Cu track.

## 3. Method — and the three things that had to be fixed to get a legal route

`route2.py`: clearance-aware 8-connected A* on a 0.20 mm grid, greedy string-pull,
then every retained segment is re-validated against the real obstacle set before a
single track is written. No track is added unless the whole polyline validates.

Hard constraints, enforced in the model and re-checked by native DRC:

* **0.20 mm copper clearance** to foreign copper (pads, tracks, vias).
* **0.50 mm copper-to-board-edge**, modelled as "inside the outline eroded by
  0.50 + half-width", so the outer Edge.Cuts rectangle *and* the four milled wing
  slots (Edge.Cuts graphics owned by the footprints) are both honoured.
* Milled slots are physical cuts: no track may cross one.

Three corrections that each unblocked a real failure, recorded because they are
where a naive attempt produces 100+ new violations (as the 9-straight-track
experiment did):

1. **The board interior is not an obstacle.** Mixing "allowed region" and "forbidden
   region" into one set inverts the search and reports every pair as illegal.
2. **Corner cutting.** Allowing diagonal grid steps through a diagonal pinch made the
   grid path legal-looking but the resulting 0.20 mm segment illegal (measured: 81 of
   81 A* paths failed the segment validator at exactly that corner). Diagonal steps now
   require both orthogonal neighbours free.
3. **Pad anchors.** A 4.0 × 1.2 mm land is not a point. A track may terminate anywhere
   on it, and the centre is often the worst entry (walled by the neighbouring land's
   clearance box). Nine spread anchors per pad, tried nearest-to-target first, is what
   let `/W2_SOLAR_N D_BP2.2 ↔ J_W2.4` route at all — no centre-to-centre path exists.

Plus 1 µm of slack in the *obstacle model only*: neighbouring lands are 0.600 mm apart
and a 0.20 mm track needs exactly 0.600 mm of envelope (0.2 + 0.2 + 0.2), so the
corridor is legal at exactly 0.200 mm and shapely reports that tangency as an
intersection. Native DRC is the authority; it reports the achieved clearance to four
decimals and raises nothing for these tracks.

## 4. The three that do not route — measured, not assumed

`showmap.py <board> <net> x0 y0 x1 y1` prints the free/blocked raster for a net, which
is how each of these was established.

### 4a. `J_W4.1` (`/W3_SOLAR_N`) has a **single free grid cell** on B.Cu

```
J_W4.1 rect x 38.10..39.30  y 1.00..5.00   (4.0 x 1.2 land at the bottom edge)
free grid cells reachable from its centre, B.Cu:   1   (38.8, 3.0)
```

Its own land is bounded by `J_W4.2`/`J_W4.3` clearance boxes, the milled slot, the
0.50 mm edge band and `/CUT_SENSE_W4` copper. A track leaving that single cell in any
direction violates one of them. That is why **both** `/W3_SOLAR_N` records touching
`J_W4.1` are blocked, and it will not be fixed by more search: the escape is
geometrically absent at 0.20 mm width and 0.20 mm clearance.

### 4b. `D_BP2.1` ↔ `J_W2.1` is walled by the copper that closes the other two pairs

This pair routes fine **on the base board** (measured: `OK`). It fails in the final
board because the two `/W1_SOLAR_N` siblings use the only corridor into `J_W1.4`'s
reach. Ordering the three `/W1_SOLAR_N` pairs differently moves the failure between
them — measured in both directions: with the trunk first, 3 pairs fail; with the
land-escapes first, 2 pairs route and this one fails. **The three pairs compete for one
corridor**; two of the three can be closed, not all three.

## 5. What this means for the board

The solar-return nets are **still split** on this candidate, and the 3 remaining
records sit at `J_W4.1` and `J_W2.1`. Nothing here claims otherwise.

What *is* established:

* 5 of 8 board-fixable pairs are closed with **zero new DRC identities** at 0.20 mm
  width and 0.20 mm clearance — so the constraint that killed the 9-straight-track
  experiment (107 added violations) is met by construction, not by waiver.
* The 3 that remain are blocked by **land geometry at the wing sockets**, not by
  router effort. A fix is a layout change (widen the escape at `J_W4` / free the
  `J_W2.1` corridor), i.e. the respin already on the table from ADR-134/136, not
  another routing pass.
* The `GND` `D_BP4.2`↔`U2.4` record is a different class (no shared layer) and is out
  of scope of board copper entirely.

## 6. Reproduce

```sh
cd docs/analysis/hub-solar-route
/usr/bin/python3 route2.py      # writes output/after/*, never touches the source
/usr/bin/python3 drc.py output/before/hub_board_v10_lora1280_7of9.kicad_pcb
/usr/bin/python3 drc.py output/after/hub_board_v10_lora1280_7of9.kicad_pcb
/usr/bin/python3 showmap.py output/after/hub_board_v10_lora1280_7of9.kicad_pcb /W3_SOLAR_N 30 0 48 10
```

`drc.py` refills, runs native DRC, and writes a `.drc-summary.json` whose
`violation_ids` / `unconnected_ids` are the multisets diffed in §1.

Each route's points, segment count and length are in `output/after/routes.json`.

## 7. Method note: which identity to diff

Violation identities are `type | severity | description | sorted(item descriptions)`
— descriptions carry ref/pad/net/layer, so a multiset over them is reproducible and
two identical runs agree. **UUID pairs are not usable for the unconnected multiset**:
measured on this board, two byte-identical DRC runs re-paired 9 of 86 unconnected
records, so a UUID-based identity reports phantom changes on a board that did not
change. Both runs are in `output/before/` if that needs re-checking.
