# Recovering the other LR2021 endpoints

Written 2026-11-08. Tracks the repair of additional bench radios while the
ESP32-S3/E80 bypass remains the known-good reference.

## Objective

Produce at least one independent, measured second node among the connected
C3/Pico/E80 boards so the 100-frame link qualification in
`docs/IPV6-DATA-PLANE-PLAN.md` can run.

## Current endpoint truth

| Endpoint | Good evidence | Fault |
|---|---|---|
| S3 `34:85` | firmware 0.4.21, LR2021 `chip=0x1801`, padded full-size TX | retain as reference |
| C3 `B0:A6` | firmware 0.5.11, LR2021 `chip=0x1801`, DIO9 TX/RX proven | qualified independent peer |
| C3 `B0:A6` | USB protocol and LR2021 version work | E80-focused firmware is wrong for this carrier; RX = 0, TX times out |
| C3 `88:56` | bridge protocol works | old 0.3.0 firmware, `chip=0x0000` |
| C3 `70:AF` | USB/ROM responds | not running bridge firmware, no RF evidence collected |
| Pico | USB bridge and `chip=0x1801` | E80-path build does not match the carrier; no useful RX result |
| Native E80 STM32 | was once a valid bridge | now silent; must be recovered before further RF work |

A USB count is not an RF count. Every candidate must prove independent RX before
being promoted to a peer.

## Carrier facts to retain

- NiceRF C3 pins: SCK=6, MISO=2, MOSI=7, NSS=10, RESET=3, BUSY=4, IRQ/DIO1=5.
- **NiceRF IRQ function is DIO9**, whereas E80 uses DIO8.
- NiceRF C3 may have an unusable IRQ status register; its established driver
  polls the DIO line instead.
- Bare NiceRF modules have an optional 2.4 GHz antenna port (pin 10) in
  addition to the sub-GHz port (pin 9). Do not infer silicon band capability
  from an optional antenna that is not fitted; carrier recovery uses 868 MHz.
- The shared E80 path selects `REG_MODE_DCDC`. Semtech's documentation warns
  that DCDC can reduce sub-GHz sensitivity and provides a conditional
  workaround. That difference is a measurement candidate, not another blind
  parameter to change.

## Phase 1 — dedicated NiceRF C3 profile

Add a target-selected C3 radio-init variant under the same bridge host
protocol. Keep the validated E80 air format:

- frequency as 4-byte big-endian Hz;
- FLRC mod params `04 17` for 650 kbps;
- packet params `1E 7D 00 FF`;
- sync `2dd4d4b2`;
- fixed 255-byte packets with explicit zero padding on TX.

Do not change any of those air-format values on both ends independently. The
C3 profile owns only reset/TCXO/PA/IRQ behavior and the possibility to override
carrier-specific values in one controlled experiment.

Checklist:

- [x] Write this plan and checklist.
- [x] Add `LR2021_NICERF_C3` selection for `esp32c3`, keeping `esp32s3` E80
      behavior unchanged.
- [x] DIO9 function and mask on C3; pin-gated TX/RX instead of register-only IRQ
      polling on that carrier.
- [x] Carrier LF/HF RX path and PA selection without blindly applying E80 TCXO
      settings to the bare module.
- [x] Fixed-size padded TX shared with E80, with host tests still passing (39/39).
- [x] S3 firmware behavior/version remains 0.4.21.
- [x] Build C3 image, flash `B0:A6` remotely with `usb_reset`, record version 0.5.0.
- [x] Verify `HELLO chip=0x1801` and `CFG --band eu868` succeeds.
- [x] Measure TX completion: C3 `tx=12 timeouts=0` after DIO9 fix, previously timed out every burst.

### Blocking control for this phase

A successful config/version read is not enough. Accept only measured RX/TX
counters; no handshake claim is permitted on SPI health alone.

## Phase 2 — independent C3 ↔ S3 radio proof

