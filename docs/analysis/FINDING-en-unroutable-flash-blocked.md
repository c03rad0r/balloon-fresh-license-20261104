# FINDING — why `/EN` cannot be routed, and what that means for the order

**Date:** 2026-11-09
**Board:** `docs/analysis/bulk-route-20261107/latest.kicad_pcb`
**Subject:** the two real routing gaps (`/EN`, `/SPI2_SCK`) and the flashing consequence

---

## 1. `/EN` and `/SPI2_SCK` are not "hard opens" — they are geometrically sealed

Three independent tools agree, and now the reason is measured rather than asserted:

| tool | result |
|---|---|
| `tracker/hardware/route_v10_astar.py --append` at pitch 0.05/0.10/0.15/0.20/0.25 | routed **0**, failed 2 |
| `route_v10_astar.py --dry-run` (no existing copper loaded) | "routed 1 net" — **optimistic, and wrong**: it ignores the copper it has to thread |
| `docs/analysis/reach_fast.py` | "PAD-LOCAL pocket on F.Cu" for both |
| flood fill from `U1.3` at 0.1 mm, 0.20 clearance (this work) | **205 reachable cells, bbox 2.0 × 1.4 mm** |

**The mechanism:** `U1` is an ESP32-S3-WROOM-1U. Its castellated pads are **1.50 mm wide on a
1.27 mm pitch**, so adjacent pads *overlap* in X by 0.23 mm:

```
pad 2 (+3V3)  ---- 1.50 wide
pad 3 (/EN)   ---- 1.50 wide     pitch 1.270
pad 4 (SPI2)  ---- 1.50 wide
```

`free gap between pad 2 and pad 3 copper = 1.270 − 1.500 = −0.230 mm`

A track needs `clearance + width + clearance = 0.20 + 0.20 + 0.20 = 0.600 mm` of clear channel.
There is **−0.230 mm**. So a pad can only be escaped **straight out along its own X axis**, never
sideways. Measured escape route for `U1.3`:

```
 inward +X 1.0mm -> BLOCKED by /SPI2_MISO
 outward -X 1.0mm -> clear
 inward +X 2.0mm -> BLOCKED by /F33_CS_N
 outward -X 2.0mm -> BLOCKED by /SPI1_MISO
 inward +X 3.0mm -> clear      (beyond the neighbouring fan-out)
```

Both escape lanes are crossed by already-routed nets within 2 mm. The 205-cell pocket in the flood
fill is exactly that 2 mm × 1.4 mm strip. **`J_PROG.3` is 22 mm away and unreachable.**

This is not a router weakness and not a rule violation: the pad is physically walled in by its own
package geometry plus the existing fan-out. Closing it needs a **layer change out of the module
shadow**, which needs a via — and a via needs `clearance + via_d + clearance = 0.20 + 0.60 + 0.20
= 1.000 mm` of clear channel on the escape lane. The lane is 0.23 mm short before anything is added.

## 2. Consequence for manufacturing: the board cannot enter download mode

Measured with `docs/analysis/flash_path_check.py`:

| net | copper | pads |
|---|---|---|
| `/USB_DN` | **HAS** (20 segments/vias) | `U1.13`, `J_PROG.4` |
| `/USB_DP` | **HAS** (47) | `U1.14`, `J_PROG.5` |
| `/EN` | **NONE** (0) | `U1.3`, `J_PROG.3` |
| `/IO0` | **NONE** (0) | `J_PROG.6` only — **no U1 pad is assigned** |

So the USB data pair reaches the header and the module. **Neither strap does.**

The schematic already records this, and it is *not* an oversight — `OPEN-16` says:

> "J_PROG pin 6 carries /IO0 but NOTHING at the U1 end is connected to it: no U1 pad is assigned to
> /IO0 on v10. Cause: the WROOM-1U GPIO0 pad number is named by no in-repo source (an earlier guess
> of pad 25 was WRONG — pad 25 is IO48). **Workaround in force: flashing works over
> USB-Serial-JTAG via EN + USB D+-, which needs no GPIO0.**"

That workaround is **not satisfied on this board**, because it depends on `EN` reachable — and `EN`
is one of the two nets that cannot be routed.

**Conclusion: as fabricated, the board has no wired way to be put into download mode.** It can be
powered and will run firmware already in flash, but a blank module cannot be programmed without
touching the module pads by hand.

## 3. The 2-wire rework, and why it is not a routing fix

`U1.3` (EN) and `U1`'s IO0 pad → `J_PROG.3` / `J_PROG.6`. Both `U1` pads are reachable *from the
module side*; what is blocked is the lateral escape into the board interior. Wires soldered directly
to the castellated pads and run to the header bypass the constraint entirely, because they are not
constrained by the 0.20 mm rule.

This is a real fix for building 4–10 units. It is **not** acceptable for a production revision:
the respin should move `EN`/`IO0` fan-out out of the module shadow, or add the reset RC
(10 kΩ + 1 µF per the Espressif datasheet, which ADR-108 already names but which is **not in the
BOM and not on the board**).

## 4. What is genuinely missing from the schematic (critical path, ordered)

1. **`EN` reset RC** — 10 kΩ + 1 µF, named by ADR-108 R1, absent from the BOM and the board.
   Without it there is no power-on reset ramp and no debounce.
2. **`IO0` assignment** — no `U1` pad carries `/IO0`. Requires reading the Espressif pin table off a
   physical module; the schematic says a previous guess (pad 25) was wrong and was reverted.
3. **`U_C` (bare LoRa2021, site C)** — `U_C.6/7/14/15` (`CS_N`, `BUSY`, `RESET_N`, `IRQ`) are
   single-pin nets with **no copper and no partner pad**. The module is on the SPI1 bus and cannot be
   addressed. ADR-128 records this as unfinished netlist work. **Recommendation: leave `U_C` off the
   assembly BOM** until these four lines exist.
4. **`J_VCC`** — a solder jumper whose footprint *is* the part. Correctly excluded; not a gap.

## 5. What this means for the order

The board is **manufacturable and will run firmware**, but **not programmable as built**. For a
first article whose purpose is to learn:

* order **assembled** (4–10 boards),
* leave **`U_C` unpopulated**,
* expect a **2-wire EN/IO0 rework per board** before the first flash,
* the 5 REAL DRC opens are unchanged and remain excluded by the gate (PASS REAL 5).

The respin that makes this a *flight* board needs items 1–3 above. None of them is reachable by
routing this revision further.

---

## Reproduce

```
/usr/bin/python3 docs/analysis/reach_fast.py \
    docs/analysis/bulk-route-20261107/latest.kicad_pcb --nets "/EN"
/usr/bin/python3 docs/analysis/flash_path_check.py \
    docs/analysis/bulk-route-20261107/latest.kicad_pcb
/usr/bin/python3 tracker/hardware/route_v10_astar.py \
    --board docs/analysis/bulk-route-20261107/latest.kicad_pcb --nets "/EN" --append
/usr/bin/python3 tracker/hardware/check_unconnected_exclusions.py \
    docs/analysis/bulk-route-20261107/latest.kicad_pcb \
    --drc <kicad-cli pcb drc --format json output> --expect-real 5
```
