# v11 — Hub board status

**Status:** 📋 **SPECIFICATION ONLY — NO BOARD FILE EXISTS.**
**Last measured:** 2026-11-11 on `origin/master` `ace09314`
**Previous generation:** **[v10 status](V10-STATUS.md)**

> There is **no `hub_board_v11.kicad_pcb`**. Nothing has been routed, fabricated or ordered for v11.
> This page exists so the v10 and v11 records are never confused: v10 is a real fabricated board
> with known open routing; v11 is a measured change list that has not been built.
>
> Search that proves the point: `find . -name "*v11*.kicad_pcb"` returns only
> `docs/analysis/bulk-route-20261107/v11-dbp2-spec.kicad_pcb`, a single-diode placement experiment,
> **not a board**.

**No render is shown on this page, because there is no board to render.** An image here would have
to be invented, and an invented board image is indistinguishable from a real one.

---

## 1. What v11 is

Straight from [`V11-DESIGN-SPEC.md`](../V11-DESIGN-SPEC.md):

> **Status:** SPECIFICATION. No v11 board exists yet; this document defines what it must change and
> what each change costs in copper. Every number below is measured on
> `docs/analysis/bulk-route-20261107/work.kicad_pcb` (board `e3cb1860`), the v10 assembly source.

And the reason it is a spec rather than an edit:

> v11 is not "v10 with tweaks". It carries four independent schematic changes, three of which add
> parts and all of which add copper. The v10 campaign took a 38-open board through ~20 routing
> batches to reach 6 real opens; **v11 starts with MORE to route than v10 ever had.** Treating it as
> an afternoon's edit would produce a board that looks finished and is not.

---

## 2. The change list, in dependency order

| # | change | parts added | copper added | blocked by |
|---|---|---|---|---|
| 1 | **ADR-146** — `D_BP1..4` move to the top face | 0 | 8 pad connections, all four sited (worst 1.42 mm) | nothing |
| 2 | `/SCAP_ADC` + cut sense + solar dividers via I²C ADC | **2 × ADS1115** | I²C taps + 8 analog nets | resolved (ADR-148) |
| 3 | Real cut driver at `U_CUT1..4` | 4 × (latch + FET + Rg + Rsense) | 4 sub-circuits | schematic |
| 4 | **ADR-145** — GPIO expander for `U_C` | 1 × MCP23017 | I²C tap + 2 traces | schematic |
| 5 | **Full re-route** | — | — | items 1–4 |

### §1 — the four wing bypass diodes move to the top

Measured on v10: all four `D_BP1..4` are **B.Cu-only**, which forces either 2 × $25 double-sided
Standard PCBA setup or hand-soldering four SMA joints. v11 places them on the top face at layout
time.

**This is not a footprint flip.** The pads are B.Cu-only, so each diode needs both connections
re-made on F.Cu. A full-board search (not a window) for positions where both pads land within 6 mm
of same-net F.Cu copper, all four rotations:

| diode | nets | sites found | best site | worst pad-to-copper |
|---|---|---|---|---|
| `D_BP1` | `/W1_SOLAR_P` / `/W1_SOLAR_N` | 387 | (3.0, 39.0) rot 90 | **0.30 mm** |
| `D_BP2` | `/W1_SOLAR_N` / `/W2_SOLAR_N` | 584 | (36.5, 77.0) rot 0 | **0.85 mm** |
| `D_BP3` | `/W2_SOLAR_N` / `/W3_SOLAR_N` | **194** | (67.5, 38.5) rot 270 | **1.42 mm** |
| `D_BP4` | `/W3_SOLAR_N` / `GND` | 6154 | (49.5, 11.5) rot 0 | **0.11 mm** |

---

## 3. Open items on v11

From [`V11-CUT-CHANNELS.md`](../V11-CUT-CHANNELS.md):

> **NOT FAB READY.** v11 is unrouted and D_BP top placement is unresolved.

That line is older than the §1 table above, which now sites all four diodes with a worst case of
1.42 mm. **The placement half of that sentence is resolved; the "unrouted" half is not.** The two
records disagree and this page records the disagreement rather than picking a winner — the board
file, when it exists, is the tiebreaker.

| item | state |
|---|---|
| routing | **not started** — no board file |
| `D_BP` top placement | sited in spec (§1 above), not yet on a board |
| cut-channel ADC protection | resolved in design (ADR-148), not on a board |
| schematic | exists as a change list, not as a `.kicad_sch` |
| fabrication | **nothing ordered** |

---

## 4. What must be true before v11 is called ready

1. A `hub_board_v11.kicad_pcb` exists and is derived from the v10 source, not hand-edited.
2. All five change-list items are on the board, not just in a spec.
3. `kicad-cli pcb drc --severity-all` reports **0 ERROR-severity** violations.
4. Unconnected count is stated as a number and justified — for an unrouted board it must equal the
   ratnest arithmetic `sum(pads-1)` over multi-pad non-GND nets, exactly as the base station does.
5. 3D model coverage is measured and reported, because `kicad-cli pcb render` is silent when a
   model is missing.
6. Renders are attached to this page the same day the board lands.

Until all six are true, **v11 has no status worth sharing beyond "specified, not built."**
