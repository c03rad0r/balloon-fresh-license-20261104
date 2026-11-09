# v10 JLCPCB order — upload bundle

**Everything in this directory was measured from `work.kicad_pcb` on 2026-11-09, not remembered.**
Rebuild it any time with:

```
/usr/bin/python3 tracker/hardware/build_order_bundle.py
```

## Upload this one file

```
v10-jlcpcb-upload.zip      290 KB, 15 entries
```

It contains the 11 gerber layers, the drill file, the job file, the BOM and the CPL. Uploading one
archive removes the "I forgot a layer" class of mistake.

If the JLCPCB form wants the files separately, `gerbers/` holds them flat and `bom-jlc.csv` /
`cpl-jlc.csv` sit alongside.

**`hand-fit-NOT-FOR-JLC.csv` is deliberately not in the zip.** Those six parts have no LCSC number
and you solder them yourself; sending them to JLC stalls the order on a no-match.

## Board

| | |
|---|---|
| Dimensions | **72.00 × 80.00 mm** |
| Layers | **4** |
| Thickness | 1.6 mm |
| Copper | **1 oz** outer |
| Surface finish | **ENIG** |
| Quantity | **10** |
| Assembly | **Double-sided PCBA** — 19 top, **4 bottom** |

**Why ENIG and 1 oz:** every one of the 161 vias is `0.300 mm` drill with a `0.600 mm` land, giving a
**0.150 mm` annulus — exactly JLCPCB's multilayer floor. HASL's thickness tolerance eats into that;
ENIG's does not. 1 oz keeps the plating build-up inside the same budget.

**Why double-sided:** `D_BP1`–`D_BP4` are on the **bottom**. A single-sided quote silently drops four
bypass diodes. This is a different price line than top-only assembly.

## Settings that matter

- **Castellated holes: YES.** The wing tabs are castellated (`T3C1.000 × 15`).
- **Edge plating: No.** Not needed, and it is a separate charge.
- **Parts substitution: OFF.** Every line is a specific LCSC number verified against stock; a
  substitute would be an unaudited part in a flight board.
- **Confirm production file: YES**, then read the preview before paying.

## What is DNP — and therefore not in the BOM or CPL

`U_C`, `U2` (F33 PA), `U5` (MAX-M10S GPS), `U6` (MS5611 baro), `C_CAP1`, `C_CAP2`, `U_CUT1`–`U_CUT4`,
`U_HUB_CVT`, `J_VCC`.

11 parts, 49 footprints, **23 placed**.

## Six parts you solder yourself

`J_W1`–`J_W4` (wing sockets), `U3` and `U_LORA1280` (the two radios). See `hand-fit-NOT-FOR-JLC.csv`.

**These carry no LCSC number**, so a BOM containing them cannot be priced by JLC.

## Two wires, after the boards arrive

| net | from → to | length |
|---|---|---|
| `/EN` | `U1.3` → `J_PROG.3` | 30.7 mm |
| `/IO0` | `U1.27` → `J_PROG.6` | 17.2 mm |

**Flash-time only.** A blank board flashes over the ESP32-S3's native USB-Serial-JTAG without either
wire — the ROM bootloader handles entry itself. The wires are for *reflash convenience*, and neither
affects anything in flight. See `docs/analysis/FLASHING-V10.md`.

## Verified before this bundle was built

| check | result |
|---|---|
| Gerbers vs board of record | **11/11 layers geometrically identical**, drill 196 hits |
| BOM ↔ CPL designators | **23 = 23**, sets identical |
| CPL coordinates vs board pads | **0.0000 mm** residual on all 23 rows |
| Assembly attributes vs plan | **0** of 49 disagree |
| DRC | 16 violations / 12 unconnected, all classified non-flight |

Reproduce:

```
/usr/bin/python3 tracker/hardware/verify_gerbers_fresh.py    # gerbers vs board
/usr/bin/python3 tracker/hardware/check_order_files.py <board> <bom> <cpl>
/usr/bin/python3 tracker/hardware/tmp_probes/flight_critical_audit.py
```

## What you are NOT getting

Three nets stay unrouted: `/SPI2_SCK` (other end is the DNP `U2`), `/EN` and `/IO0` (flash-time
only). Every flight part — `U1`, `U3`, `U_LORA1280`, `U7` — has **zero** single-pad nets, and the
power path is complete. See `docs/analysis/FINDING-flight-readiness-audit.md`.

`U_C` is DNP: its four control nets have no MCU end because only 2 usable GPIOs remained. `U3` covers
the function. ADR-145 records the v11 fix.
