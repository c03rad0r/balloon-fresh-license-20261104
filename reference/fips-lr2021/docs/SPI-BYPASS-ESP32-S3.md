# E80 SPI bypass with an ESP32-S3 — wiring and wiring test

Purpose: drive the E80's LR2021 directly from an ESP32-S3 with the STM32 held in
reset. This removes the STM32 from the data path, which means the board works
even when its debug port or firmware is unusable, and it removes the 115200 UART
bottleneck.

This document covers the wiring and a minimal test that proves the wiring before
any radio protocol work.

## Wiring

E80 `J2` is a **2×9 dual-row header, zigzag numbered**: odd pins down one column,
even pins down the other.

```
Row 1:   1  VIN          |  2  3V3
Row 2:   3  DIO11        |  4  DIO10
Row 3:   5  radio NRST   |  6  3V3
Row 4:   7  BUSY         |  8  DIO7
Row 5:   9  MISO         | 10  DIO8  (IRQ)
Row 6:  11  MOSI         | 12  DIO9
Row 7:  13  SCK          | 14  MCU_TXD
Row 8:  15  NSS          | 16  MCU_RXD
Row 9:  17  DIO6         | 18  DIO5
```

Pin 1 is marked on the board (silkscreen `1`, square pad, or dot). Confirm it
electrically: with the board USB-powered, **3.3 V must appear on pins 2 and 6**
(even column, rows 1 and 3) with pin 4 between them. If 3.3 V is one column over,
the column assignment is flipped.

| E80 J2 | Signal | ESP32-S3 silk label | Notes |
|---|---|---|---|
| J2-13 | SCK | `6` | |
| J2-11 | MOSI | `7` | |
| J2-9 | MISO | `2` | |
| J2-15 | NSS | `10` | |
| J2-7 | BUSY | `4` | input |
| J2-10 | DIO8 | `5` | input, IRQ |
| J2-5 | radio NRST | `3` | **radio** reset, not the STM32 |
| — | GND | `GND` | debug header GND or USB shell |

### Non-negotiable extras

1. **STM32 NRST → GND.** Hold the E80 RESET button pressed (tape/Blu-Tack). The
   STM32 must be in reset so its pins float and stop driving the shared SPI bus.
   This fights only a 10 kΩ pull-up (~0.33 mA) and is fully reversible.
2. **Common ground** between the ESP32 and the E80.
3. **Do not connect 3V3/V.** Power each board from its own USB. The E80's LDO runs
   from VBUS regardless of the STM32's state.

`J2` has **no GND pin** — all 18 are signals or power.

## Wiring test

The ESP32-S3 reads `GET_VERSION` (opcode `0x0101`) and `GET_ERRORS` (`0x0110`):

```text
=== E80 SPI wiring test ===
SCK=6 MOSI=7 MISO=2 CS=10 BUSY=4 IRQ=5 RST=3
GET_VERSION -> 18 01 .. .. | GET_ERRORS -> 00 00 | BUSY=0 IRQ=0
```

| Result | Meaning |
|---|---|
| plausible version bytes, errors `00 00` | wiring correct, radio alive |
| `00 00 00 00` | MISO not connected, or radio held in reset |
| `FF FF FF FF` | MISO floating / CS not asserted |
| BUSY stuck high | BUSY not connected, or STM32 still driving the bus |

Run at 4 MHz first; raise to 20 MHz only after the version reads correctly.

## Flashing

The ESP32-S3 must be in ROM download mode (**hold BOOT, tap RESET, release**).
Then:

```bash
esptool.py --chip esp32s3 -p /dev/ttyACMx -b 460800 \
  --before no-reset --after watchdog-reset \
  write-flash 0x0 bootloader.bin 0x8000 partition-table.bin \
              0x10000 esp32s3-e80-spitest.bin
```

`--after watchdog-reset` is required; `hard-reset` prints a message but does not
reset a chip on USB-Serial/JTAG.

## Known caveats from the E80 side

- **IRQ DIO is 8 on the E80.** A different carrier in this project uses DIO9.
  Copying settings between boards produces total silence.
- The E80's STM32 firmware does **not** use the host's sync word — it hardcodes
  `0x2DD4D4B2`. Any peer must match that value.
- Do not power-cycle an ESP32-S3 that is running a probe/bridge application; it
  can wedge the firmware. Reset with esptool instead.
