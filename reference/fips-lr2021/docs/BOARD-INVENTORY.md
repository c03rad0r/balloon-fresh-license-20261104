# LR2021 board inventory — x280 bench

Recorded 2026-11-04. Every LR2021 board on the bench: how it is identified, how it
is wired, what firmware it carries, and what it still needs before it can carry
FIPS traffic.

## Identification rule

The USB ID is authoritative — not the silkscreen and not the label on the carrier.

| USB ID | Meaning |
|---|---|
| `2e8a:000a` | RP2040 running firmware |
| `2e8a:0003` | RP2040 in BOOTSEL |
| `2e8a:000c` | RP2040 running a debugprobe (CMSIS-DAP) |
| `303a:1001` | ESP32 running firmware |
| `303a:4001` | ESP32 in ROM download mode |
| `1a86:7523` | CH340 USB-UART (the E80's onboard bridge chip) |

An **ESP32 can never produce a `2e8a` ID**, and an RP2040 can never produce a
`303a` one. This is the only way to settle "which board is this" without opening
the enclosure.

### Identifying the two E80s

CH340s carry **no serial number**, so the two E80s are indistinguishable by ID.
The only stable identifier is the **USB path**, which survives replugging:

| USB path | Board |
|---|---|
| `1-1.1` | E80 wired for SPI bypass (with the ESP32-S3) |
| `4.1.3` | E80 driven by its own STM32 |

`ttyUSB*` numbers **do** change across replugs — do not rely on them.

## The five LR2021 radios

| # | Board | Host MCU | USB identifier | USB path | Radio firmware |
|---|---|---|---|---|---|
| 1 | NiceRF carrier | ESP32-C3 | `B0:A6:04:00:96:DC` | `4.1.4` | none |
| 2 | NiceRF carrier | ESP32 | `88:56:A6:7B:C6:98` | `4.1.2` | none |
| 3 | NiceRF + GPS | RP2040 | `E663B035977F242D` | `1.2.1.2` | our bridge, TX fails |
| 3b | *(same carrier)* | ESP32 | `70:AF:09:21:FB:18` | `1.2.1.1` | none |
| 4 | E80-900MBL-02 | ESP32-S3 | `123456` (`303a:4001`) | `1.4` | none, in BOOTSEL |
| 5 | E80-900MBL-02 | STM32F103 | CH340 (no serial) | `1.1` | our bridge, works |

Board 3 carries **two** host MCUs — an RP2040 and an ESP32 — on adjacent hub
ports. That is the "second RP2040" that does not exist; a long round of board
shuffling was spent chasing it.

An SWD probe `203584200D2D0D42` (`2e8a:000c`, path `1.3`) is present when
attached. It is a tool, not a radio.

## Wiring

### E80 debug header (boards 4 and 5)

Four pins, labelled `C D G V`:

| Header | Signal |
|---|---|
| C | SWCLK |
| D | SWDIO |
| G | GND |
| V | 3V3 — **leave open** |

### E80 J2 SPI bypass (board 4)

`J2` is a **2×9 dual-row header, zigzag numbered**: odd pins down one column, even
pins down the other.

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

| J2 | Signal | ESP32-S3 silk label |
|---|---|---|
| 13 | SCK | `6` |
| 11 | MOSI | `7` |
| 9 | MISO | `2` |
| 15 | NSS | `10` |
| 7 | BUSY | `4` |
| 10 | DIO8 / IRQ | `5` |
| 5 | radio NRST | `3` |
| — | GND | debug header GND or USB shell |

Three things that are not optional:

1. **J2 has no GND pin.** All 18 are signals or power.
2. **J2-5 is the radio's reset, not the STM32's.** They are different nets.
3. **The STM32 must be held in reset** by keeping its RESET button pressed, so its
   pins float and release the shared SPI bus. This fights only a 10 kΩ pull-up
   (~0.33 mA) and is fully reversible.

Do not connect 3V3 between the boards. Each is powered from its own USB; the E80's
LDO runs from VBUS regardless of the STM32's state.

### NiceRF carrier RP2040 (board 3)

| Radio signal | RP2040 GPIO |
|---|---|
| SCK | GP2 |
| MOSI | GP3 |
| MISO | GP4 |
| NSS | GP5 |
| BUSY | GP6 |
| IRQ | GP7 |
| radio NRST | GP8 |

Two settings differ from the E80 and are **required** on this carrier:

- **IRQ routed on DIO9** (the E80 uses DIO8).
- **FRF frequency encoding**: `frf = f × 2^18 / 52 MHz`, 3 bytes (the E80 uses
  plain 4-byte Hz).

Boards 1 and 2 have **not** had their pin maps verified.

## Intended use

All five are meant to look identical to the host: a serial port speaking the
`A5 5A … CRC16` protocol in `docs/BRIDGE-PROTOCOL.md`. That way `fips-lr2021ctl`,
`fips-lr2021d` and the FIPS `lr2021` transport work unchanged, and the host does
not care which MCU sits behind the radio.

| # | Intended use | Blocker |
|---|---|---|
| 1 | FIPS node (ESP32-C3 + NiceRF) | no bridge firmware; ESP-IDF port not written |
| 2 | FIPS node (ESP32 + NiceRF) | same |
| 3 | FIPS node (RP2040 + NiceRF + GPS) | bridge flashed, **radio never completes TX** |
| 4 | FIPS node (ESP32-S3 + E80 via SPI) | no bridge firmware; S3 sitting in BOOTSEL |
| 5 | FIPS node (E80 via STM32) | **works** — HELLO/CFG/STATUS verified |

## Onboarding status

**Ready:** board 5.

**Blocked on one piece of firmware:** boards 1, 2 and 4. Every ingredient exists
but is not joined:

- SPI + LR2021 init/TX/RX: `firmware/esp32-c3-flrc` (proven at 20 MHz)
- Host protocol: `reference/fips-lr2021/firmware/rp2040-bridge` (~300 lines)
- Host side: unchanged

**Blocked on radio init:** board 3. The host protocol works and SPI reads the chip
version, but every TX times out — even with the DIO line bypassed by polling the
IRQ status register, and at both 915 MHz and 2.4 GHz. The carrier's own firmware
uses a different init sequence; porting it is the likely fix.

## Traps that cost real time

1. **Sync word.** The E80's STM32 firmware hardcodes `0x2DD4D4B2` and ignores the
   sync word in `CFG`. A peer must match it (`--sync-word 2dd4d4b2`).
2. **IRQ DIO differs per carrier** — E80 uses DIO8, the NiceRF/GPS carrier DIO9.
3. **Frequency encoding differs per carrier** — plain 4-byte Hz vs FRF.
4. **`esptool --after hard-reset` does not reset** a chip on USB-Serial/JTAG.
   Use `--after watchdog-reset`.
5. **Do not power-cycle an ESP32 running probe/bridge firmware.** It can wedge the
   application; only a reflash recovers it.
6. **Two probes on one SWD header contend.** Use one at a time.
7. **The power LED is not the 3.3 V rail.** Measure `V` on the debug header.
8. **Only the probe firmware answers `303a:1002`.** A test image enumerates as
   `303a:1001`, which produces the same "no connection" output as a dead target —
   confirm which one you have before trusting a negative result.
