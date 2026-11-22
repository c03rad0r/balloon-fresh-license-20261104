# Seeed LR2021 EVK — direct-FLRC bridge and half-duplex FIPS implementation report

**Date:** 2026-11-22
**Hardware:** two official Seeed/Semtech LR2021 EVKs on their stock USB-C path
**Firmware:** Seeed nRF54L15 bridge, direct-FLRC build, 87,780 bytes,
SHA256 `526ba7f571fe0cb505c1354a8c2320683ba5d506dfff3bf31c90b8e42e40318a`
**FIPS revision:** `c03rad0r/fips` branch `seeed-halfduplex`,
`78b76d45c71f443099ff7bc5f89ecab4260495d5`
**Bridge commit:** `b2267e546f60e8b01e68d7c3c1347994d437bfd8`

This document records the complete implementation: what was built, what was
measured, what failed, why decisions were taken, and how to reproduce each
result. It deliberately separates measured evidence from expectations.

---

## 1. Scope

The goal was to turn the two EVKs into a usable FIPS transport over raw LR2021
FLRC packets, preserving the existing host bridge protocol and the FIPS stack,
without soldering or replacing the stock USB path.

The work covered:

1. a real LR2021 FLRC backend behind the existing host protocol;
2. two-node RF validation in both directions and a long soak;
3. reset/crash diagnosis and a firmware stability fix;
4. a half-duplex link layer that makes FIPS usable over the radios;
5. measured `ping6`, iperf3 UDP, raw TCP, SSH and a soak;
6. documentation, reproducible configs and log hashes.

It did **not** produce a usable `iperf3` TCP bulk path, and it does not claim
2.6 Mbit/s application throughput.

---

## 2. Hardware and final bench state

| Item | Station A | Station B |
|---|---|---|
| Probe | `7CDB5271` | `A8022EF0` |
| Host UART | `/dev/ttyACM0` | `/dev/ttyACM1` |
| Bridge firmware | 0.2.0, protocol 1 | same |
| LR2021 version | `0x0118` (1.24) | `0x0118` |
| Capabilities | `0x000a` | `0x000a` |

Radio profile: EU 2.4 GHz, 2440 MHz, FLRC 2600 kbps, coding rate 3/4,
12 dBm, 255-byte radio payload, 1 Mbaud host UART.

Final state: both stations at **boot #2** (one deliberate reset after flashing),
`cfg=1`, `rxen=1`, in RX, no host traffic, FIPS containers stopped. No modem
crash log, no Zephyr fatal, no watchdog reset.

---

## 3. Firmware architecture

### 3.1 Two build modes

- **Loopback** (`seeed-bridge-loopback-*`): the original host codec/UART
  regression path. It never opens the radio; `CFG` returns a nonzero status.
- **FLRC** (`seeed-bridge-flrc-*`): a raw LR2021 packet bridge using the
  official Semtech RAC transaction API. It moves raw packets only; FIPS
  fragmentation, ARQ, deduplication, Noise and IPv6 remain in the host.

### 3.2 Radio backend

`src/flrc_radio.cpp` owns the RAC context and one radio owner at a time:

- RX is re-armed from the RAC completion callback.
- TX is queued in a 32-packet message queue and drained by the main loop.
- A 2 ms inter-frame guard lets the peer re-arm RX between fragments.
- A 100 ms RX window is used, but a queued TX aborts RX only after **5 ms of
  radio silence**, so a fragment burst is never truncated.
- Counters cover confirmed TX done, valid RX, CRC errors, queue drops, oversize
  RX, TX timeouts, IRQ clears and RAC submit results.

`CFG` maps band/frequency, 325/650/1300/2080/2600 kbps, TX power, exact sync
word and payload length; invalid combinations return a nonzero `CFG_ACK`.

### 3.3 Reset and crash diagnosis

The earlier “intermittent reset” was an assumption. The firmware now records
evidence that survives a warm reset:

- `src/reset_diag.cpp`: a `.noinit` boot record with magic, version, boot
  count, raw `RESETREAS`, fatal reason/PC/LR/thread, last uptime and checksum.
  It is filled at `PRE_KERNEL_1`, before any driver can consume the reset cause.
