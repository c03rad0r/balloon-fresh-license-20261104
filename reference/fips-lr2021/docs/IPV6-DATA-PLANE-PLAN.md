# IPv6 data-plane recovery plan

Written 2026-11-08. Tracks the work needed to take the E80/ESP32-S3 FIPS transport
from "authenticated radio peers" to a working IPv6 link and SSH session.

## What failed

Two FIPS link peers authenticated successfully, but the **end-to-end FSP
session** never completed. The measured sequence was:

```text
A: Session initiation started dest=node-b
B: SessionSetup opened; SessionAck sent; awaiting msg3
A: Session handshake timed out ... OpeningFailed
B: Session setup answered ... expired without msg3
```

`show sessions` was empty in both namespaces while `ping` was already sending
packets into the TUN. Therefore IPv6 did not fail because of namespaces, routes
or TUN addresses. It failed because FIPS had no end-to-end session and the
underlying radio link was corrupting the handshake frames.

### Radio evidence

```text
A log: 1121 bad crc32 / bad magic drops in 1296 log lines
B log:    9 bad crc32 / bad magic drops in 200 log lines
```

The asymmetry came from the mixed test topology:

| Node | Radio host | TX packet length behavior |
|---|---|---|
| A | ESP32-S3 SPI bypass | fixed 255-byte radio configuration |
| B | native E80 STM32 | changes FLRC packet length per transmission |

The S3 → native direction worked; the short native → S3 direction was rejected
or corrupted. This is not the design the onboarding person is building. The
intended design is two identical ESP32-S3/E80 adapters.

### Why Wirehair is not the first fix

Wirehair is an erasure code for multi-symbol blocks. It cannot repair a broken
short-packet framing path, cannot reconstruct a message when no valid symbol
arrives, and does not replace a missing FIPS session handshake. On this
half-duplex link, extra FEC transmissions would also increase collisions before
the baseline loss is understood. It is therefore scheduled as a later optional
data-plane optimization, not as this repair.

## Goal and acceptance

A pass means all of the following, not just a successful `HELLO` or peer entry:

- [ ] Two identical ESP32-S3/E80 adapters are installed.
- [ ] Every E80 TX packet is explicitly padded to the configured fixed length.
- [x] 100 consecutive packets cross in the A → B direction (128 bytes each, no echo CRC failures).
- [x] 100 consecutive packets cross in the B → A direction (128 bytes each and gentler pacing, no echo CRC failures).
- [x] No `bad magic` or `bad crc32` occurs during those controlled PER runs.
- [ ] Simultaneous FIPS control flows and bidirectional traffic survive a sustained test (not yet clean).
- [x] Both FIPS nodes report a non-empty `show sessions`.
- [ ] The FIPS IPv6 ping succeeds in both directions with 0% loss.
- [ ] An interactive SSH command succeeds over the FIPS IPv6 address.
- [ ] The test is repeated once from a clean daemon start to prove reliability.

## Phase 1 — deterministic fixed-size TX

The one clean control measurement was 20 full-size packets with zero chip-CRC
errors. Every observed failure was on short frames. Make the E80 path always
transmit a full configured packet:

- [x] Add a host-testable E80 TX-FIFO builder that preserves the payload and
      zero-fills through `payload_length`.
- [x] Use it in `EspIdfLr2021Radio::send_packet` in E80 compatibility mode.
- [x] Add unit tests proving payload preservation, exact zero padding and no
      truncation at an already-full length.
- [x] Build and flash the padded firmware to the available ESP32-S3.
- [x] Confirm `HELLO` reports `chip=0x1801` on that S3.
- [x] Confirm `cfg --band eu868` uses 868.1 MHz, FLRC-650 and sync `2dd4d4b2`.
- [x] Host suite passes 39/39, including the three new E80 FIFO padding tests.
- [x] Radio-init retries raised to five attempts with 100 ms spacing; a fresh
      boot now reports `firmware=0.4.21 chip=0x1801` without an initial CFG.
- [ ] Build and flash the same padded firmware to the second ESP32-S3.
- [ ] Confirm both adapters are independent nodes, not one S3 plus a C3,
      Pico or native STM32.

### Current hardware blocker

