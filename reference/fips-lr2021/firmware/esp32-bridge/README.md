# ESP32 bridge for LR2021

ESP-IDF implementation of the host bridge protocol, so an ESP32-hosted LR2021 can
act as a FIPS transport. It uses the same wire protocol as the RP2040 and STM32
bridges (`docs/BRIDGE-PROTOCOL.md`), so `fips-lr2021ctl`, `fips-lr2021d` and the
FIPS `lr2021` transport work unchanged.

## Supported hardware

The maintained target is an **ESP32-S3 wired to an E80-900MBL-02 LR2021 through
J2**. The E80's STM32 must be held in reset, or it contends for the shared SPI
bus. Follow the end-to-end build, wiring and onboarding guide:

- `../docs/E80-ESP32-S3-FIPS-ONBOARDING.md`
- `../docs/SPI-BYPASS-ESP32-S3.md`

The radio side links
`tracker/firmware/components/lr2021_transport` (`EspIdfLr2021Radio`). The
`LR2021_E80_COMPAT` build option selects the E80 sub-GHz implementation: plain
4-byte frequency in Hz, LF PA, DIO8, vendor FLRC-650 rate and packet framing. It
is not interchangeable with the older 2.4 GHz NiceRF driver defaults.

The NiceRF ESP32-C3 carriers have different RF/IRQ behavior. They are not a
supported equivalence path for this build, even though the host bridge protocol,
pin numbering and chip-version check may work.

## Build

From the firmware directory:

```bash
rm -f sdkconfig sdkconfig.old
docker run --rm \
  -v "$PWD/../../../..:/project" \
  -w /project/reference/fips-lr2021/firmware/esp32-bridge \
  espressif/idf:release-v5.5 \
  bash -lc 'idf.py set-target esp32s3 && idf.py build'
```

The firmware version currently reported by the validated S3 image is **0.4.21**
(NiceRF C3: **0.5.11**).
The build must set the main task stack to 8192 bytes (see `sdkconfig.defaults`)
because large protocol/radio buffer paths otherwise cause a boot loop.

## Flash

Use current esptool 5.x. An ESP32-S3 whose application uses native
USB-Serial/JTAG can normally be reflashed without pressing BOOT:

```bash
esptool --chip esp32s3 -p /dev/ttyACMx -b 460800 \
  --before usb_reset --after watchdog_reset \
  write-flash 0x0 build/bootloader/bootloader.bin \
              0x8000 build/partition_table/partition-table.bin \
              0x10000 build/esp32-bridge.bin
```

`--after watchdog_reset` is required; `hard_reset` does not reliably reset a
chip on USB-Serial/JTAG. If `usb_reset` is unavailable, enter ROM download mode
once with **BOOT held while tapping RESET**, then use `--before no_reset`.

## Pin map

| Radio signal | ESP32-S3 | E80 J2 |
|---|---|---:|
| SCK | GPIO6 | 13 |
| MOSI | GPIO7 | 11 |
| MISO | GPIO2 | 9 |
| NSS | GPIO10 | 15 |
| BUSY | GPIO4 | 7 |
| DIO8 / IRQ | GPIO5 | 10 |
| radio NRST | GPIO3 | 5 |

Plus a shared ground. J2 has no ground pin; take ground from another verified E80
pad/header. Power each board separately—do not connect 3V3 between them.

## Host checks

```bash
fips-lr2021ctl --serial /dev/ttyACMx hello
fips-lr2021ctl --serial /dev/ttyACMx --sync-word 2dd4d4b2 cfg --band eu868 --radio-payload 128
fips-lr2021ctl --serial /dev/ttyACMx status
```

Expected healthy version:

```text
protocol=1 firmware=0.4.21 chip=0x1801 capabilities=0x0007
```

`status` also emits cumulative FLRC packet/CRC/length statistics on this E80
build. The `GET_VERSION` read discards the two leading status bytes, so `01 18`
is the parsed firmware version; old raw-frame notes `07 21 01 18` contained the
status bytes too.

## Radio behavior found on hardware

- DIO8 is optional for operation: this bridge polls the IRQ **status register**,
  including TX_DONE. Poll it also for RX, so an unconnected DIO8/IRQ wire does
  not turn transmissions into false timeouts.
- FLRC FIFO writes contain opcode `0x0002` followed directly by payload; no
  software length byte is inserted. FIFO reads use opcode `0x0001` in one CS
  transaction with no dummy bytes.
- The SPI bridge reports hardware-CRC failures in its counters but still lets
  the host link decide validity. On this bench all short packets were marked as
  chip-CRC failures while intact payloads passed the link's CRC32. Full
  255-byte frames gave a control run of 20 packets with zero CRC errors.
- Initial radio configuration can fail intermittently; the bridge makes up to
  three bounded attempts and reports an EVT per failed attempt. Configuration
  success is not an OTA test by itself.

See the onboarding guide for measured evidence and the remaining larger-packet,
IPv6 and SSH validation work.
