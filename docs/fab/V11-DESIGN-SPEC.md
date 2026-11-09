# v11 DESIGN SPECIFICATION — measured change list, not a wish list

**Status:** SPECIFICATION. No v11 board exists yet; this document defines what it must change and
what each change costs in copper. Every number below is measured on
`docs/analysis/bulk-route-20261107/work.kicad_pcb` (board `e3cb1860`), the v10 assembly source.

**Why this is a spec and not a board:** v11 is not "v10 with tweaks". It carries four independent
schematic changes, three of which add parts and all of which add copper. The v10 campaign took a
38-open board through ~20 routing batches to reach 6 real opens; v11 starts with MORE to route than
v10 ever had. Treating it as an afternoon's edit would produce a board that looks finished and is not.

---

## The change list, in order of dependency

| # | change | parts added | copper added | blocked by |
|---|---|---|---|---|
| 1 | ADR-146: `D_BP1..4` to the top face | 0 | 8 pad connections (3 sites easy, 1 needs new trunk) | nothing |
| 2 | `/SCAP_ADC` to an ADC-capable pin | 0 | 1 net, ~28.6 mm | pin budget (see §2) |
| 3 | Real cut driver at `U_CUT1..4` | 4 × (latch + FET + Rg + Rsense) | 4 sub-circuits | schematic |
| 4 | ADR-145: GPIO expander for `U_C` | 1 × MCP23017 | I2C tap + 2 traces | schematic |
| 5 | Full re-route | — | — | 1–4 |

---

## §1 — ADR-146: the four wing bypass diodes move to the top

Measured on v10: all four are **B.Cu-only**, which forces either 2 × $25 double-sided Standard
PCBA setup or hand-soldering four SMA joints. v11 places them on the top face at layout time.

**This is not a footprint flip.** The pads are B.Cu-only, so each diode needs both connections
re-made on F.Cu. Searched a 20 × 20 mm window around each v10 site, both rotations, for positions
where both pads land within 2.5 mm of same-net F.Cu copper:

| diode | nets | candidate sites | best site | worst pad-to-copper |
|---|---|---|---|---|
| `D_BP1` | `/W1_SOLAR_P` / `/W1_SOLAR_N` | 20 | (3.0, 39.0) rot 90 | **0.30 mm** |
| `D_BP2` | `/W1_SOLAR_N` / `/W2_SOLAR_N` | 15 | (35.0, 78.0) rot 0 | **1.08 mm** |
| `D_BP3` | `/W2_SOLAR_N` / `/W3_SOLAR_N` | **0** | — | **needs new copper** |
| `D_BP4` | `/W3_SOLAR_N` / `GND` | 55 | (39.0, 6.0) rot 90 | **0.98 mm** |

**`D_BP3` is the one that costs work.** `/W2_SOLAR_N` has 220 F.Cu segments and `/W3_SOLAR_N` has
314, yet no top-side position within 2.5 mm reaches both — they occupy opposite halves of the
board at that corner. v11 must either route a new trunk for it or accept a slightly worse placement.

**What would change this:** a v11 layout that reserves the four corner regions for the diodes
before routing anything else makes all four trivial. That is the correct order and is the single
highest-value instruction for whoever lays out v11.

---

## §2 — `/SCAP_ADC` has no MCU end

Measured: the net contains **exactly two pads** — `R_DIV1.2` and `R_DIV2.1`. It is a 2:1 divider
from `/VSCAP` to GND whose midpoint goes nowhere. Firmware cannot read the storage rail.

There is also **no divider at all on the raw solar inputs** (`/W1_SOLAR_P` touches only `D1`,
`D_BP1` and `J_W1`), so solar yield is unmeasurable by any means.

**Free ADC-capable pins on v10: exactly one.**
Of the 41 signal pads, 19 ADC-capable pads are already consumed by SPI1, SPI2, the radio control
lines, USB and the GNSS UART. The remaining free pads are:

| pad | GPIO | ADC | note |
|---|---|---|---|
| 15 | GPIO3 | **ADC1_CH2** | strapping pin (JTAG source select) — usable |
| 16 | GPIO46 | none | input only |
| 26 | GPIO45 | none | strapping |
| 28/29/30 | GPIO35/36/37 | none | occupied by octal PSRAM on this N8R8 module |
| 35 | GPIO42 | none | — |

Distance from the divider midpoint to `U1.15` is **28.6 mm** on a board with two signal layers, both
poured. v10 could not close a 43.7 mm run or a 1.35 mm neck under those conditions; 28.6 mm is the
same class of problem.

**v11 must do one of:**
- give `/SCAP_ADC` its own short path to an ADC pin at layout time (preferred), or
- adopt ADR-145's expander and use one of its analog-capable inputs, or
- accept no rail telemetry and probe on the bench.

