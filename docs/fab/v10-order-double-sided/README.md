# v10 order bundle

Two variants, identical gerbers, one difference: **whether the four bottom-side diodes are placed by
JLC or by you.**

| | `v10-order-top-only/` | `v10-order-double-sided/` |
|---|---|---|
| Placements | **19**, all top | **23**, 19 top + 4 bottom |
| Bottom parts | none | `D_BP1`–`D_BP4` (SS24, SMA) |
| JLC tier | **Economic PCBA** | **Standard PCBA only** |
| Hand-solder | 4 × SMA diode | nothing extra |

**JLCPCB offers double-sided placement only on Standard PCBA.** A double-sided board takes the full
Standard fee structure even if it is otherwise an Economic-class design. So the choice is:

- **top-only** — cheaper tier, you solder four large SMA parts (very easy, 2 pads each, clearly
  marked on the bottom silkscreen)
- **double-sided** — no extra soldering, higher assembly fee

Both zips are complete and self-contained. Upload whichever you choose; nothing needs regenerating.

## Upload one file

```
v10-jlcpcb-upload.zip      290 KB, 15 entries
```

11 gerber layers + drill + job + BOM + CPL. One archive removes the "forgot a layer" mistake.

`hand-fit-NOT-FOR-JLC.csv` is deliberately **not** in the zip: those parts have no LCSC number, and a
BOM containing them stalls the order on a no-match.

## Board settings

| | |
|---|---|
| Dimensions | **72.00 × 80.00 mm** (centreline) |
| Layers | **4** |
| Thickness | 1.6 mm |
| Copper | **1 oz** outer |
| Surface finish | **ENIG** |
| Quantity | **10** |
| Castellated holes | **YES** (`T3C1.000` × 15 at the wing tabs) |
| Edge plating | **No** |
| Parts substitution | **OFF** |

**Why ENIG + 1 oz:** all 161 vias are `0.300` drill / `0.600` land → **0.150 mm annulus**, exactly
JLCPCB's multilayer floor. HASL's thickness tolerance eats into that margin; ENIG's does not, and
1 oz keeps plating build-up inside the same budget.

**Why not "top side only" on the JLC form for the double-sided variant:** that form field controls
which paste/stencil is used. Saying top-only while shipping a CPL with 4 bottom rows gets the bottom
parts silently skipped.

## DNP — 11 parts, absent from BOM and CPL

`U_C`, `U2` (F33 PA), `U5` (MAX-M10S GPS), `U6` (MS5611 baro), `C_CAP1`, `C_CAP2`, `U_CUT1`–`U_CUT4`,
`U_HUB_CVT`, `J_VCC`. 49 footprints total, **23 placed**.

## Six parts you always solder yourself

`J_W1`–`J_W4` (wing sockets), `U3` (LoRa2021), `U_LORA1280` (SX1280). No LCSC numbers exist for them.

## Two wires, after the boards arrive

| net | from → to | length |
|---|---|---|
| `/EN` | `U1.3` → `J_PROG.3` | 30.7 mm |
| `/IO0` | `U1.27` → `J_PROG.6` | 17.2 mm |

**Flash-time only.** A blank board flashes over the ESP32-S3's native USB-Serial-JTAG with neither
wire — the ROM bootloader handles entry itself. Neither affects anything in flight.

## Verified before this bundle was built

| check | result |
|---|---|
| Gerbers vs board of record | **11/11 layers geometrically identical**, drill 196 = 196 |
| BOM ↔ CPL designators | sets identical in both variants |
| CPL coordinates vs board pads | **0.0000 mm** residual |
| Assembly attributes vs plan | **0** of 49 disagree |
| DRC | 16 violations / 12 unconnected, all classified non-flight |

## What you are NOT getting

Three nets stay unrouted: `/SPI2_SCK` (other end is the DNP `U2`), `/EN` and `/IO0` (flash-time only).
Every flight part — `U1`, `U3`, `U_LORA1280`, `U7` — has **zero** single-pad nets and the power path
is complete. See `docs/analysis/FINDING-flight-readiness-audit.md`.