Only **one** usable S3 adapter is connected. The native STM32 E80 became silent
and does not recover through USB re-enumeration. The C3 carrier can read a chip
version after the driver fix but receives none of the S3's full-size traffic.
The Pico also receives none with its current E80-path build. Therefore the
100-frame qualification cannot be completed until a second S3 is connected or
the native E80 is physically power-cycled and revalidated.

Do not use the native STM32 bridge as the peer for this acceptance test. It has
different per-packet length behavior and requires its own validated padding
change.

## Phase 2 — link qualification before FIPS

Run an echo listener on node B and 100 payloads from node A:

```bash
fips-lr2021ctl --serial "$PORT_B" --sync-word 2dd4d4b2 \
  echo --band eu868 --seconds 180

fips-lr2021ctl --serial "$PORT_A" --sync-word 2dd4d4b2 \
  per --band eu868 --count 100 --size 231 --peer-id 2
```

Acceptance is **`echo: 100 frames`** on B and no host link CRC errors. Then swap
the roles and repeat. Record:

- [ ] delivered / attempted for each direction;
- [ ] `status` TX timeouts and resets deltas;
- [ ] FLRC RX valid/CRC/length counter deltas;
- [ ] RSSI range.

Only if both directions pass should simultaneous traffic be tested. If
simultaneous traffic loses frames while one-way traffic is clean, the remaining
problem is media access/collisions, not framing.

## Phase 3 — FIPS session gate

Recommended temporary bench settings:

```yaml
node:
  heartbeat_interval_secs: 30

transports:
  lr2021:
    radio_payload: 128
    ack_timeout_ms: 500
    max_retries: 10
```

`radio_payload=128` is mandatory on the current RF pair. 128 works in both
ways; 160 and 192 yield bad host CRC. A plain `cfg --band eu868` resets payload
to 255, so keep the explicit setting in all FIPS configs and `per`/`echo` tests.

Use one static initiator initially to avoid simultaneous reciprocal handshake
floods. On 2026-11-08 this produced authenticated peers and established sessions
on both sides. It did not yet make IPv6 or SSH reliable.

### Carrier-sense guard added in this phase

The bridge now reads preamble/sync/header events before TX, drains completed RX
first, then waits a randomized guard of **8–16 ms during collision-heavy bring-up**.
Idle wait is bounded at 20 ms. This is best-effort CSMA/CA, not global TDMA;
no GPS or common UTC clock is needed. `cca deferral`, `cca capped` and
`cca guard_us` quantify its effect and allow latency-oriented tuning later.
The random guard alone is not a promise that collisions are impossible.

- [ ] Compare PER and ping RTT before/after the guard with identical MTU/ports.
- [ ] Test that sessions still progress to the initiator and responder states.
- [ ] If collisions persist, only then assess fixed slots based on packet-time
      alignment rather than adding redundant transmissions.
- [ ] Wait until `fipsctl show sessions` is **non-empty on both nodes**.
- [ ] Only then run one `ping6`, then a three-packet ping.
- [ ] Check both daemon logs for `SessionSetup`, `SessionAck`, `SessionMsg3` and
      any `bad magic` / `bad crc32` drops.
- [ ] If sessions stay empty, capture the session-layer timestamps and fix that
      before sending more ICMP.

## Phase 4 — IPv6 and SSH

- [ ] Ping B from A using B's actual reported IPv6 address.
- [ ] Ping A from B.
- [ ] Confirm replies are not through host networking by using the isolated
      namespaces (or separate machines with no other route).
- [ ] Start `sshd` inside namespace B bound to B's FIPS address and run one
      non-interactive SSH command from namespace A.
- [ ] Record latency, throughput and any session rekeys.

## Phase 4b — throughput and internet-speed benchmarks

### Benchmark tooling status

- [x] `tests/hardware/per.sh` defaults to `eu868`, 128-byte radio payload and
      a 500 ms sender wait; it prints per-direction delivery and counters.
- [x] `tests/hardware/http-speed.sh` runs the HTTP client inside a FIPS netns,
      measures TTFB/total/goodput and refuses unless its `PING_IP` preflight has
      0% loss.
- [x] The HTTP gate correctly refused a measurement while ping was 1/3
      (`66.7%` loss); no unsupported throughput number was recorded.
- [ ] Pass the 0%-loss gate with the final default CSMA build.
- [ ] Record radio-only 128 KiB/1 MiB results and then optional MCP results.

These are **two different measurements** and must not be conflated.

### Radio/FIPS-local benchmark (authoritative for bridge changes)

