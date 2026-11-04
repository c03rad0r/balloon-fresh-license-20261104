# Flashing an E80 with an ESP32-S3 CMSIS-DAP probe

This replaces the Raspberry Pi Pico probe with an ESP32-S3 running Espressif's
`esp-usb-bridge` firmware. The S3 is only the programmer; the E80's STM32 is the
FIPS bridge.

## Hardware

- ESP32-S3 DevKitC-1 N8R2 or N16R8 with **native USB** (`303a:1001` / `303a:1002`)
- E80-900MBL-02 debug header, labeled **C D G V**
- 3 dupont wires
- Two USB-C data cables (S3 and E80)

## Wiring

| E80 | Signal | ESP32-S3 | DevKitC-1 header pin |
|---|---|---|---|
| C | SWCLK | GPIO10 | **J1 pin 16** |
| D | SWDIO | GPIO8 | **J1 pin 12** |
| G | GND | GND | **J1 pin 22** or **J3 pin 1** |
| V | 3V3 | **leave open** | — |

The physical header pin numbers matter on the DevKitC-1. J1 is the header with
3V3/RST/GPIO4…GPIO14; J3 is the header with G/TX/RX/GPIO1…GPIO21. GPIO10 is
**not** pin 10 of the header — it is J1 pin 16.

The E80 is powered by its own USB. The S3 is powered by its own USB. Only GND is
shared. Do not connect V to the S3.

Verify before powering:

- G has continuity to the E80 USB-C shell.
- V is 3.3 V when the E80 is powered.
- No short between 3V3 and GND, or between GPIO8/GPIO10 and GND.
- If OpenOCD cannot read IDR, swap C and D.

## Build `esp-usb-bridge`

The firmware is built for ESP32-S3 with the SWD interface:

```bash
git clone --recursive https://github.com/espressif/esp-usb-bridge
cd esp-usb-bridge
docker run --rm -v "$PWD":/project -w /project \
  -e SDKCONFIG_DEFAULTS='sdkconfig.defaults;sdkconfig.defaults.esp32s3;sdkconfig.swd.defaults' \
  espressif/idf:release-v5.5 \
  bash -lc 'idf.py set-target esp32s3 && idf.py build'
```

Build output:

```text
build/bootloader/bootloader.bin
build/partition_table/partition-table.bin
build/bridge.bin
```

## Flash the S3

The S3 must be in ROM download mode: **hold BOOT, tap RESET, release BOOT**.
There is no software path into download mode once `esp-usb-bridge` is running,
because that firmware owns the USB PHY.

```bash
esptool.py --chip esp32s3 -p /dev/ttyACM1 -b 460800 \
  --before no-reset --after watchdog-reset \
  write_flash 0x0 bootloader/bootloader.bin \
              0x8000 partition_table/partition-table.bin \
              0x10000 bridge.bin
```

Two traps, both measured:

- The running app **and** the ROM bootloader enumerate as `303a:1001`, so the
  USB ID alone does not tell you which one you have. Probe with
  `esptool ... chip-id` before trusting it.
- `--after hard-reset` prints "Hard resetting via RTS pin" but does **not**
  reset a chip running on USB-Serial/JTAG. Use `--after watchdog-reset`; that
  actually reboots into the application.

After the reset the probe enumerates as:

```text
303a:1002  Espressif Systems Co. Ltd. CMSIS-DAP
```

## Pin verification with a meter (do this before blaming the probe)

Flash a tiny image that drives one pin as a slow square wave, then measure the
E80 pad. This separates "is the wire right?" from "is the protocol right?" and
needs no working probe.

```c
gpio_set_level(10, level);          /* SWCLK */
vTaskDelay(pdMS_TO_TICKS(2000));    /* 2 s high, 2 s low */
```

Measured 2026-11-03 on S3 serial `94A9902E9484`:

| Build | E80 C | E80 D | Conclusion |
|---|---|---|---|
| GPIO10 toggles | 3.3 V ↔ 0 V | steady 3.3 V | GPIO10 → C **confirmed** |
| GPIO8 toggles, GPIO10 held low | steady 0 V | 3.3 V ↔ 0 V | GPIO8 → D **confirmed** |
| idle | — | — | V = 3.3 V, so the E80 is powered |

Both signal wires are proven. After this, a `cannot read IDR` is **not** a
wiring, soldering or pin-numbering fault.

Note: the app and the ROM bootloader both enumerate as `303a:1001`, so the USB
ID alone cannot tell them apart. Probe with `esptool ... chip-id` before
flashing, and use `--after watchdog-reset` — the "hard reset via RTS" path does
not reset a chip running over USB-Serial/JTAG.

## Test the probe

Espressif's own documentation for the SWD bridge gives this invocation:

```bash
openocd -s tcl -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c 'adapter speed 5000'
```

Two details matter:

- Use a **current** OpenOCD. Espressif syncs CMSIS-DAP fixes from mainline
  continuously; Ubuntu 24.04's `openocd 0.12.0-1build2` predates them.
