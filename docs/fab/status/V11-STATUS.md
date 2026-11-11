# v11 — hub board status (NOT STARTED)

**Status: specification only. No v11 board file exists, no schematic has been drawn, and nothing has
been quoted or ordered.**

This page exists so the v11 state is shareable and unambiguous. The design content lives in
[`docs/fab/V11-DESIGN-SPEC.md`](../V11-DESIGN-SPEC.md); this page is the status summary.

| | |
|---|---|
| Board | **does not exist** |
| Schematic | not drawn |
| Placement | not done |
| Routing | not started |
| DRC | n/a |
| Render | **none available — there is no board to render** |
| Quoted / ordered | no |
| Blocked by | 2 unresolved inputs (below) |

---

## Why there is no image on this page

Every other board status page on this project shows a render. This one cannot, and putting a "concept"
image here would be worse than nothing — a rendered v11 would look real and be fiction.

v11 is a **schematic change set**, not a re-place of v10. Four independent changes, three adding
parts and all adding copper. Until the schematic is drawn there is no geometry to render.

---

## The five changes v11 must carry

Taken from the specification, in dependency order.

| # | Change | Parts added | Blocked by |
|---|---|---|---|
| 1 | ADR-146 — `D_BP1..4` move to the top face | 0 | nothing — **all four sited**, worst 1.42 mm |
| 2 | `/SCAP_ADC` + cut sense + solar dividers via I²C ADC | **2 × ADS1115** | resolved (ADR-148) |
| 3 | Real cut driver at `U_CUT1..4` | 4 × (latch + FET + Rg + Rsense) | **schematic** |
| 4 | ADR-145 — GPIO expander for `U_C` | 1 × MCP23017 | **schematic** |
| 5 | Full re-route | — | 1–4 |

**Why it is not an afternoon's edit:** the v10 campaign took a 38-open board through roughly 20
routing batches to reach 6 real opens. v11 starts with **more** to route than v10 ever had.

---

## What v11 is fixing — measured on v10

### The four bypass diodes move to the top

On v10 all four are **B.Cu-only**, which forces either double-sided PCBA setup or hand-soldering four
SMA joints. A full-board search (not a 20 mm window) finds viable top-side sites for all four:

| diode | sites found | best site | worst pad-to-copper |
|---|---|---|---|
| `D_BP1` | 387 | (3.0, 39.0) rot 90 | 0.30 mm |
| `D_BP2` | 584 | (36.5, 77.0) rot 0 | 0.85 mm |
| `D_BP3` | **194** | (67.5, 38.5) rot 270 | 1.42 mm |
| `D_BP4` | 6154 | (49.5, 11.5) rot 0 | 0.11 mm |

**A correction worth keeping:** an earlier version of the spec reported `D_BP3` as having **zero**
sites and "needs new copper". That was an artefact of searching only a 20 × 20 mm window around its
v10 position. `/W2_SOLAR_N` occupies y 44–77 and `/W3_SOLAR_N` occupies y 3–34, so nothing near the
old site can reach both. v11 is a re-layout, and a full-board search finds 194 sites.

**Layout instruction:** place the four diodes on the top face **before** routing anything else.

### `/SCAP_ADC` measures nothing

The net contains **exactly two pads** — `R_DIV1.2` and `R_DIV2.1`. It is a 2:1 divider from `/VSCAP`
to GND whose midpoint goes **nowhere**. Firmware cannot read the storage rail. There is also no
divider at all on the raw solar inputs.

v10 had **exactly one** free ADC-capable pad (GPIO3), 28.6 mm from the divider midpoint on a
two-layer poured board. **ADR-148 resolves this** with two `ADS1115IDGSR` (`C37593`) on the existing
I²C bus: eight analog channels for **zero** new MCU pins, and GPIO3 is freed so the strapping-pin
risk disappears.

The cut sense is a **shunt, not a divider** — a divider measures pad voltage, which stays ~5.4 V
whether or not the wire is intact, and therefore cannot detect a cut.

### The cut driver has parts, not placeholders

v10's `U_CUT1..4` value string is literally `latched cut driver + cut-sense (part TODO(unverified))`,
and pads 4/5/6 have **no net at all**.

| role | part | LCSC | package | unit |
|---|---|---|---|---|
| nichrome switch | `AO3400A` | `C20917` | SOT-23 | $0.0891 |
| latch (holds after MCU death) | `SN74LVC1G373DBVR` | `C128413` | SOT-23-6 | $0.2779 |

`AO3400A` was chosen deliberately **against** the cheaper `2N7002` ($0.0175), which fails on both
load axes: `I_max` 115 mA against a 0.5–1.0 A requirement, and `RDS(on)` ~8–10 Ω at a 3.3 V gate,
which at 1 A would drop 8–10 V from a 5.4 V rail. **Price ranks candidates that pass; it does not
select the winner.**

### `U_C` needs an expander

`U_C` needs 4 control lines and has 2 free pins. The binding constraint is **escape geometry, not pin
budget** — `U_C`'s four control pads span 19.81 mm on opposite faces. `MCP23017-E/SS` (`C506653`)
costs zero new MCU pins because `/I2C_SCL` and `/I2C_SDA` are already routed. It must be placed next
to `U_C` **at schematic time**, not retrofitted.

---

## Three v10 defects v11 must not inherit

1. **`/F33_VSENSE` is a 43.7 mm dead run** — `U1.21` isolated from a complete 51-item divider chain.
   It reads zero harmlessly because the rail's only load is the DNP F33 PA, but it is an unwired net.
2. **`/EN` and `/IO0` have no copper at all** — sealed by the ESP32-S3-WROOM-1U's 1.50 mm pads on
   1.27 mm pitch. v11 should escape them at layout time or drop them deliberately.
3. **`U_CUT1..4` as placeholders** — see above.

---

## Blocked — two inputs needed before layout can start

1. **Gate resistor and sense resistor values are not specified anywhere in the repo.** They need a
   calculation from the nichrome's resistance and the target cut current. I cannot pick these
   arbitrarily; the parts would be placed around a resistor I invented.
2. **Nichrome specification** — gauge, length and resistance per metre for the actual tether in use.

Everything else in the change list is either settled or is straightforward schematic work.

---

## Sequence for whoever builds v11

1. **Schematic first.** Settle the gate/sense resistor values, add the solar dividers, place the
   expander next to `U_C`. No layout until ERC is clean.
2. **Reserve the corners.** Place `D_BP1..4` on the top face before anything else.
3. **Route the new nets first**, while the board is empty: `/SCAP_ADC`, the four cut-driver
   sub-circuits, the expander fan-out.
4. **Then** re-route inherited nets in batches, with the two checks that worked on v10:
   previously-connected pairs not broken, and opens decreasing.

---

*Related: [v10 status](V10-STATUS.md) · [v11 design specification](../V11-DESIGN-SPEC.md)*