Run a small HTTP or `iperf3` server on the peer behind the radio and request it
from inside the FIPS namespace. No public CDN or WAN is in the measurement.

- [ ] Start the HTTP fixture in peer namespace B bound to B's FIPS address.
- [ ] Run `tests/hardware/http-speed.sh` from namespace A with `PING_IP` set to B.
- [ ] Use 128 KiB and 1 MiB payloads first; do not start with 128 MiB.
- [ ] Record TTFB, total time, goodput, per-run values and medians.
- [ ] Compare only runs with identical firmware, MTU, payload size, guard, TX
      power, position and daemon configuration.
- [ ] Reset daemons between before/after configurations so session state does not
      contaminate the comparison.

### Public internet-path benchmark (ContextVM/MCP)

A tool such as `mcp-internet-speed-test` can provide download, upload, latency
and jitter figures through an MCP interface. It is useful only as an
**end-to-end path benchmark after the radio-only path is stable**.

- [ ] Ping from the measuring namespace to the far FIPS address at 0% loss.
- [ ] Ensure the measuring process runs inside the FIPS namespace and has no
      Wi-Fi/Ethernet fallback route.
- [ ] Use a small bounded transfer first (128 KiB–1 MiB), not its 128 MiB class.
- [ ] Record the download/upload goodput, latency, jitter and error counts.
- [ ] Repeat each measurement three times and report the median.
- [ ] Compare against the radio-only baseline from the same run window.
- [ ] Reject a result if it cannot be shown that its HTTP traffic traversed
      LR2021.

Metrics that answer “is the bridge improving?”:

| Metric | Why it matters |
|---|---|
| FIPS ping loss and RTT distribution | Core liveness and retry/collision behavior |
| Radio PER delivered/attempted | Link-layer quality independent of TCP |
| FIPS goodput (local HTTP/iperf) | Actual transport throughput |
| TTFB and total time | Interactive usability |
| Jitter and timeout counts | Tail-latency symptoms |
| Bridge TX timeouts/CRC/CCA counters | Whether MAC settings improve or regress |
| CDN download/upload rate | Only an end-to-end cross-check |

The ContextVM/MCP result is **not** evidence that its traffic used LR2021 unless
the process is confined to the FIPS namespace or runs on the far node and is
invoked over the radio path.

## Phase 5 — optional Wirehair FEC evaluation (later)

Trigger this only if Phase 2–4 pass at low load but bulk transfers or p99 latency
remain unacceptable due to measured erasures. Do not add FEC to fix a broken
link.

Candidate implementation: canonical `catid/wirehair` C++ library (or a thin Rust
FFI wrapper over it), integrated in the host-side `fips-lr2021` link layer.
The bridges remain raw packet pipes.

Evaluation gates:

- [ ] Benchmark ARQ alone at known loss rates (0%, 1%, 5%, 10%, 20%).
- [ ] Measure a hybrid ARQ + FEC link on the same traces.
- [ ] Confirm FEC is used only for multi-packet/bulk messages, not ACK or
      session-handshake control.
- [ ] Guard every FEC symbol with an outer sequence/ID and CRC; never decode
      corrupted symbols.
- [ ] Compare p50/p95/p99 session setup, ping and bulk-transfer latency.
- [ ] Compare goodput, airtime and 868 MHz duty-cycle cost.
- [ ] Compare memory/CPU cost before considering an embedded target.
- [ ] Reject FEC if it worsens collision rate or interactive latency.

Open-source references to evaluate when Phase 5 starts:

- `catid/wirehair` — canonical C++ implementation; use the project's own build
  and license terms.
- `reed-solomon-erasure` (Rust) — candidate for smaller fixed blocks.
- RaptorQ/RFC 6330 implementations — alternative for standardized deployments.

## Current blockers and findings

- The native STM32 E80 became silent after testing; USB re-enumeration did not
  recover it. It requires a physical power cycle before it can serve as a
  reference again.
- The NiceRF ESP32-C3 reports a valid LR2021 version with the corrected driver,
  but its TX/IRQ behavior is different and it is not a substitute for a second
  S3 adapter.
- Short packets may set the chip CRC flag even when their payload reaches the
  independent FIPS CRC intact. The host CRC decision remains authoritative.
- No FIPS IPv6/SSH claim is valid until Phases 2–4 pass.
