# Results

**Status: measured hardware acceptance passed on 2026-11-10 at host revision
`c03rad0r/fips@8155e5ff`.** Earlier results below are retained as history.

## Verified FIPS data-plane acceptance — 2026-11-10

Configuration: S3 `0.4.22` and C3 `0.5.12`, EU-868 FLRC-650, 128-byte radio
packets, 14 dBm, minimal link/session MMP, 20 ms fragment pacing, 300 ms ACK
backstop and bounded asynchronous one-frame scheduling. Firmware and host code
versions are separated in `PING-RELIABILITY-PLAN.md`.

| Gate | Measured result | Raw evidence on `archipelago` |
|---|---|---|
| Authenticated sessions | Initiator and responder XK sessions established | `session-evidence.log` |
| Bidirectional IPv6 | 50/50 replies each way, 0% loss | `ping-gate-async.log` |
| Post-rekey IPv6 | Real link/FSP rekey during 1 MiB run 3; then 50/50 each way, 0% loss | `rekey-evidence.log`, `ping-gate-post-rekey.log` |
| HTTP 128 KiB | Three exact-length HTTP 200 runs; 147.019/167.250/138.060 s; mean 0.0070 Mb/s | `http-128k-async-results.log` |
| HTTP 1 MiB | Three exact-length HTTP 200 runs; 1275.047/1272.223/1313.169 s; mean 0.0065 Mb/s | `http-1m-async-results.log` |
| SSH over FIPS | Public-key remote `RADIO_SSH_OK`, exit 0; reusable `ssh-smoke.sh` passed and removed credentials | `ssh-smoke.out`, `ssh-smoke-client.log`, `ssh-smoke-sshd.log` |

Raw evidence archive: `/home/archipelago/fips-results/2026-11-10/` (includes
`README.md`, non-secret configs and `SHA256SUMS`). No private FIPS or SSH keys
were archived. The deployed host binary SHA-256 matched the local rebuild:
`1ee7bda54116e80773e030c619f66b857ff78aad762706b5fc88e9ad50b18112`.

Host tests: **25/25** FIPS LR2021 link tests, **4/4** native transport tests,
**39/39** tracker driver tests. The optional MCP/ContextVM WAN test was not run:
no registered MCP speed-test tool or isolated WAN route was present. Wirehair,
production TDMA and MTU increases remain deferred.

## EU 2.4 GHz / 511-byte experiment — partial, not accepted

Measured 2026-11-11/12 on the same S3 `34:85` and NiceRF C3 `B0:A6` pair.
This work is documented but was **not accepted into the default runtime
profile**. Full handover: [`HANDOVER-2026-11-12.md`](HANDOVER-2026-11-12.md).

| Gate | Result |
|---|---|
| HF carrier control, 128-byte packets | 20/20 both directions, zero link errors |
| 511-byte smoke, CR 3/4, after FIFO/read fixes | 20/20 both directions, zero link errors |
| 511-byte strict 100, CR 3/4 | 100/100 unique each direction, but 1 and 6 host link CRC/framing errors |
| 511-byte strict 100, CR-none | 100/100 with 12 errors one way; 99/100 with 13 errors the other |
| FIPS XK / IPv6 / HTTP / SSH at 2.4 GHz / 511 | **not run — strict link gate did not pass** |
| Maximum application goodput | **unknown / not claimed** |

Root causes/fixes established during the experiment:

- The bridge RX path was limited to 255 bytes; the 16-bit FLRC payload length
  was also narrowed in the driver/config structs.
- The four extended-FIFO `WriteRegMem32` commands were malformed: a 4-byte
  address was sent where three bytes are required. Corrected frames are tested
  in `test_extended_fifo_commands_match_datasheet`.
- A 511-byte RX FIFO read in one SPI transaction still produced corrupt later
  payloads. Bounded 128-byte RX reads fixed delivery in the accepted smoke runs.
- The CR-none profile increased observed link errors; it remains opt-in via
  `-DLR2021_FLRC_CR_NONE=ON`. The default remains CR 3/4.
- The raw `2.6 Mbps` value is the FLRC air setting, not measured HTTP goodput.

Bench state at handover: experimental CR-none images S3 `0.4.29` / C3 `0.5.19`
remain flashed; locks are released and FIPS test daemons are stopped. Source
HEAD default is S3 `0.4.30` / C3 `0.5.20` and was not flashed.

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
