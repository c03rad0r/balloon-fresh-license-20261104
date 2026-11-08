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
| S3 `34:85` | firmware 0.4.10, LR2021 `chip=0x1801`, padded full-size TX | retain as reference |
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
- [x] S3 firmware behavior/version remains 0.4.10.
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
