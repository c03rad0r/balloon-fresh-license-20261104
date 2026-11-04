# Dual-node bring-up plan — two LR2021 endpoints on FIPS

Written 2026-11-04. Goal: two independent LR2021 nodes that FIPS can talk over,
so the `lr2021` transport is exercised on real hardware end to end.

## Target topology

```
laptop A  <-> USB  <-> RP2040 + LR2021   ~~~ FLRC ~~~   LR2021 + STM32 <-> USB <-> laptop B
                        (node A)                          (node B, E80)
```

Both nodes speak the same host protocol (`A5 5A … CRC16`) defined in
`docs/BRIDGE-PROTOCOL.md`, so the host side — `fips-lr2021ctl`, `fips-lr2021d`,
and the native FIPS transport — is identical for both. Nothing on the host needs
to know which MCU is behind the radio.

## Node A — RP2040 + LR2021 ("old GPS board")

**What it is.** A carrier with two RP2040s, a GPS, and an LR2021. The enumerated
Pico (`E663B035977F242D`, `/dev/ttyACM2`) runs `multi_radio_sweep_gps_v3/v4` and
prints `NMEA_RMC:` lines.

**Why it is easy.** Its radio pins match the reference bridge exactly:

```
SCK=GP2  MOSI=GP3  MISO=GP4  CS=GP5  BUSY=GP6  IRQ=GP7  RST=GP8
```

which is the same map as `firmware/e80-bypass/common/e80_pinmap.h`.

**The one required change.** The reference bridge logs to `Serial1` on GP12/GP13,
and on this board those are the **GPS UART**. Driving GP12 into the GPS's RX and
reading GP13 would be wrong, so logging is compiled out for this board.

**Steps**

1. Patch `firmware/rp2040-bridge/src/main.cpp` to disable the `Serial1` log
   (behind a build flag so the E80 bypass build is unaffected).
2. Build the UF2 locally with PlatformIO.
3. Put the Pico in BOOTSEL (hold BOOTSEL, tap RESET) so it enumerates as
   `2e8a:0003` and exposes a mass-storage device.
4. Copy the UF2, let it reboot.
5. Verify: `fips-lr2021ctl --serial /dev/ttyACM2 hello` → `HELLO_ACK`.

**Status 2026-11-04: done.** Reflashed and verified (HELLO/CFG/STATUS). The
enumerated Pico did turn out to be the one wired to the LR2021.

**Risks (historical).** The second RP2040 is not enumerated, so we cannot tell from USB alone
which one is wired to the LR2021. `multi_radio_sweep_gps` implies one device does
GPS + radio, so the enumerated Pico is the likely candidate — but this is the
first thing to falsify. If `hello` never answers after flashing, the radio is on
the other RP2040.

## Node B — E80 (fourth board)

**Current state.** The S3 probe (`94A9902E9484`) is soldered to this board and
correctly enumerates as CMSIS-DAP FW 2.1.2, but SWD returns
`cannot read IDR`, and the board's UART is silent.

**Why this is suspicious.** It is the third board in a row to fail SWD with a
probe that is proven good (drive and read both verified by meter). Three dead
debug ports is implausible; the common factor is the harness, which has been cut,
twisted, re-soldered and moved across four boards.

**Steps**

1. Flash the GPIO10-only toggle test to the S3 and measure `C` and `D` on this
   board.
   - `C` toggles → harness fine, board fault.
   - `C` flat → harness fault; re-make the joints.
2. If the harness is good, measure `V` (~3.3 V) and `D` (~3.3 V, target pull-up).
3. Once SWD connects, `openocd … -c "adapter speed 5000" … program e80_bench
   verify reset exit`.
4. `fips-lr2021ctl --serial /dev/ttyUSBx --baud 115200 bridge`, then
   `hello` / `cfg` / `status`.

**Fallback.** If the board's SWD is genuinely dead, drive its LR2021 by SPI
bypass instead (see `docs/E80-STM32-BRIDGE.md` and
`E80-SPI-BYPASS-WIRING.md`), holding the STM32 in reset.

## Known asymmetry

The E80's STM32 bridge talks to the host at **115200**, about 90 kbps. The RP2040
speaks USB CDC at megabytes per second. A cross-node test will therefore **work
functionally** but be capped by the E80 side. This plan validates the transport;
it does not measure throughput. A throughput number needs SPI hosts on both ends.

## Order of work

1. Node A: patch, build, flash, `hello`.
2. Node B: toggle-test the harness, then flash.
3. Configure both: same `band`, `sync_word`, `radio_payload`, `mtu`; different
   `local_id`.
4. `echo` on one node, `per` on the other.
5. FIPS `ping6`, then `iperf3 -u` as a smoke test.
6. Record results in `docs/RESULTS.md`.

## Success criteria

- Both nodes answer `HELLO_ACK` and `CFG_ACK`.
- 20/20 frames delivered across the radio with 0% loss at bench distance.
- FIPS handshake completes between two hosts.

## Current situation (2026-11-04)

| Component | State |
|---|---|
| Node A — RP2040 + LR2021 (`/dev/ttyACM2`) | **verified**: HELLO/CFG/STATUS, 915 MHz FLRC-1300, +22 dBm |
| Node B — E80 STM32 (`/dev/ttyUSB2`) | `fw=f89eca4` present, in bench mode; needs `BRIDGE` |
| Over-the-air frame | **not yet sent** |
| Fourth E80 + S3 probe | SWD still `cannot read IDR`; harness suspected |

Node A's firmware is the reference bridge built with
`-e rp2040-bridge-gpsboard`: 20 MHz SPI, `Serial1` log compiled out because
GP12/GP13 are the GPS UART on that carrier.

## Throughput expectations (important)

| Path | Host link | Practical ceiling | Bound by |
|---|---|---|---|
| E80 STM32 @ 115200 (current node B) | UART 115200 | ~92 kbps | serial |
| E80 STM32 @ 2 Mbaud (firmware change) | UART 2 Mbaud | ~1.6 Mbps | radio @ 915 |
| RP2040 + SPI bypass | USB CDC + SPI 20 MHz | ~0.6–0.9 Mbps @ FLRC-1300 | radio |
| ESP32 + SPI bypass, 2.4 GHz | USB CDC + SPI 20 MHz | ~1.3–1.8 Mbps @ FLRC-2600 | radio |

The radio side is **already SPI on the E80** — the STM32 drives the LR2021 over
SPI. The 115200 UART between the STM32 and the CH340 is the only bottleneck, and
it sits on the host side of the bridge.

Consequences:

- The current pair proves the transport, not its throughput.
- FIPS handshake, `ping6` and low-rate UDP fit inside 92 kbps.
- TCP is possible but slow (double retransmission: FIPS session layer + link ARQ
  + TCP), and video is not viable at this rate.

## Immediate steps

1. Put node B into bridge mode: `fips-lr2021ctl --serial /dev/ttyUSB2 --baud 115200 bridge`.
2. `hello` → `HELLO_ACK`; `cfg --band us915` must match node A.
3. Cross-node link test: `echo` on one, `per` on the other.
4. Then two FIPS instances (namespaces or two hosts) for `ping6`.

## Later

- Raise the E80 bridge to 2 Mbaud (biggest throughput win without rewiring).
- Or move node B to SPI bypass so the STM32 stops mattering.
