# FIPS over LR2021 / FLRC — reference implementation

**Status:** E80↔ESP32-S3 SPI bypass, two-way RF payload delivery and FIPS peer authentication verified on hardware; IPv6 ping and SSH remain open validation gates.

**Latest hardware guide:** [`docs/E80-ESP32-S3-FIPS-ONBOARDING.md`](docs/E80-ESP32-S3-FIPS-ONBOARDING.md)

**Merge:** https://github.com/felixfelix-bot/balloon-fresh/pull/475
**Purpose:** keep the working LR2021 transport, bridge firmware, band configs and
event runbook in one place, separate from the flight firmware.

This tree is a reference implementation, not a flight integration. The FIPS-side
code lives on a fork; this directory pins it, vendors the diff, and carries the
RP2040 bridge firmware, configs and test scripts.

## Start here

- **Building the two-radio E80 + ESP32-S3 adapter?** Start with
  [`docs/E80-ESP32-S3-FIPS-ONBOARDING.md`](docs/E80-ESP32-S3-FIPS-ONBOARDING.md)
  for exact soldering, reset-jumper, flashing, FIPS setup and measured results.
- **Planning the IPv6/data-plane fix?** `docs/IPV6-DATA-PLANE-PLAN.md` contains
  the failure analysis, the 100-frame acceptance gate, and the deferred
  Wirehair/FEC evaluation.
- **Repairing additional radio endpoints?** `docs/CARRIER-RECOVERY-PLAN.md` keeps
  the C3/Pico/native recovery steps, measured bidirectional C3 proof and the
  half-duplex CSMA/CA implementation checklist.
- **No physical access?** `docs/FLASHING-WITHOUT-BUTTONS.md` — both ESP32 and
  RP2040 can be reflashed over USB with no button press.
- **Picking up this work?** `docs/LEARNINGS.md` first, then `docs/OTA-PROOF-PLAN.md`.

**Bench radio profiles are EU-only (`eu868` or `eu2400`), never `us915`.**

## What it does

```
Laptop A: FIPS  <->  USB CDC  <->  RP2040 + E80/LR2021  <->  FLRC  <->  RP2040 + E80/LR2021  <->  USB CDC  <->  Laptop B: FIPS
```

- FIPS sees a normal transport named `lr2021`.
- The host fragments each FIPS frame into 255-byte radio packets.
- The bridge is a raw packet pipe: it does not parse FIPS or hold keys.
- The receiver reassembles, ACKs and delivers one complete FIPS frame.
- A third bridge can run in relay mode for the event bent-pipe test.

## Fork pin

All FIPS changes are on **`c03rad0r/fips`**, branch `balloon-lr2021`.
No PR, issue or push is made against `jmcorgan/fips`.

The exact commit and upstream base are in [`fips/fips-pin.txt`](fips/fips-pin.txt).
The complete diff is vendored at
[`fips/patches/0001-lr2021-transport.patch`](fips/patches/0001-lr2021-transport.patch).

## Quick start (host tests, no hardware)

```bash
cd reference/fips-lr2021
make bootstrap          # clone c03rad0r/fips at the pinned commit
make host-test          # fork unit/config tests
make mock-e2e           # two virtual bridges, 20/20 delivered
```

Or manually:

```bash
./scripts/bootstrap-fips.sh
cd "$FIPS_DIR"
cargo test -p fips-lr2021
cargo build --release -p fips-lr2021 --bins
```

## Quick start (two radios)

For the validated E80 SPI-bypass design, use **two E80 + ESP32-S3 adapters** and
follow [`docs/E80-ESP32-S3-FIPS-ONBOARDING.md`](docs/E80-ESP32-S3-FIPS-ONBOARDING.md).
It includes the required STM32 reset jumper, J2 pin map, build/flash commands,
per-board RF checks and a runnable two-namespace FIPS configuration.

Measured on `archipelago` on 2026-11-07:

- real LR2021 chip version `0x1801` through the S3 SPI bypass;
- first S3 → native-E80 radio frames, 20 valid at about −49 dBm;
- 20 full-size native-E80 → S3 frames with zero chip-CRC errors;
- five valid 64-byte payloads delivered into the link layer in each direction;
- Noise-authenticated FIPS peers in two isolated namespaces, both connected.

IPv6 ping and SSH are not yet passing. Measure those as separate gates; never
infer them from `HELLO_ACK`, a self-reception count or one-way RF reception.