Use full-size 255-byte packets at 868.1 MHz. Use `monitor` first, not FIPS or
self-reception as a substitute.

- [x] `B0:A6` receives at least 10 frames from S3 (40 full-size packets decoded, CRC=0).
- [x] S3 receives at least 10 frames from C3 (21 valid full-size packets at about −35 dBm, plus one garbage frame).
- [ ] If either direction fails, record FLRC valid/CRC/length counters and IRQ
      status to classify receiver silence vs demodulation failure.
- [ ] If CRCs fail but payloads are intact, keep host-CRC rejection as the
      integrity boundary.
- [ ] If counters stay zero, check RF hardware (antenna, module rail, RF path,
      power and a third receiver/SDR if available).
- [ ] Run `echo` and require 100/100 accepted full-size payloads in each
      direction.

If DIO9 still does not assert while the radio transmits, TX is not validated by
a printed `rssi=OK` or `CFG_ACK`. Inspect actual packet stats rather than
retreating to self-reception guesses.

## Phase 2b — half-duplex channel access (after working radios were proven)

The independent C3↔S3 link now works at 128-byte air packets. Controlled PER
measurements showed **100 accepted packets in each direction with zero host CRC
failures**, but simultaneous FIPS control flows still collide. A common
Crystal/TCXO is not a TDMA scheduler: per-frame sending uses host requests and
host retransmission timers, so two radios can overlap.

Implement best-effort **CSMA/CA before strict TDMA**:

### Results already measured before this guard

| Test | Result |
|---|---|
| C3→S3 at 128 bytes | 100/100 delivered, zero echo CRC failures |
| S3→C3 at 128 bytes and gentler pacing | 100/100 delivered, zero echo CRC failures |
| 160- and 192-byte air packets | bad host CRC; payload corruption persists beyond 128 bytes |
| FMP peer initiation on one static initiator | inbound and outbound peers both connect |
| End-to-end XK session | established on both ends after waiting |
| IPv6 A→B | one packet reached after retries; reverse later achieved 4/5 with large RTT variance |
| SSH | listener configured on FIPS address, but login has not finished reliably |

Do not confuse stable full-size packet transmission with loss-free MAC. Repeated
simultaneous FMP/FSP control messages still overlap, hence guard and guard-time
measurements are required.

- [x] Do not use `cfg`/`rssi=OK` or a self-packet as proof of interoperability.
- [x] Prove 128-byte bidirectional exchange before changing media access.
- [x] Keep one static initiator to avoid simultaneous initial handshake floods.
- [x] Read pre-amble/sync/header events before committing to TX.
- [x] Drain a completed RX before entering TX.
- [x] Add a bounded 20 ms idle wait, followed by **8–16 ms** randomized guard
      for bring-up; revisit latency only after collisions are measured.
- [x] Use independent seeds on S3/C3, not a shared absolute UTC clock.
- [x] Inspect progress bits with `GET_IRQ_STATUS` rather than adding them to the
      DIO mask. `0x004C0060` produced S3 TX timeouts, so preserve the proven
      completion-only mask `0x004C0000` and avoid optional-mask coupling.
- [x] Expose `cca deferral`, `cca capped` and `cca guard_us` as host-visible
      events rather than pretending there is always a free channel.
- [x] Compare PER runs before and after introducing CCA: 100/100 proof
      during radio qualification, then 20/20 current guarded round trips
      in each direction with no unexplained TX timeouts.
- [x] Check a static-initiator FIPS handshake forms without a retry storm.
- [x] Require an established session on both ends before ping (verified on
      2026-11-08).
- [x] Re-measure directional ping RTT: earlier CSMA-only runs reached
      **2/3 replies in both directions**; the final default-build check was
      **0/5 A→B and 3/5 B→A**, so this is not yet a passing gate.
- [x] Confirm the HTTP benchmark refuses invalid data: it rejected a 1/3-ping
      window with no speed result recorded.
- [ ] Prove stable repeated dual-direction ping without continuing session
      or packet-loss churn; current RTT is still variable and too high.
