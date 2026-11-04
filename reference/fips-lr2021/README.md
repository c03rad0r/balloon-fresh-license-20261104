# FIPS over LR2021 / FLRC — reference implementation

**Status:** host-tested end-to-end through two virtual bridges; one E80 STM32 bridge verified on hardware; two-node RF pending.  
**PR:** https://github.com/felixfelix-bot/balloon-fresh/pull/395
**Purpose:** keep the working LR2021 transport, bridge firmware, band configs and
event runbook in one place, separate from the flight firmware.

This tree is a reference implementation, not a flight integration. The FIPS-side
code lives on a fork; this directory pins it, vendors the diff, and carries the
RP2040 bridge firmware, configs and test scripts.

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

Two bridge targets are supported:

- **E80 STM32** (`firmware/e80-stm32-bench` bridge mode): the actual event
  hardware. Build/flash with `scripts/build-e80-bridge.sh` and
  `scripts/flash-e80-bridge.sh`; enter bridge mode with
  `fips-lr2021ctl bridge`. See `docs/E80-STM32-BRIDGE.md`.
- **RP2040 + E80** (`firmware/rp2040-bridge`): the reference SPI-bypass target.

One E80 STM32 board was flashed and verified on 2026-11-02 (HELLO/CFG/STATUS).
The second board is blocked on its SWD probe; see `docs/RESULTS.md`.

1. Flash the bridge on both boards (see `docs/HARDWARE.md`).
2. Connect both boards by USB.
3. Configure both ends:

```bash
# RP2040: /dev/ttyACM*
fips-lr2021ctl --serial /dev/ttyACM0 cfg --band us915
fips-lr2021ctl --serial /dev/ttyACM1 cfg --band us915

# E80 STM32: /dev/ttyUSB*, 115200, once per reset
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 bridge
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 cfg --band us915

fips-lr2021ctl --serial /dev/ttyACM0 status
fips-lr2021ctl --serial /dev/ttyACM1 status
```

4. Start FIPS on both machines with the `transports.lr2021` block from
   [`fips/configs/us915.yaml`](fips/configs/us915.yaml).
5. Run `ping6` between the FIPS addresses, then `iperf3 -u`.

The full procedure is in [`docs/DEMO-RUNBOOK.md`](docs/DEMO-RUNBOOK.md).

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

Run it with `tests/host/run_mock_e2e.sh`. Hardware evidence is **not claimed
yet**. The current x280 host is unreachable;
the hardware gate and exact commands are in
[`docs/RESULTS.md`](docs/RESULTS.md).

## Layout

| Path | What |
|---|---|
| `PLAN.md` | full plan and checklist |
| `ARCHITECTURE.md` | design and data path |
| `fips/` | fork pin, vendored diff, FIPS configs |
| `firmware/rp2040-bridge/` | RP2040 + E80 bridge firmware |
| `scripts/` | bootstrap, sync, build, flash, demo |
| `tests/hardware/` | PER, ping, relay and soak scripts |
| `docs/` | protocol, bands, hardware, runbook, results, bring-up findings |
| `docs/BOARD-INVENTORY.md` | every bench LR2021 board: USB IDs, wiring, firmware state |

## Known limitations

- The RP2040 bridge uses fixed 255-byte packets in this first cut; variable
  length is a follow-up after hardware validates the fixed path.
- 2.4 GHz needs the HF path verified on the actual E80 module; sub-GHz is the
  default.
- The relay mode is single-relay only in this cut.
- RP2040 flashing is BOOTSEL/picotool; pre-flash before travel. The ESP32
  porting guide is in `docs/PORTING-ESP32.md`.
