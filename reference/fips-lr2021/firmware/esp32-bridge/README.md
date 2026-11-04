# ESP32 bridge for LR2021

ESP-IDF implementation of the host bridge protocol, so an ESP32-hosted LR2021 can
act as a FIPS transport. Same wire protocol as the RP2040 and STM32 bridges
(`docs/BRIDGE-PROTOCOL.md`), so `fips-lr2021ctl`, `fips-lr2021d` and the FIPS
`lr2021` transport work unchanged.

It reuses the proven raw register driver from `firmware/e80-bypass/common` by
supplying the ESP-IDF equivalents of the RP2040 macros the driver expects.

## Build

```bash
# ESP32-C3 (NiceRF carrier)
idf.py set-target esp32c3 && idf.py build

# ESP32-S3 (E80 via SPI bypass)
idf.py set-target esp32s3 && idf.py build
```

The component is built from the repo root so the shared headers resolve:

```bash
docker run --rm -v "$PWD/repo":/project -w /project/reference/fips-lr2021/firmware/esp32-bridge \
  espressif/idf:release-v5.5 bash -lc 'idf.py set-target esp32c3 && idf.py build'
```

## Flashing

The ESP32 must be in ROM download mode (**hold BOOT, tap RESET, release**), then:

```bash
esptool.py --chip esp32s3 -p /dev/ttyACMx -b 460800 \
  --before no-reset --after watchdog-reset \
  write-flash 0x0 build/bootloader/bootloader.bin \
              0x8000 build/partition_table/partition-table.bin \
              0x10000 build/esp32-bridge.bin
```

`--after watchdog-reset` is required — `hard-reset` does not reset a chip running
on USB-Serial/JTAG.

After flashing the board enumerates as `303a:1001` and speaks the binary protocol
on that CDC port:

```bash
fips-lr2021ctl --serial /dev/ttyACMx --sync-word 2dd4d4b2 hello
```

## Pin map

From `firmware/e80-bypass/common/e80_pinmap.h` (`E80_HOST_ESP32C3`):

| Radio signal | ESP32 |
|---|---|
| SCK | GPIO6 |
| MOSI | GPIO7 |
| MISO | GPIO2 |
| NSS | GPIO10 |
| BUSY | GPIO4 |
| IRQ | GPIO5 |
| NRST | GPIO3 |

Plus a shared ground. On an E80, `J2` has no GND pin — take ground from the debug
header or the USB shell — and the STM32 must be held in reset.

## Per-carrier differences

Selected in `main/CMakeLists.txt` by target:

| Setting | ESP32-C3 (NiceRF) | ESP32-S3 (E80) |
|---|---|---|
| Init sequence | carrier variant | E80 demo variant |
| IRQ DIO | 9 | 8 |
| Frequency encoding | FRF | plain 4-byte Hz |

Both are guesses for the NiceRF boards until verified — the C3 path matches the
RP2040 carrier's own firmware, which is the only evidence available.

## Notes

- The RX path polls the radio's IRQ status register over SPI rather than reading
  the DIO line, so a mis-routed IRQ cannot break reception. This costs a little
  SPI traffic and removes a whole class of failure.
- Defaults are EU: 868.1 MHz, FLRC-650, +14 dBm, sync `2DD4D4B2`.
- Keep the 1% duty cycle in mind on 868.0–868.6 MHz.
