# Learnings — LR2021 / FIPS bench, 2026-11-03 to 11-05

Consolidated so a future session does not rediscover any of this. Each item cost
real time; most cost an hour or more.

## Start here

| Need | Document |
|---|---|
| Flash without a button | `docs/FLASHING-WITHOUT-BUTTONS.md` |
| Which board is which | `docs/BOARD-INVENTORY.md` |
| Where the radio work stands | `docs/OTA-PROOF-PLAN.md` |
| Remote-access constraints | `docs/REMOTE-ACCESS-PLAN.md` |

## Flashing

- **RP2040 flashes remotely** via the 1200-baud touch (see the flashing doc).
- **ESP32-C3/S3 flash remotely** via `esptool --before usb_reset`, but the
  rebooting option must be `--after watchdog_reset` and that needs esptool 5.x.
- **E80 STM32 does not flash remotely.** SWD only. The UART ROM bootloader is
  unusable because the CH340 cannot do 8E1.
- `Broken pipe` during a 1200-baud touch is normal.
- Two probes on one SWD header contend; use one.

## Radio configuration

**The three firmware families drifted. Copy bytes from the vendor driver rather
than inferring them.** The vendor HAL (`firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver`)
encodes:

| Command | Vendor bytes |
|---|---|
| `SET_RF_FREQ` (0x0200) | frequency as 4-byte big-endian **Hz** |
| `SET_MOD_PARAMS` (0x0248) @650 kbps | `04 17` — br_bw 0x04, `(CR_3_4<<4)\|BT_1.0` |
| `SET_PKT_PARAMS` (0x0249) | `1E 7D` — `sync4B + (pre32<<2)`, `CRC2 + FIX<<2 + match123<<3 + txsw1<<6` |

What our driver had before: mod `04 25`, packet `0C 4C` (and later `0E 4D`). Both
were wrong — different coding rate *and* different packet framing.

Other hard-won facts:

- **The E80's STM32 firmware hardcodes sync word `0x2DD4D4B2`** and ignores the
  value in `CFG`. Peers must match it (`fips-lr2021ctl --sync-word 2dd4d4b2`).
- **IRQ DIO differs per carrier**: E80 = DIO8, NiceRF carrier = DIO9.
- **The IRQ status register reads back 0 on the NiceRF chip** — poll the DIO pin
  instead. The carrier's own driver does exactly this.
- **Bitrate code tables differ**: 650 kbps is `0x04` in the E80 driver, `0x03` in
  the NiceRF driver. At 2600 both agree on `0x00`.
- **TCXO modules need `SET_STANDBY_XOSC` (0x0128)**, not RC standby — otherwise
  the chip never clocks and every SPI read returns zero.
- **The NiceRF carrier's ESP32 pins** are `SCLK=6 MISO=2 MOSI=7 NSS=10 RST=3
  BUSY=4 DIO1=5` (confirmed from its own build flags).

## Measurements and tests

- **Self-reception is the cheapest radio health check.** Configure one node,
  transmit, read `status`:
  - `tx=N, rx=N, timeouts=0` → TX and RX both work, no peer needed.
  - `timeouts>0` → the radio never reported TX completion.
- **`cfg` returning success proves nothing** once the version gate is removed. A
  zero `chip=` in `HELLO_ACK` means SPI reads are returning zeros.
- **`TX: seq=… rssi=OK` is not proof of transmission.** In
  `tracker/firmware/radio_test` that line prints whenever `send_packet()` returns
  `Ok`, which only means the SPI command was accepted.
- **A null result from an unverified receiver proves nothing.** Before blaming
  node A, confirm node B can receive anything at all.

## Embedded pitfalls

- **Large buffers on the main task stack cause boot loops.** A 2 KB frame buffer
  plus a 3.5 KB default stack on ESP-IDF produced a reboot loop that looked like
  a hardware fault. Move big buffers to `static` and raise the stack
  (`CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192`).
- ESP-IDF C++ needs `extern "C" void app_main(void)` or the link fails with
  `undefined reference to app_main`.
- C++ designated initializers must follow struct declaration order, or use
  `= {}` plus assignment.

## Regulatory

- **The bench is in the EU.** Use `eu868` or `eu2400` only — never `us915`.
- 868.0–868.6 MHz has a **1% duty cycle**, so sustained testing belongs on
  `eu2400` (2440 MHz, FLRC-2600).
- At 868 the FLRC rate must be 650 kbps or lower: FLRC-2600 needs ~2.6 MHz and
  the 868.0–868.6 sub-band is only 600 kHz.

## Open problems

1. **No frame has ever crossed between two nodes.** Both nodes transmit and
   self-receive; neither hears the other. Framing is now copied verbatim from the
   vendor, so the remaining suspects are absolute frequency / band-variant
   differences. This needs an SDR or a third receiver, not another parameter.
2. **The ESP32 bridge radio returns zeros on both NiceRF carriers** despite
   correct pins and a proven driver. Hardware-side (module power or bus), needs a
   meter.
3. **FIPS peer addressing over `lr2021`** (peer address = 4-byte link id) has
   never been exercised.