- `src/fatal_hook.cpp`: `k_sys_fatal_error_handler` stores the fatal reason and
  stacked PC/LR, then cold-reboots.
- `CONFIG_STACK_SENTINEL`, `CONFIG_THREAD_NAME` and
  `CONFIG_HW_STACK_PROTECTION` make a stack overflow a recorded fatal error.
- `BR_DIAG` / `BR_DIAG_ACK` (bridge protocol 11/12) let the host request the
  record and live RAC counters with `fips-lr2021ctl diag`.
- `STAT.resets` is now the cumulative warm-reset count (boot count minus one),
  not a hard-coded zero.

Example `diag` output:

```text
boot#2 rst=SREQ up=1116534ms
flrc up=1116534 svc=1031967 eng=895481 rx_ok=49551 rx_fail=2 tx_ok=35442 tx_fail=0 abort=23949
cb rx=24098 tx=35438 crc=2 to=1847 ab=23607 other=0 rc=0 st=5
q host_tx=35442 tx_full=0 rx_full=0 rx_over=0 irq_clr=84995 tx_hw=4 rx_hw=1 cfg=1 rxen=1
```

### 3.4 The two modem-panic paths

Both were vendor-code panics, not Zephyr fatals or brownout:

1. **Stale `RX_DONE` during TX.** `rp_irq_get_status:1036` processed an
   `RX_DONE` IRQ while the current radio task was `TX_FLRC`; the generic
   payload fetch then saw an unsupported task type, returned
   `RP_HOOK_STATUS_ID_ERROR`, and `SMTC_MODEM_HAL_PANIC` rebooted the MCU.
   Fix: clear the radio IRQ status before every RX/TX submit.
2. **Oversize RX length.** A corrupt FLRC length header can carry up to 511
   bytes. The RAL rejected a length above the 255-byte RAC buffer, tripping the
   panic path. Fix: give the RAC a 511-byte RX buffer (512-byte array) and drop
   frames above the 255-byte application payload in the callback.

Before the fix one station reached **boot #15** in a single session. After the
fix both stations stayed at boot #2 through 25k/50k/100k traffic and a
10-minute soak.

### 3.5 511-byte payload experiment (not adopted)

The LR2021 FLRC driver supports 6–511-byte payloads and a 1023-byte FIFO. The
bridge limit was raised to 511 and tested:

- 480-byte single-frame traffic was intermittent;
- 500/1000-byte multi-frame traffic intermittently reset the MCU or stalled the
  sender;
- the harmonized bench requires a **≥40 ms gap** for LEN > 256.

Production remains at 255 bytes. 511 is a hardware capability, not a validated
FIPS configuration, and it would not lift the 1 Mbaud host ceiling.

---

## 4. Half-duplex FIPS link layer

### 4.1 Why the first link failed

The original link layer ACKed every fragment immediately and allowed up to 64
pending messages. On a half-duplex radio this produced collisions:

- data and ACK crossed on the air;
- the receiver was not listening while transmitting;
- ACKs were lost, the sender retransmitted, and the retransmissions caused more
  collisions.

The result was 94–99% UDP loss at 100k–1M offered.

### 4.2 What changed

All changes are in the pinned FIPS fork:

- **Poll frame and master/slave role.** The master may initiate; the slave
  transmits only after receiving a frame. When idle, the master sends a poll
  every 20 ms and listens for 15 ms.
- **ACK policy.** A complete message is ACKed immediately. Only a partial
  message uses a 10 ms delayed ACK, so a fragment burst can finish.
- **One message in flight.** The submitter does not fragment the next FIPS
  frame until the previous message is ACKed or dropped.
- **Pacing and priority.** Host→bridge frames are spaced by 2 ms; link ACKs use
  a priority channel ahead of queued data.
- **Instrumentation.** Link stats log frames, ACKs, matches, retransmits,
  drops and pending depth once per second.

### 4.3 Validated configuration

```yaml
transports:
  lr2021:
    baud: 1000000
    band: eu2400
    local_id: 1            # 2 on node B
    mtu: 512
    radio_payload: 255
    ack_timeout_ms: 200
    ack_delay_ms: 10
    tx_pacing_ms: 2
    max_retries: 5
    master: true           # false on node B
```

