# ADR-145 — v11 GPIO economy: three pin-saving measures, deferred from v10

**Status:** PROPOSED for v11. **Not applied to v10.** Operator directive 2026-11-09: *"put all
three pin saving improvements on the roadmap for the next board version"*.

## Why this exists as a roadmap item and not a v10 change

`U1` (ESP32-S3-WROOM-1U) has **34 of its 41 signal pads consumed**. The four radios each cost
four to six control lines:

| device | control lines | fitted on v10 |
|---|---|---|
| `U_LORA1280` | 6 — `CS_N`, `RESET_N`, `BUSY`, `DIO1`, `DIO2`, `DIO3` | yes |
| `U3` LoRa2021 | 4 — `CS_N`, `RESET_N`, `BUSY`, `IRQ` | yes |
| `U2` F33 PA | 4 | **DNP** (2 W not licence-free in DE) |
| `U_C` LoRa2021 | 4 | **DNP on v10** (this ADR) |

Free and *usable* pads on v10: **`IO3` (pad 15) and `IO42` (pad 35)** — two. `U_C` needs four.
Pads 16/26 are input-only; 28/29/30 are GPIO35/36/37 and are dead because this module is the
**N8R8** variant with **octal PSRAM**, which occupies GPIO33–37.

`U_C` is DNP on v10 as a consequence. `U3` carries the LoRa2021 function fully, so what is lost is
**redundancy, not capability**.

## The three measures, in order of value

### 1. Shared `RESET` and `BUSY`, individual `CS` — saves 2 GPIOs per extra radio

`RESET` and `BUSY` are not address-critical: every radio on the bus can be reset simultaneously,
and `BUSY` can be polled by asserting one `CS` at a time. Only `CS` must be unique.

Measured applicability on this board: the four `RESET` nets are already separate
(`/U3_RESET_N` 51 tracks, `/U_C_RESET_N` 0, `/F33_RESET_N` 40, `/E28_RESET_N` routed). Sharing them
would free **2 GPIOs** across three fitted radios — enough for half of `U_C`'s requirement on its
own.

Cost: **zero parts.** Two traces merge instead of four running separately.

### 2. `CS` on a 3-to-8 decoder — turns 3 GPIOs into 8 chip-selects

Candidates verified on LCSC by this project:

| LCSC | part | package | note |
|---|---|---|---|
| `C52145496` | CJ74HC138AEN | SOP-16 | $0.162 @5, 890 in stock |
| `C22439339` | HANSCHIP 74HC138DRG | SOP-16 | alternate |

Net effect with 4 radios: instead of 4 individual `CS` GPIOs, **3 select lines** address up to 8
devices. Saves **1 GPIO now**, and scales — a fifth to eighth radio costs zero further pins.

Cost: **~$0.16** plus one SOP-16 site and 3 select traces.

### 3. I2C GPIO expander — fan-out with **zero** MCU pins

`C506653` MCP23017-E/SS, 16 I/O on 2 pins, ~$1.

**The bus already exists and is already routed.** Measured: `/I2C_SCL` 16 tracks (`U1.38` → `U6`),
`/I2C_SDA` 26 tracks (`U1.39` → `U6`). So an expander costs **no new MCU pin at all**.

Cost: ~$1, plus one site, plus its own decoupling.

## Why none of them is a v10 change — measured, not assumed

This is the part that decides it, and it is **geometry, not pin budget**:

- `U_C`'s four control pads span **19.81 mm**, on **opposite faces** of the module —
  left column `x ≈ 33.80`, right column `x ≈ 53.60`.
- Already-routed I2C copper is **16.7–17.7 mm** from `U_C`'s nearest control pad, and sits at
  `y ≈ 35–56` while `U_C` is at `y ≈ 15–19` — the opposite half of the board.
- The nearest unpopulated site that could host a SOT-23-6 / SOP-16 is **14.17 mm** away (`U2`, the
  DNP F33 PA, 18 pads).

So a decoder or expander placed near the bus needs **four traces crossing the full module** to
reach pads on both faces; placed near `U_C` it needs two traces 17 mm back to I2C **plus** a site
that does not exist there. Either way the copper lands in the same congested region where the
router has already failed five times on `/EN` and `/IO0`.

**A mux changes which nets must be routed; it does not change whether they can be.** The binding
constraint on `U_C` is escape geometry — the same 1.50 mm-on-1.27 mm pad arrangement that sealed
`/EN`.

## What v11 must do differently

Place the expander **deliberately**, at schematic time, adjacent to `U_C` — not retrofit it to a
fixed layout. Then:

- `U_C` costs **0 MCU pins**
- `IO3` and `IO42` are released for other work
- measures 1 and 2 compound with it

Expected v11 pin budget with all three: `U3`, `U2`, `U_C` and `U_LORA1280` addressed with roughly
**3 select lines + shared RESET/BUSY + expander fan-out**, versus 18 individual control GPIOs
today. That is the difference between "no room for a fourth radio" and "room for eight".

## Reproduce

```
/usr/bin/python3 tracker/hardware/tmp_probes/mux_feasibility.py
/usr/bin/python3 tracker/hardware/tmp_probes/i2c_expander_feasibility.py
```
Both read `docs/analysis/bulk-route-20261107/work.kicad_pcb` and print the distances and spans
cited above. `pcbnew` lives in the **distro** python, not the project venv.

## What would change this decision

If a future board places `U_C` with control pads on **one face**, or leaves a site within ~5 mm of
it, measure 3 becomes viable on that revision without a respin.
