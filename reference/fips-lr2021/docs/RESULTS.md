# Results

**Status: hardware pending.** Do not fill this in from expectations.

## Host tests

Run:

```bash
cd <fips-fork>
cargo test -p fips-lr2021
cargo check -p fips-mesh
cargo test -p fips-mesh lr2021_transport_parses --lib
```

Record:

| Date | Commit | Command | Result |
|---|---|---|---|
| 2026-11-02 | `8aa2dd6` | `cargo test -p fips-lr2021` | 22 passed |
| 2026-11-02 | `8aa2dd6` | `cargo check -p fips-mesh` | clean |
| 2026-11-02 | `8aa2dd6` | config parse | pass |

## Hardware matrix

Fill only with measured numbers. Attach the raw CSV/log path.

| Date | Host A | Host B | Band | Bitrate | Distance | Payload | Sent | RX | PER | RSSI | SNR | Notes |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-11-02 | mock PTY A | mock PTY B | us915 | 1300 | 0 m | 64 | 20 | 20 | 0% | -40 | 10 | host link/CLI E2E |
| 2026-11-02 | x280 E80 STM32 | — | us915 | 1300 | 0 m | — | — | — | — | — | — | HELLO/CFG/STATUS verified; RF peer blocked (second SWD dead) |

## FIPS checks

| Date | Band | Handshake | Ping | iperf3 UDP | Relay? | Notes |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## Soak

| Date | Band | Duration | Resets | Drops | Result |
|---|---|---:|---:|---:|---|
|  |  |  |  |  |  |

## Hardware bridge protocol

2026-11-02, `/dev/ttyUSB6`, probe `203584200D2D0D42`:

```text
OK BRIDGE 115200
protocol=1 firmware=0.1.0 chip=0x1801 capabilities=0x0007
configured band=us915 freq=915000000 Hz flrc=1300 kbps power=22 dBm payload=255B relay=false
pong
tx=0 rx=0 crc=0 drops=0 timeouts=0 resets=0
```

Blocked: second E80 SWD probe `148757200D2D1425` cannot read IDR; CH340 ROM
bootloader path fails as documented. Two-node RF needs the second board
re-seated or power-cycled.

## Native FIPS transport start

2026-11-02, patched FIPS rev `1559063`, config `transports.lr2021` on
`/dev/ttyUSB6` at 115200:

```text
Transports initialized count=1
Node started: state=running transports=1
Transport stopped transport_id=transport:1 transport_type="lr2021"
```

This proves the native fork path opens the E80 bridge, applies CFG, enters the
node dataplane, and shuts down cleanly. No peer was present, so this is not a
handshake result.

## Known issues observed

- 

## ESP32-S3 probe verification (2026-11-03)

Replaced the Raspberry Pi Pico probe with an ESP32-S3 (serial `94A9902E9484`)
running `espressif/esp-usb-bridge` in CMSIS-DAP SWD mode.

Pin mapping verified with a multimeter by flashing slow toggles and measuring the
E80 header: GPIO10 -> pad C (SWCLK), GPIO8 -> pad D (SWDIO), pad V untouched.

Programming the E80 through the S3:

```text
Info : SWD DPIDR 0x1ba01477
Info : [stm32f1x.cpu] Cortex-M3 r1p1 processor detected
** Programming Started **
Info : device id = 0x20036410
Info : flash size = 64 KiB
** Programming Finished **
** Verified OK **
```

Bridge after the flash:

```text
OK BRIDGE 115200
protocol=1 firmware=0.1.0 chip=0x1801 capabilities=0x0007
configured band=us915 freq=915000000 Hz flrc=1300 kbps power=22 dBm payload=255B relay=false
pong
tx=0 rx=0 crc=0 drops=0 timeouts=0 resets=0
```

Two requirements, both needed: a **current** OpenOCD and **`adapter speed 5000`**.
Ubuntu's `openocd 0.12.0-1build2` does not connect to this bridge at any speed.

## Third E80: debug port unresponsive (2026-11-03)

A third E80 board answered neither SWD (5000..50 kHz) nor UART
(9600..921600 baud). The fault was localised to the board:

- S3 probe **drive** verified: GPIO10 -> C and GPIO8 -> D both toggle at 2 s.
- S3 probe **read** verified: grounding D produced `MIRROR GPIO8=0` then
  `MIRROR GPIO8=1`.
- Board rail `V` = 3.3 V.
- NRST normal: 3.3 V, pulled to 0 V only while the reset button is pressed.
- A 120-attempt reset-window connect loop, with the probe firmware confirmed
  present (`CMSIS-DAP: Interface ready`), never saw a `DPIDR`.

Conclusion: the STM32 on that board does not service its debug port. Not
recoverable over SWD; do not use it as an event node.

## E80 B: live MCU, SWD not yet connected (2026-11-03)

- UART works: `ID E80BENCH v1.2 fw=5fa7912`, and `BRIDGE` returns `ERR UNKNOWN`
  (that build predates bridge mode, so the board must be reflashed).
- S3 wiring verified on this board: GPIO10 -> C toggles, D sits at 3.3 V (target
  SWDIO pull-up).
- SWD connect fails at 5000 kHz with the probe confirmed present.
- Only 5000 kHz has been tried on this board. Lower speeds were tried on a
  different board (E80 C), not this one.

## Node A: RP2040 + LR2021 bridge verified (2026-11-04)

The dual-RP2040 GPS carrier was reflashed from its sweep firmware to the
reference bridge, using env `rp2040-bridge-gpsboard` (20 MHz SPI, `Serial1` log
compiled out because GP12/GP13 are the GPS UART on that carrier).

Host protocol verified at `/dev/ttyACM2`, Pico `E663B035977F242D`:

```text
protocol=1 firmware=0.1.0 chip=0x1801 capabilities=0x0007

configured band=us915 freq=915000000 Hz flrc=1300 kbps power=22 dBm payload=255B relay=false

pong
tx=0 rx=0 crc=0 drops=0 timeouts=0 resets=0
```

That is HELLO_ACK, a matching CFG_ACK, and PONG+STAT. Node A is ready; it has not
yet exchanged a frame with a second node.