Both ends must run the `seeed-halfduplex` FIPS revision. The link frame set
gained a Poll kind, so a mixed revision will not interoperate.

### 4.4 Rejected experiments

| Experiment | Result | Decision |
|---|---|---|
| 5 ms RX window | Receiver listened only ~55% of the time; ~65% ACK loss | Reject; use 100 ms + 5 ms quiet-guard abort |
| Abort RX immediately for TX | Truncated the peer's packet; CRC errors on both sides | Reject; abort only after silence |
| 512-byte `max_rx_size` | FLRC length is 9 bits (6–511); receiver misread packets | Use 511 |
| Priority data queues + 300 ms expiry | Starved bulk data; 9.5% loss at 10k | Reject; reverting restored 0% |
| iperf3 TCP with 8K/4K windows | Still 0 bytes | Record as not usable |

---

## 5. Measured results

### 5.1 Direct FLRC packet path

| Direction | App payload | Sent | Delivered | Loss | RSSI |
|---|---:|---:|---:|---:|---:|
| B→A | 64 B | 100 | 100 | 0% | −20.6 dBm |
| A→B | 64 B | 100 | 100 | 0% | −20.6 dBm |
| B→A | 255 B | 100 | 100 | 0% | −20.6 dBm |
| A→B | 255 B | 100 | 100 | 0% | −20.6 dBm |

A 255-byte application message is two radio frames at `radio_payload: 255`.
A 30,000-message, ~35-minute 64-byte soak delivered 15,000/15,000 in each
direction (0% loss), with no drops or timeouts and 5 CRC errors total.

### 5.2 FIPS over the radios

