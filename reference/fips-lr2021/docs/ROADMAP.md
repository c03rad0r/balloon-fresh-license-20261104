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

**Revised 2026-11-04: do not reimplement the radio.** A first cut of
`firmware/esp32-bridge` drove the radio from the E80 register driver and needed
four blind iterations, each uncovering a carrier quirk:

| Symptom | Actual cause |
|---|---|
| boot loop | 2 KB frame buffer on a 3.5 KB main-task stack |
| `chip=0x0000` | RC standby instead of `SET_STANDBY_XOSC` (TCXO module) |
| SPI read empty | manual GPIO CS + full duplex, instead of hardware CS + `SPI_DEVICE_HALFDUPLEX` |
| TX never completes | the IRQ status register **reads back 0** on this chip; only the DIO pin works |
| wrong rate | 650 kbps is `0x03` here, `0x04` in the E80 table |

Every one of those is already encoded in
**`tracker/firmware/components/lr2021_transport`**, whose `EspIdfLr2021Radio`
runs on this exact hardware. The bridge must **link that component** rather than
carry its own radio code. Keep only the host protocol on top:

```
USB-Serial/JTAG  ->  bridge protocol (A5 5A)  ->  EspIdfLr2021Radio  ->  LR2021
```

Inputs: proven driver in `tracker/firmware/components/lr2021_transport`,
protocol in `reference/fips-lr2021/firmware/rp2040-bridge`, framing in
`docs/BRIDGE-PROTOCOL.md`.

- [x] Bridge protocol over USB-Serial/JTAG (`firmware/esp32-bridge`)
- [x] `HELLO_ACK` / `PONG` / `STAT` answer on real hardware
- [x] Flashing without a button (`esptool --before usb_reset`)
- [x] **Replace the radio layer with `tracker/.../lr2021_transport`**
- [x] `chip` reports a non-zero version
- [x] TX completion measured through the IRQ status register (`timeouts=0`)
- [x] `per`/`echo` against a native E80 (5/5 accepted payloads each way)
- [x] Full-size 255-byte RX control (`valid=20 crc=0`)
- [x] Document at `docs/E80-ESP32-S3-FIPS-ONBOARDING.md`

Lessons to keep: the main-task stack needs 8 KB; large buffers must be static;
do not gate E80 TX/RX solely on its DIO wire; parse and use FLRC FIFO/status
opcodes instead of their generic predecessors; and the bitrate/packet tables
are carrier-specific. Short-packet PHY CRC flags require host CRC verification,
not unconditional frame discard.

## Phase 4 — FIPS peer addressing

Peer addressing is explicit, textual and decimal. Config uses `addr: "1"` or
`"2"` corresponding to `local_id`; both sides had to be converted the same way.
Two isolated FIPS namespaces proved bidirectional peer authentication before
IPv6 testing was attempted.

- [x] Determine how a peer transport address is encoded and matched
- [x] Documented config example (`local_id` ↔ decimal-string peer address)
- [x] Handshake over `lr2021` (authenticated, connected peers in both namespaces)
- [ ] `ping6` — latest test was 0/3 in each direction
- [ ] TCP (`iperf3 -t`) and interactive SSH
- [ ] Larger-payload plus fragmented-message validation
- [ ] Document MTU interaction: FIPS TUN 1280 vs link MTU 1400

## Phase 5a — half-duplex medium access control

The LR2021 radios have independent oscillators; host retries have independent
timebases, not a common wireless scheduler. Reduce collisions before increasing
symbol rate.

- [x] CSMA/CA guard: inspect preamble/sync/header RX events before TX
- [x] Drain completed RX before switching to TX
- [x] Bounded 20 ms waiting plus randomized **8–16 ms** TX guard
  (bring-up tuning; reduce only after stability is measured)
- [x] Independent host-side retry epochs on S3 and C3
- [x] User-visible CCA counters (deferrals, capped waits, last guard)
- [ ] Before/after comparison at 128-byte payload on both directions
- [ ] Established FIPS session and ping on both directions
- [ ] Optional later scheduled slots only if CSMA/CA cannot stabilize the link
- [x] Optional 40 ms link-ID slot experiment implemented but **disabled** after
      it underperformed CSMA on delivery (see carrier-recovery plan)
- [ ] Rerun TDMA only after RX handling/background traffic is characterized

Implementation details and live checklist:
`docs/CARRIER-RECOVERY-PLAN.md` (Phase 2b) and
`docs/PING-RELIABILITY-PLAN.md` (active reliability gates).

## Phase 5 — throughput

Measure, do not estimate.

- [ ] E80 @115200 (expected ~90 kbps, serial-bound)
- [ ] E80 @2 Mbaud (expected ~1.6 Mbps; firmware + host baud change)
- [ ] SPI nodes at FLRC-1300
- [ ] SPI nodes at FLRC-2600 (2.4 GHz)
- [ ] Real numbers replace the estimates in `DUAL-NODE-BRINGUP-PLAN.md`

## Phase 6 — optional link FEC, including Wirehair (later)

Do this only after the baseline link is stable enough that residual loss, not
framing or session setup, is the limiting factor. Detailed gates live in
`docs/IPV6-DATA-PLANE-PLAN.md`.

- [ ] Measure ARQ-only loss/latency at 0, 1, 5, 10 and 20 percent erasure.
- [ ] Prototype a hybrid ARQ + FEC data path for multi-packet/bulk messages.
- [ ] Never FEC control frames, ACKs or the FIPS session handshake.
- [ ] Give every coded symbol an outer ID and CRC before decoding.
- [ ] Evaluate `catid/wirehair` (canonical C++), wrapped from the Rust host link.
- [ ] Compare alternatives such as Reed–Solomon or RaptorQ for small blocks.
- [ ] Reject FEC if collision rate, airtime or interactive latency worsens.
- [ ] Record duty-cycle and memory/CPU costs before considering embedded use.

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