- The documented speed is **5000 kHz**, not a conservative 100 kHz. The
  bit-banged SWD path was developed against that speed.

Expected on a good target:

```text
Info : SWD DPIDR 0x1ba01477
Info : [stm32f1x.cpu] Cortex-M3 r1p1 processor detected
```

Build a current OpenOCD (needs `libusb-1.0-0-dev`, `libjim-dev`,
`libhidapi-dev`, `libtool`):

```bash
git clone --depth 1 https://github.com/openocd-org/openocd
cd openocd && ./bootstrap
./configure --enable-cmsis-dap --disable-werror --prefix=/opt/openocd
make -j"$(nproc)" && sudo make install
```

The ESP USB Bridge supports **USB bulk (v2) only**; the HID backend is not
implemented.

## Flash the E80

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 5000; program e80_bench.elf verify reset exit"
```

## Root cause of `cannot read IDR`

It was never the hardware. **Two** things had to change, and both were needed:

1. **OpenOCD must be current.** Espressif syncs CMSIS-DAP fixes from mainline
   into its fork continuously. Ubuntu 24.04 ships `0.12.0-1build2`, which is too
   old. Git master `0.12.0+dev-g8443233` connects.
2. **`adapter speed 5000`.** Every failing attempt used 100 kHz or lower. The
   documented speed for this bridge is 5 MHz, and 5 MHz is what connects.

The Pico works at 100 kHz because it is a different CMSIS-DAP implementation.
Do not carry its speed over to the ESP32-S3.

## Current status (2026-11-03) — working

Verified end to end on S3 serial `94A9902E9484`, E80 on `/dev/ttyUSB6`:

```text
Info : SWD DPIDR 0x1ba01477
Info : [stm32f1x.cpu] Cortex-M3 r1p1 processor detected
** Programming Started **
Info : device id = 0x20036410
Info : flash size = 64 KiB
** Programming Finished **
** Verified OK **
```

Then, over the same board's USB serial:

```text
OK BRIDGE 115200
protocol=1 firmware=0.1.0 chip=0x1801 capabilities=0x0007
configured band=us915 freq=915000000 Hz flrc=1300 kbps power=22 dBm payload=255B relay=false
pong
tx=0 rx=0 crc=0 drops=0 timeouts=0 resets=0
```

The ESP32-S3 is therefore a verified replacement for the Pico probe.

## Checklist

- [x] S3 native USB enumerates (`303a:1001`)
- [x] `esp-usb-bridge` SWD build
- [x] S3 flashed with bridge
- [x] S3 enumerates as `303a:1002` CMSIS-DAP
- [x] OpenOCD sees the CMSIS-DAP probe
- [x] GPIO10 → E80 C verified by meter
- [x] GPIO8 → E80 D verified by meter
- [x] OpenOCD reads DPIDR through the S3
- [x] E80 flashed with the bridge firmware through the S3
- [x] E80 `hello`/`status` over USB
- [ ] Two-node FIPS test

## When the target does not answer

`cannot read IDR` has two very different causes: the probe, or the board.
Separate them with a multimeter before touching any firmware.

### 1. Prove the probe can both drive and read

A square-wave test only proves the **output** path. SWD also needs the probe to
**read** the target's ACK bits, so test the input path too:

```c
/* GPIO8 = input with pull-up, GPIO10 mirrors it */
gpio_set_level(10, gpio_get_level(8));
```

Ground the E80 `D` pad and watch `C`:

| Observation | Conclusion |
|---|---|
| C follows D low, returns high | GPIO8 **input** works |
| C never moves | GPIO8 input is damaged |

Measured 2026-11-03 on serial `94A9902E9484`: one clean falling edge and one
clean rising edge, so drive and read both work.

### 2. Prove the board is running

Reference is E80 `G`:

| Measure | Healthy | Meaning if wrong |
|---|---|---|
| `V` | ~3.3 V | rail down |
| `D` with nothing driving it | ~3.3 V | STM32 not executing |
| reset button, not pressed | 3.3 V on one side | NRST shorted |

The power LED is **not** evidence: on these boards it often hangs off USB 5 V,
not the 3.3 V rail.

### 3. Only then suspect the probe

If the probe drives and reads, the wiring carries both signals to the pads, `V`
is 3.3 V and NRST is high, yet the target will not connect at any speed — the
STM32 itself is at fault. A reset-window retry loop was run 120 times against
one such board, with `CMSIS-DAP: Interface ready` confirmed before the loop, and
never saw a `DPIDR`.

Check that the probe firmware is actually running before trusting a negative
result. A test image left on the S3 enumerates as `303a:1001` and gives the same
"no connection" output as a dead target — that mistake produced one invalid
result before it was caught.

Still use a current OpenOCD and `adapter speed 5000` for the first attempt; the
speed issue alone can make a healthy board look dead.