| Gate | Result |
|---|---|
| Native `lr2021` transport | **up** |
| Noise peer authentication | **connected** |
| `ping6` over `fips0` | **5/5, 0% loss**, RTT ~59–1746 ms |
| iperf3 UDP 10k offered | **0% loss**, 9.1 kbit/s delivered |
| iperf3 UDP 25k offered | **0% loss**, 24.9 kbit/s delivered |
| iperf3 UDP 50k offered | 3.4% loss, 34.6 kbit/s delivered |
| iperf3 UDP 100k offered | 46% loss, 36.3 kbit/s delivered |
| 10-minute UDP soak, 25k | **0.08% loss (5/6251)**, 24.9 kbit/s |
| Raw 4 KiB TCP | ~4.5 s, ~7 kbit/s |
| SSH over `fips0` | **pass** (`SSH_OVER_FIPS_OK`) |
| iperf3 TCP bulk | **0 bytes over 30 s**, not usable |
| MCU resets under test | **none** (boot #2 throughout) |

The stable operating point is **25 kbit/s at 0% loss**. Delivered throughput
saturates around 35 kbit/s before loss rises. The limiter is per-message
half-duplex turnaround and FIPS queuing, not CRC, radio loss or the host UART.

`iperf3` TCP bulk remains an open failure. The control connection establishes,
raw TCP carries 4 KiB, and SSH works; the bulk stream itself delivers 0 bytes
with default, 8 KiB and 4 KiB socket windows. This is documented as a known
limitation, not a pass.

---

## 6. Reproduction

### 6.1 Build and flash

```bash
cd reference/fips-lr2021
make seeed-bridge-flrc-build BRIDGE_BAUD=1000000
make seeed-bridge-flrc-flash BRIDGE_BAUD=1000000 PROBE=7CDB5271
make seeed-bridge-flrc-flash BRIDGE_BAUD=1000000 PROBE=A8022EF0
```

The build uses the pinned FIPS fork. Build FIPS binaries with an isolated
`CARGO_TARGET_DIR` so a shared target directory cannot mix another checkout:

```bash
cd build/fips
CARGO_TARGET_DIR=/var/tmp/build/c08rad0r/cargo-target-seeed-fips \
  cargo build --release -p fips-lr2021 --bins
CARGO_TARGET_DIR=/var/tmp/build/c08rad0r/cargo-target-seeed-fips \
  cargo build --release -p fips-mesh
```

### 6.2 Two-node FIPS harness

Private configs live under ignored `build/fips-e2e/`; never commit nsecs.
Build the container image once, then run:

```bash
FIPS_E2E_CONFIG_DIR="$PWD/build/fips-e2e" \
SERIAL_A=/dev/ttyACM0 SERIAL_B=/dev/ttyACM1 \
tests/hardware/run_fips_e2e.sh
```

The harness uses two `--network none` containers, one serial device each,
`CAP_NET_ADMIN` and `/dev/net/tun`. `IPERF_RATES` defaults to `10k 25k 50k`.

### 6.3 Focused rate or soak run

```bash
RATES="25k" SECONDS_PER_RATE=600 IPERF_LEN=300 \
  ./tests/hardware/run_fips_rate.sh
```

### 6.4 Reset/radio diagnostics

```bash
fips-lr2021ctl --serial /dev/ttyACM0 --baud 1000000 diag
```

The same record is readable over SWD with pyocd if FIPS owns the UART.

### 6.5 Validation checks

```bash
./tests/host/run_seeed_bridge_test.sh
g++ -std=c++11 -Wall -Wextra -Werror -o build/test_bridge_protocol \
  tests/host/test_bridge_protocol.cpp && ./build/test_bridge_protocol
CARGO_TARGET_DIR=... cargo test -p fips-lr2021        # 22 passed
CARGO_TARGET_DIR=... FIPS_DIR=... ./tests/host/run_mock_e2e.sh
shellcheck tests/hardware/*.sh scripts/*.sh
```

---

## 7. Artifacts and evidence

| Artifact | Value |
|---|---|
| Bridge commit | `b2267e546f60e8b01e68d7c3c1347994d437bfd8` |
| FIPS fork / branch | `c03rad0r/fips` / `seeed-halfduplex` |
| FIPS commit | `78b76d45c71f443099ff7bc5f89ecab4260495d5` |
| Firmware image | 87,780 bytes, SHA256 `526ba7f571fe0cb505c1354a8c2320683ba5d506dfff3bf31c90b8e42e40318a` |
| Validated configs | `fips/configs/seeed-eu2400-node-{a,b}.example.yaml` |
| Harnesses | `tests/hardware/run_fips_e2e.sh`, `run_fips_rate.sh`, `per.sh` |
| Results evidence | `docs/SEEED-LR2021-EVK-BENCH-RESULTS-2026-11-22.md` |
| Run guide | `docs/SEEED-LR2021-EVK-FIPS-E2E.md` |
| Protocol | `docs/BRIDGE-PROTOCOL.md` |

Raw log hashes are recorded in the results document. Logs live under the
ignored `build/flrc/` directory.

---

## 8. Decisions and rationale

1. **Use the official RAC API, not RadioLib or FLRP session semantics.**
   The RAC path is the supported LR20xx driver and the stock PER sample’s
   structure; it preserves the host’s raw-packet contract.
2. **Cap application payloads at 255 bytes.** 511 is supported by the radio but
   was unstable in multi-frame traffic and the harmonized bench requires a
   ≥40 ms gap for >256 bytes.
3. **Keep the host UART at 1 Mbaud.** The stock USB-C path tops out there.
   UARTE00 at 4 Mbaud shares the peripheral instance with SPI00, which the radio
   needs, so it is not usable concurrently on the XIAO.
4. **Fix the panic rather than mask it.** Clearing IRQs and sizing the RX buffer
   addresses the vendor trigger while preserving the packet path.
5. **Use a master/slave token rather than CSMA.** There is no carrier sense on
   this FLRC path, and a deterministic poll is simpler and more reliable for a
   point-to-point link.
6. **ACK complete messages immediately, delay only partial ones.** This removes
   the per-message latency without reintroducing data-vs-ACK collisions.
7. **Report the TCP bulk failure.** Raw TCP and SSH pass, but iperf3 TCP bulk
   does not; calling it a pass would be false.

---

## 9. Open items

1. `iperf3` TCP bulk: 0 bytes over 30 s. Likely a window/queue interaction;
   needs TCP-level tracing and possibly a larger link window or MSS tuning.
2. Extend the 10-minute soak to the planned 30 minutes.
3. Reverse-direction and bidirectional bulk measurements.
4. Optional FIPS gateway/Internet test with explicit NAT/egress, reported
   separately from iperf3.
5. Above ~1 Mbit/s requires a hardware change (direct USB-SPI or a different
   host board); no purchase or wiring is approved.
