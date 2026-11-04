# Roadmap — one working node → full LR2021 transport matrix

Written 2026-11-04. Current state: **1 of 5 nodes usable** (the E80 driven by its
own STM32). Ordered so every phase produces something testable.

## Phase 0 — a working pair (today)

Flash the second E80's STM32 with the already-verified bridge image, using the Pico
debugprobe. No new firmware if it can be avoided.

**Why first:** separates "does FIPS work over LR2021" from "does this carrier's
radio work". Only the first matters for the transport, and the two have been
tangled.

- [x] Node A (E80 `fw=f89eca4`, USB path `4.1.3`): `BRIDGE`, `HELLO_ACK`, `CFG_ACK` at 915 MHz
- [ ] Pico debugprobe reaches `DPIDR` on the second E80 (`fw=5fa7912`, path `1.1`)
- [ ] Bridge firmware flashed and verified
- [ ] `BRIDGE` mode entered, `HELLO_ACK` + `CFG_ACK`
- [ ] `per`/`echo` across the pair: 20/20, 0% loss
- [ ] FIPS handshake between two hosts
- [ ] `ping6` succeeds
- [ ] `iperf3 -t` (TCP) moves bytes

**If it fails:** Phase 2 yields the same pair via the RP2040 node.

## Regulatory constraint (bind every test to this)

**The bench is in the EU. Use `eu868` or `eu2400` only — never `us915`.**

- `eu868` = 868.1 MHz, FLRC-650, +14 dBm, 1% duty cycle in 868.0–868.6 MHz.
  Keep bursts short; do not run continuous throughput sweeps on this band.
- `eu2400` = 2440 MHz, FLRC-2600, +12 dBm. Better suited to sustained testing.
- 915 MHz is a US DTS band and is not permitted here.

Several early bench runs used `us915` before this was flagged. They were brief and
low-duty, but every command example in these docs should be read as `eu868` or
`eu2400`.

## Phase 1 — validate every radio pair

- [ ] E80 ↔ E80
- [ ] E80 ↔ RP2040
- [ ] RP2040 ↔ RP2040
- [ ] ESP32 ↔ any (after Phase 3)
- [ ] Results recorded per pair in `docs/RESULTS.md`
- [ ] Unrun cells written `not run`
- [ ] 868/915 and 2.4 GHz kept in separate tables

**Exit:** a measured matrix of combinations.

## Phase 2 — fix the RP2040 carrier's radio

Already excluded: IRQ DIO 8 and 9, the IRQ line entirely (register polling), FRF
vs plain Hz, and 915 vs 2.4 GHz.

Approach: port the carrier's own init sequence from
`firmware/rp2040/src/dual_radio_gps_sweep*.cpp` into the bridge's `radioApply`,
keeping the host protocol.

- [x] Extract the carrier init sequence
- [x] Replace `radioApply` internals, keep the protocol (`E80_BRIDGE_CARRIER_INIT`)
- [x] `GET_VERSION` still reads
- [x] `timeouts` stops incrementing on a `per` run (was 20/20, now 0/20)
- [ ] A peer receives frames

Root cause of the silent TX: the carrier needs FLRC packet type `0x04` (not `0x05`),
`CALIB_FRONT_END` before `CALIBRATE 0x5F`, and the HF PA config on all bands.

Two builds are kept ready for an A/B on the frequency encoding, which is the next
suspect for the remaining 100% loss:

- `rp2040-bridge-gpsboard` — FRF encoding
- `rp2040-bridge-gpsboard-hz` — plain 4-byte Hz

## Phase 3 — the ESP-IDF bridge

Largest piece; unlocks three boards.

Inputs that exist: SPI/radio in `firmware/esp32-c3-flrc`, protocol in
`reference/fips-lr2021/firmware/rp2040-bridge`, framing in
`docs/BRIDGE-PROTOCOL.md`.

- [x] Port `bridge_protocol` + TX/RX loop to ESP-IDF (`firmware/esp32-bridge`)
- [x] USB-Serial/JTAG host link
- [x] Per-carrier settings: IRQ DIO, frequency encoding, init variant
- [x] Build for `esp32c3`
- [x] Build for `esp32s3`
- [ ] `fips-lr2021ctl hello` returns `HELLO_ACK` on an ESP32 board
- [ ] `per`/`echo` against an E80

## Phase 4 — FIPS peer addressing

The real integration gap: no discoverable peers, `auto_connect` false, peers must
be configured statically with the transport address equal to the 4-byte link id.
That path has never been exercised.

- [ ] Determine how a peer transport address is encoded and matched
- [ ] Documented config example (`local_id` ↔ peer address)
- [ ] Handshake over `lr2021`
- [ ] `ping6`
- [ ] TCP (`iperf3 -t`)
- [ ] Document MTU interaction: FIPS TUN 1280 vs link MTU 1400

## Phase 5 — throughput

Measure, do not estimate.

- [ ] E80 @115200 (expected ~90 kbps, serial-bound)
- [ ] E80 @2 Mbaud (expected ~1.6 Mbps; firmware + host baud change)
- [ ] SPI nodes at FLRC-1300
- [ ] SPI nodes at FLRC-2600 (2.4 GHz)
- [ ] Real numbers replace the estimates in `DUAL-NODE-BRINGUP-PLAN.md`

## Ordering rationale

Phase 0 first because it can finish in an hour and validates the whole stack on
known-good hardware. Phase 1 makes it reproducible. Phases 2–3 broaden hardware
support only after the transport is proven. Phase 4 is the real integration
question and should not start until two nodes are stable.

## Explicitly out of scope

- Relay / multi-hop scheduling
- Encryption beyond FIPS's own session layer
- Regulatory certification
- Running FIPS on the host MCU (microfips) instead of a laptop
