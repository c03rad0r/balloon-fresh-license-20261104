# `/IO0` netlist fix — a dead pin became a reported gap

**Date:** 2026-11-09
**Board of record:** `docs/analysis/bulk-route-20261107/latest.kicad_pcb`
**Change:** one line — `U1.27` gains `net 49 "/IO0"`
**Hash:** `8a2e49e9` → `b90bf629`

---

## The defect

`/IO0` was a **single-pad net**. Its only pad was `J_PROG.6`. There was no MCU end at all,
because the netlist was grown by text transform rather than from a schematic (ADR-128's recorded
position), so the connection to `U1` was never generated.

A one-pad net **cannot be reported as unconnected** by DRC — there is nothing to connect it to. So
this defect was invisible in every count the project published. The board reported 11 unconnected
records and looked no worse than a board with a genuine routing gap.

## The fix, and why the pad is right

`U1.27` → GPIO0, the ESP32-S3 boot strapping pin.

The pad→GPIO map is not documented in the board file or the KiCad footprint (neither carries
pinfunction), so it was **proved against four functions the board already encodes**:

| pad | net on the board | GPIO |
|---|---|---|
| 13 | `/USB_DN` | 19 |
| 14 | `/USB_DP` | 20 |
| 36 | `/GNSS_TX` | 43 (U0TXD) |
| 37 | `/GNSS_RX` | 44 (U0RXD) |

Those agree with the WROOM-1U pinout, which fixes the numbering and makes pad 27 GPIO0.

**Pads 28/29/30 are GPIO35/36/37 and must not be used**: this module is the **N8R8** variant, its
8 MB PSRAM is **octal**, and octal PSRAM occupies GPIO33–37. Assigning a strapping input there would
look correct on a schematic and fail on hardware.

## Measured result (this verification, on the board of record)

Baseline and modified boards were DRC'd with their matching `.kicad_dru` in place — a re-named copy
silently loses the custom rules and reports 500+ library violations instead of 16, which would have
made any comparison meaningless.

```
                                  violations   unconnected   REAL
baseline  (8a2e49e9)                    16           11         5
with /IO0 (b90bf629)                    16           12         6
```

* **violations 16 → 16** — zero new faults
* **unconnected 11 → 12**, REAL **5 → 6**

The count went **up**, and that is the fix working: an unreported dead pin became a reported gap.
The gate (`check_unconnected_exclusions.py --expect-real 6`) **PASSES**.

## The routing was attempted and rejected — correctly

A router run produced 28 segments and reported `agreement_ok: true` while **shorting `/IO0` to
`/USB_DN` on B.Cu in two places**. DRC caught it (16 → 18 violations, two `shorting_items`); the
router's own validator did not. A boot-strapping line shorted to USB D− can damage the ESP32 during
flashing. **The route was reverted and no copper from it is present.** This is the second recorded
instance of the router passing its own check while emitting illegal copper.

`/EN` remains unroutable for the reason already recorded in
`FINDING-en-unroutable-flash-blocked.md`: the WROOM-1U pads are 1.50 mm wide on a 1.27 mm pitch, so
adjacent pads overlap by 0.23 mm and a pad can only be escaped along its own axis, where both lanes
are crossed by routed nets within 2 mm.

## Consequence for the order

The netlist is now correct for `/IO0`; the **copper is still absent**, so the board still cannot
enter download mode as built. Two wires (`U1.3`→`J_PROG.3`, `U1.27`→`J_PROG.6`) make both straps
usable. That is unchanged by this commit.

## `U_C` — same defect class, and it cannot be fixed on v10

`/U_C_CS_N`, `/U_C_BUSY`, `/U_C_RESET_N`, `/U_C_IRQ` are each single-pad nets at `U_C` only, while
`U3`'s equivalents are proper two-pad nets (`U1.20` ↔ `U3.6` etc). Fixing them needs **four** GPIOs.

Free usable `U1` pads: **IO3 (pad 15)** and **IO42 (pad 35)** — two. Pads 16/26 are input-only and
28/29/30 are octal-PSRAM. **`U_C` therefore cannot be fully wired on v10 without sacrificing a
signal.** Recommendation stands: leave `U_C` off the assembly BOM.

## Power path is intact

`/W1_SOLAR_P` (21 tracks, 1 via) → `D1` → `/VSCAP` (4 tracks, 4 vias, zone) → `U7` → `+3V3`.
The board flies on wing solar with `U_HUB_CVT` unpopulated.

---

## Reproduce

```
cd docs/analysis/bulk-route-20261107
kicad-cli pcb drc --format json --severity-all -o /tmp/drc.json latest.kicad_pcb
/usr/bin/python3 -B tracker/hardware/check_unconnected_exclusions.py \
    docs/analysis/bulk-route-20261107/latest.kicad_pcb --drc /tmp/drc.json --expect-real 6
```