- [ ] Complete SSH over FIPS. Client reached `SSH2_MSG_SERVICE_ACCEPT` before
      remote closure, so listener and transport setup advanced, but login has
      not completed.
- [ ] Only consider fixed TDMA slots if carrier sense and jitter are insufficient.

A future fixed-slot design should use host-relative `esp_timer_get_time()`
slot origins and packet arrival times, not pretend the ESP32 and LR2021 crystals
or NTP wall clocks provide one shared RF timebase.

### Fixed-slot experiment result

An optional `BR_CFG_EXT` frame now carries `local_id` and the host Unix epoch;
hosts use it to assign 40 ms slots by `local_id & 1`. This is **disabled by
default** in firmware because it did not improve delivery on the bench:

- integration succeeded: `role=1/id=1` and `role=0/id=2`, sessions established;
- one successful ping reply arrived at **159 ms** RTT, confirming slot timing
  can remove most latency when a frame gets through;
- delivery was still poor: one direction 1/3, the reverse 0/3, versus a better
  2/3 in each direction with CSMA-only;
- bridge logs still show real `bad crc32`/`bad magic`, so fixed slots alone are
  not sufficient while RX handling and retry timing remain unverified.

Decision: keep `LR2021_ENABLE_TDMA=0` for the usable build. Treat TDMA as an
opt-in experiment until a run passes the 0%-loss ping gate. The optional
extension is backward-compatible: older bridges ignore frame kind 11 and retain
their previous behavior.

- [x] Implement optional link-ID/epoch slot extension.
- [x] Keep default build on the better-performing CSMA-only path.
- [ ] Retest TDMA with RX pumping and with all background control traffic
      characterized; only enable it if it beats CSMA on loss and latency.
- [ ] Never describe theoretical 40/80 ms slots as achieved latency: the
      measured successful RTT was 159 ms, while delivery remained incomplete.

## Phase 3 — clone only a proven C3 build

After C3 ↔ S3 passes Phase 2:

- [ ] Flash `88:56` with the same image.
- [ ] Verify its HELLO and RX/TX counters.
- [ ] Flash `70:AF`, which is currently not running a bridge.
- [ ] Verify its HELLO and RX/TX counters.
- [ ] Keep only boards that pass the independent 100-frame test as FIPS nodes.

No C3 hardware may be declared interchangeable until both directions pass.

## Phase 4 — recover the Pico

- [ ] Restore carrier-specific RP2040 reset/PA behavior rather than its current
      E80-path firmware.
- [ ] Keep DIO9 for this carrier.
- [ ] Rebuild and flash remotely via 1200-baud touch.
- [ ] Confirm S3 → Pico reception, then Pico → S3 reception.
- [ ] Leave it out of qualified tests until it passes both directions.

## Phase 5 — recover the native STM32 E80

This is blocked on physical connectivity, not more RF configuration.

- [ ] Physically power-cycle the board.
- [ ] Test CH340 `ID?`.
- [ ] If still silent, attach a probe and flash with SWD. CH340 ROM flashing has
      already failed on two hosts due the ordering/parity handshake.
- [ ] Prove `BRIDGE`, `HELLO`, `CFG`, `STATUS` again.
- [ ] Update its TX helper to zero-pad to configured 255-byte radio packets so it
      no longer reintroduces short-frame asymmetry with the S3.

## Phase 6 — return to FIPS

- [ ] Choose two independently validated endpoints (identical S3 adapters are
      preferred for the production design).
- [ ] Re-run 100 full-size packets each way with zero host CRC/magic drops.
- [ ] Start FIPS and wait for non-empty `show sessions` on both nodes.
- [ ] Test ping, then interactive SSH.
- [ ] Update `docs/IPV6-DATA-PLANE-PLAN.md` with the concrete result and metrics.

Wirehair remains a later optional evaluation in the roadmap, after this
baseline is stable. No new packet-coding complexity is introduced here.
