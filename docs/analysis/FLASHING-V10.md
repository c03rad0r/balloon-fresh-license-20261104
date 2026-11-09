# Flashing the v10 hub: does it need `IO0`/`EN` at all?

**2026-11-09.** Answers the question "how will we flash these boards", and narrows the two
remaining unrouted nets from *blocking* to *belt-and-braces*.

## What the board actually has

There is **no USB connector** on the board. Programming reaches the ESP32 only through
`J_PROG`, a 1x6 2.54 mm header:

| pin | net | copper | reaches |
|---|---|---|---|
| 1 | `GND` | 39 tracks | — |
| 2 | `+3V3` | 24 tracks | — |
| 3 | `/EN` | **0 tracks** | `U1.3` (30.71 mm away, unrouted) |
| 4 | `/USB_DN` | 19 tracks | `U1.13` = GPIO19 |
| 5 | `/USB_DP` | 46 tracks | `U1.14` = GPIO20 |
| 6 | `/IO0` | **0 tracks** | `U1.27` = GPIO0 (netlist fixed, unrouted) |

So `D+/D-` are wired to the ESP32-S3's **native USB Serial/JTAG** pins. That is the part that
matters, and it is the thing that changes the answer.

## What esptool's documentation says

From `docs/en/advanced-topics/boot-mode-selection.rst`:

> `esptool` resets the chip automatically by asserting `DTR` and `RTS` control lines of the USB to
> serial converter chip, i.e., FTDI, CP210x, or CH340x. The `DTR` and `RTS` control lines are in
> turn connected to `GPIO0` and `EN` (`CHIP_PU`) pins.

and it lists when automatic reset is **impossible**:

> - Your hardware does not have the `DTR` and `RTS` lines connected to `GPIO0` and `EN`
> - There are no such serial control lines at all

**This board has no USB-to-UART bridge at all.** `D+/D-` go to the ESP32-S3 directly. There are no
`DTR`/`RTS` lines, so the classic two-transistor auto-reset circuit **cannot exist here** — it
requires a bridge chip to provide them.

## So how does it work?

The ESP32-S3 has a second path the classic ESP32 does not: **USB Serial/JTAG is implemented in
hardware inside the chip** and the **ROM bootloader exposes it**. That means:

1. **A blank or unbootable board** — flash empty, or no valid app — falls into the ROM bootloader,
   which enumerates on the USB pins. `esptool` can talk to it and flash **without touching `IO0` or
   `EN`**. This is the first-flash case, and it is the case that matters for 10 new boards.
2. **Reflashing a running board** — depends on the firmware keeping the USB Serial/JTAG console
   enabled (`CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG`). If it does, `esptool --before
   usb_reset` can request a reset into download mode over USB alone. If the running firmware
   disables it, you are back to a manual reset.

## What this means for the order

**The two unrouted nets are not a flashing blocker for new boards.** They are:

- **`/EN`** — a *reliability* lever. With it, you can force a hard reset from the header. Without
  it, an unresponsive board needs a power cycle.
- **`/IO0`** — a *fallback* lever for forcing download mode if the USB-Serial-JTAG path fails
  because running firmware has disabled the console.

Both remain worth having. Neither is required to flash a fresh board.

## Recommendation, and why it is not "keep grinding the router"

Order the 10 boards. On the bench, flashing goes:

    J_PROG.4/5  ->  a 2-wire USB cable to the ESP32-S3's USB pins
    (no bridge chip, no DTR/RTS, no adapter)

For the first build this works through the ROM bootloader. To make reflashing reliable regardless
of firmware state, add the two wires during assembly as planned — they are 2.54 mm header pins, not
fine-pitch work.

Do **not** enable any firmware option that disables the USB Serial/JTAG console on flight firmware,
or you re-create the flashability problem for a board in the air.

## What is NOT proven here

- This is documentation reasoning, not a measurement on this board. Nobody has put a cable on a
  v10 hub.
- Point 2 above (reflash of a running board over USB only) depends on firmware configuration we
  have not fixed yet.
- Therefore the two bodge wires stay in the assembly plan. This document downgrades them from
  "required" to "recommended", not to "unnecessary".
