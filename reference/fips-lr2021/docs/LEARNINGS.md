# Learnings — LR2021 / FIPS bench, 2026-11-03 to 11-07

Consolidated so a future session does not rediscover any of this. Each item cost
real time; most cost an hour or more.

## Start here

| Need | Document |
|---|---|
| E80 + ESP32-S3 build, flash, RF and FIPS guide | `docs/E80-ESP32-S3-FIPS-ONBOARDING.md` |
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

## E80 SPI bypass findings on 2026-11-07

Read `docs/E80-ESP32-S3-FIPS-ONBOARDING.md` before repeating any of this work.

- **The E80 STM32 MUST be held in reset** while an ESP32-S3 drives J2. The user's
  soldered NRST-to-GND jumper changed a zero version read into a real radio;
  no meter-discovered wiring repair was necessary.
- `GET_VERSION` returns two status/dummy bytes before payload. Treating an
  entire four-byte read as firmware bytes produced the misleading `07 21 01 18`;
  the parsed version is **`01 18`**, hence `HELLO chip=0x1801`.
- Full-duplex SPI with dummy TX on reads works where the earlier half-duplex
  receive-only transfer was rejected. BUSY/RST/SCK/MOSI/MISO/NSS all worked.
- Poll the IRQ **status register** rather than depending on DIO8 being wired:
  TX timeouts went to 0 when the bridge stopped waiting solely for the DIO pin.
- FLRC TX FIFO framing is `0x0002 + payload` with **no inserted length byte**.
  RX FIFO is `0x0001 + payload` in one transaction with no dummies. Packet
  status uses `0x024B`; cumulative RX/CRC/length counters use `0x024A`.
- Short FLRC packets on this bench show hardware-CRC failures even when the
  payload is intact. Allow them into the FIPS link, whose CRC32 independently
  rejects real corruption. Full 255-byte frames are a clean control
  (`valid=20 crc=0` on one burst).
- First S3→native-E80 exchange: 20 valid frames near −49 dBm. Both directions
  later delivered 5/5 64-byte payloads through the host link layer.
- **Textual peer IDs matter.** `TransportAddr` strings are UTF-8; `addr: "2"`
  must produce decimal link ID 2, not ASCII byte 0x32. Reception constructs the
  same decimal string (`c03rad0r/fips@66b53835`).
- An `echo` helper listens on link ID **2** by default. Sending to peer ID 1
  while it runs is a host-addressing error, not an RF failure.
- Two namespaces established authenticated FIPS peers in **both** directions.
  IPv6 ping was nevertheless 0/3 each way, so transport readiness is still not
  claimed for SSH.
- Copying the STM32's 304 us ramp/STDBY_RC fallback, adding front-end calib,
  changing every TX packet length and enabling PRAM were tried individually;
  they regressed or did not fix this RF pair. The working E80 bypass build is
  firmware 0.4.10. Do not stack these unvalidated modifications again.
- **Short TX packets must be explicitly zero-padded.** With fixed-length FLRC,
  writing fewer bytes than the configured packet length left the tail undefined.
  The current build pads through `payload_length` (tests in
  `lr2021_transport/test`) and the receiver trims with the FIPS frame length.
  Qualification requires 100 full-size frames each way.

## Open problems

1. **Larger payloads, fragmentation, IPv6 ping and SSH still need validation.**
   The latest isolated two-node test authenticated both ways but ping was 0/3
   each way. Daemon logs distinguish `bad magic`, `bad crc32` and stale-session
   errors; use those measurements rather than changing RF settings blindly.
2. **The native STM32 reference E80 became silent.** USB re-enumeration did not
   bring it back; further native-reference comparisons require a physical power
   cycle. This does not block the already-documented S3 bypass build.
3. **NiceRF ESP32-C3 carriers are not an E80-equivalent shortcut.** One reads
   version 0x1801 after the driver correction, but TX/IRQ behavior differs.
   Do not substitute it for the validated E80 SPI-bypass adapter.
4. **Throughput and production hardening remain open:** RX IRQ status polling is
   intentional because DIO8 is not required on this adapter, and init retries
   are bounded at three.