The alternative RP2040 and native E80 STM32 bridge documents remain below as
hardware-specific notes. Their older US-band examples are **not** instructions
for this bench.

## Bands

| Profile | Frequency | FLRC | Power | Use |
|---|---:|---:|---:|---|
| `eu868` | 868.1 MHz | 650 kbps | +14 dBm | EU SRD, 1% duty cycle |
| `eu868-high` | 869.525 MHz | 650 kbps | +14 dBm | EU 869.4–869.65, 10% duty cycle |
| `us915` | 915.0 MHz | 1300 kbps | +22 dBm | US event target |
| `us915-robust` | 915.0 MHz | 650 kbps | +22 dBm | Narrower US fallback |
| `eu2400` | 2440 MHz | 2600 kbps | +12 dBm | EU 2.4 GHz |
| `us2400` | 2440 MHz | 2600 kbps | +12 dBm | US 2.4 GHz |

These are starting points, not regulatory certification. See
[`docs/BANDS-AND-REGULATORY.md`](docs/BANDS-AND-REGULATORY.md).

## Current evidence

Host tests in the fork:

- frame encode/decode and CRC,
- fragmentation and reassembly,
- loss, reorder, duplicate and timeout,
- ACK/NACK retransmission,
- bridge protocol split/coalesced frames and CRC recovery,
- config parsing for `transports.lr2021`.

End-to-end host check through two virtual bridges:

```text
per: sent=20 delivered=20 loss=0.0% elapsed=0.01s avg_rssi=-40.0 dBm
mock end-to-end: PASS
```

Run it with `tests/host/run_mock_e2e.sh`. Hardware evidence and reproduction
commands are in [`docs/E80-ESP32-S3-FIPS-ONBOARDING.md`](docs/E80-ESP32-S3-FIPS-ONBOARDING.md);
virtual end-to-end success is not a substitute for RF verification.

## Layout

| Path | What |
|---|---|
| `PLAN.md` | full plan and checklist |
| `ARCHITECTURE.md` | design and data path |
| `fips/` | fork pin, vendored diff, FIPS configs |
| `firmware/rp2040-bridge/` | RP2040 + E80 bridge firmware |
| `firmware/esp32-bridge/` | ESP32-S3 + E80 SPI-bypass firmware |
| `docs/E80-ESP32-S3-FIPS-ONBOARDING.md` | end-to-end soldering, flashing, RF and FIPS guide |
| `scripts/` | bootstrap, sync, build, flash, demo |
| `tests/hardware/` | PER, ping, relay and soak scripts |
| `docs/` | protocol, bands, hardware, runbook, results, bring-up findings |
| `docs/BOARD-INVENTORY.md` | every bench LR2021 board: USB IDs, wiring, firmware state |
| `docs/FLASHING-WITHOUT-BUTTONS.md` | **flash ESP32 and RP2040 boards over USB, no button press** |
| `docs/LEARNINGS.md` | every hard-won finding, so future sessions don't rediscover them |
| `docs/OTA-PROOF-PLAN.md` | staged plan to prove an over-the-air frame |
| `docs/IPV6-DATA-PLANE-PLAN.md` | IPv6 failure analysis, link acceptance gate and deferred Wirehair/FEC plan |
| `docs/CARRIER-RECOVERY-PLAN.md` | Other radio endpoint recovery, C3 DIO9 proof and half-duplex CSMA/CA checklist |
| `tests/hardware/http-speed.sh` | FIPS-namespace HTTP goodput meter with a mandatory 0%-loss ping gate |
| `tests/hardware/per.sh` | EU-868, 128-byte reciprocal PER/echo qualification |

## Known limitations

- The RP2040 bridge uses fixed 255-byte packets in this first cut; variable
  length is a follow-up after hardware validates the fixed path.
- 2.4 GHz needs the HF path verified on the actual E80 module; sub-GHz is the
  default.
- The relay mode is single-relay only in this cut.
- RP2040 can be flashed remotely using the 1200-baud touch; ESP32-C3/S3 use
  esptool `usb_reset`. See `docs/FLASHING-WITHOUT-BUTTONS.md` before pressing
  BOOTSEL or BOOT manually.
- E80↔ESP32-S3 delivery and FIPS peers are proven; larger payloads, IPv6 ping
  and SSH are still open, and are tracked in the onboarding guide.