**Recommendation: add dividers for the three solar inputs too**, not just `/VSCAP`. A board whose
purpose is validating the power path should be able to report it.

---

## §3 — the cut driver has parts, not placeholders

v10's `U_CUT1..4` are placeholder footprints. Their value string is literally
`latched cut driver + cut-sense (part TODO(unverified))`, and pads 4/5/6 have **no net at all**.

The parts are already selected and measured in `docs/fab/CUT-DRIVE-FET-SELECTION.md` and
`docs/fab/CUT-DRIVER-SELECTION.md`:

| role | part | LCSC | pkg | tier | unit |
|---|---|---|---|---|---|
| nichrome switch | `AO3400A` | `C20917` | SOT-23 | **Basic** | $0.0891 |
| latch (hold after MCU death) | `SN74LVC1G373DBVR` | `C128413` | SOT-23-6 | — | $0.2779 |

**`AO3400A` was chosen deliberately against a cheaper part.** `2N7002` at $0.0175 fails on both load
axes: `I_max` 115 mA against a 0.5–1.0 A requirement, and `RDS(on)` ~8–10 Ω at a 3.3 V gate, which
at 1 A is an 8–10 V drop from a 5.4 V rail — physically impossible. **Price ranks candidates that
pass the requirement; it does not select the winner.**

The `SN74LVC1G373` was chosen over the LTC2954/LTC2955 because those are pushbutton controllers
with ~6 µA permanent quiescent draw, and 4 × 6 µA sits on `VSCAP` — the one rail whose entire job is
to still have charge when the converter is dead.

Per wing, v11 needs: latch, FET, gate resistor, and a sense element. **Four sub-circuits.**

**Open question that must be settled before layout:** the gate resistor and sense resistor values
are not yet specified anywhere in the repo. They need a short calculation from the nichrome's
resistance and the cut current target.

---

## §4 — ADR-145: `U_C` becomes addressable

`U_C` needs 4 control lines and has 2 free pins. ADR-145's three measures (shared RESET/BUSY,
`CS` decoder, I2C expander) are all deferred to v11 and none is applied. The expander
(`MCP23017-E/SS`, `C506653`) is the one that costs **zero** new MCU pins because `/I2C_SCL` (16
tracks) and `/I2C_SDA` (26 tracks) are already routed.

ADR-145's own conclusion is that the binding constraint is **escape geometry, not pin budget** —
`U_C`'s four control pads span 19.81 mm on opposite faces. v11 must place the expander adjacent to
`U_C` at schematic time, not retrofit it.

---

## What v11 must NOT inherit from v10

Three defects that were accepted as v10 risks and should not carry forward:

1. **`/F33_VSENSE` is a 43.7 mm dead run.** `U1.21` is isolated from a complete 51-item divider
   chain. The rail's only load is the DNP F33 PA, so it reads zero harmlessly — but it is still
   an unwired net that took a whole campaign to leave open.
2. **`/EN` and `/IO0` have no copper at all.** Both are flash-time only and the ROM bootloader
   needs neither, but they were sealed by the ESP32-S3-WROOM-1U's 1.50 mm pads on 1.27 mm pitch.
   v11 should escape them at layout time or drop them deliberately.
3. **`U_CUT1..4` as placeholders.** See §3.

---

## Sequence for whoever builds v11

1. **Schematic first.** Settle the gate/sense resistor values (§3), add the solar dividers (§2),
   place the expander next to `U_C` (§4). No layout until ERC is clean.
2. **Reserve the corners.** Place `D_BP1..4` on the top face before anything else (§1). This makes
   all four trivial; doing it after routing makes one of them hard.
3. **Route the new nets first**, while the board is empty: `/SCAP_ADC`, the four cut-driver
   sub-circuits, the expander fan-out.
4. **Then** re-route the inherited nets, in batches, with the two checks that worked on v10:
   previously-connected pairs not broken, opens decreasing.

---

## Reproduce

```bash
/usr/bin/python3 - <<'PY'
import pcbnew
b = pcbnew.LoadBoard('docs/analysis/bulk-route-20261107/work.kicad_pcb')
for r in ('D_BP1','D_BP2','D_BP3','D_BP4'):
    f = b.FindFootprintByReference(r)
    print(r, 'top' if not f.IsFlipped() else 'bottom')
print('SCAP_ADC pads:',
      [f'{pcbnew.Cast_to_FOOTPRINT(p.GetParent()).GetReference()}.{p.GetNumber()}'
       for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == '/SCAP_ADC'])
u1 = b.FindFootprintByReference('U1')
print('free U1 pads:', [p.GetNumber() for p in u1.Pads() if p.GetNumber() and not p.GetNetname()])
PY
```

`pcbnew` lives in the distro python (`/usr/bin/python3`), not the project venv.
