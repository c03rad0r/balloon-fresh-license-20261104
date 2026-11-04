# FIPS over LR2021/FLRC — Reference Implementation Plan & Checklist

**Status:** Plan / ready for build mode  
**Created:** 2026-11-02  
**PR target:** `felixfelix-bot/balloon-fresh` (subdirectory: `reference/fips-lr2021/`)  
**FIPS fork:** `felixfelix-bot/fips`, branch `balloon-lr2021`  
**Event target:** Exit & Build 6, Bandera TX, 5–8 Nov 2026  
**Immediate goal:** two machines on the hermes fleet exchanging FIPS traffic over LR2021 FLRC.

## 0. Status snapshot (2026-11-02)

| Area | State |
|---|---|
| Fork sync + pin | done (`c03rad0r/fips`, `balloon-lr2021`, tag `event-2026-11`) |
| Link layer + host tests | done (21 link/bridge tests + config test; 20/20 virtual-bridge E2E) |
| FIPS native transport | done; real E80 start verified (`1559063`), transport `lr2021` running/stopped cleanly |
| Daemon + CLI | done, builds; `per`/`echo` validated over virtual PTYs |
| RP2040 bridge firmware | written, host protocol test passes; hardware build/flash pending |
| E80 STM32 bridge | built; flashed via Pico and via ESP32-S3; HELLO/CFG/STATUS verified |
| ESP32-S3 probe | **verified** — current OpenOCD + `adapter speed 5000`; programmed an E80 end to end |
| Board inventory | 1 working bridge, 1 untested (failed with Pico earlier), 1 with a dead STM32 debug port |
| Hardware validation | one E80 bridge verified; two-node RF pending a second working board |
| Balloon-fresh PR | https://github.com/felixfelix-bot/balloon-fresh/pull/395 |

See `docs/BRINGUP-FINDINGS-2026-11-03.md` for the probe setup, the meter tests
that separate probe faults from board faults, and what the dead board is still
good for.


---

## 1. Objective

Build a self-contained, testable **FIPS transport over LR2021 using FLRC**, with:

- a native `transports.lr2021` integration in a **fork** of `jmcorgan/fips`;
- a stock-FIPS UDP daemon fallback;
- an RP2040 + E80/LR2021 bridge firmware;
- configurable bands for EU 868 MHz, US 902–928 MHz, and 2.4 GHz;
- host-side tests, hardware tests, and an event runbook;
- all reference material under `reference/fips-lr2021/` in `balloon-fresh`.

### Non-goals

- No pull request, issue, comment, or push to `jmcorgan/fips`.
- No rewiring of the existing balloon flight firmware.
- No PCB fabrication.
- No claim of regulatory certification.
- No multi-relay mesh scheduling in the MVP (single transparent relay is a stretch goal).
- No RP2040-native microfips port in the MVP.

---

## 2. Key decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Native FIPS transport **and** daemon fallback | Native is the real deliverable; daemon keeps a working event path if the fork integration slips. |
| D2 | RP2040 + E80 bridge first | Reuses the proven raw-FLRC E80 path already in `firmware/e80-bypass`; hardware is on hand. |
| D3 | Host-tested now, hardware gate later | x280 is currently unreachable; do not claim hardware results until boards answer. |
| D4 | Fork-only FIPS work | No upstream PRs/issues. Fork `master` mirrors upstream; feature branch rebased. |
| D5 | Event build pinned | Tag `event-2026-11` freezes the demo; upstream sync can move without breaking the event. |
| D6 | 2.4 GHz first, then US 915, then EU 868 | 2.4 GHz is the proven path; 915 is the event target; 868 is the EU requirement. |
| D7 | Link layer on the host | Firmware stays a small, testable packet pipe; hard logic is unit-tested in Rust. |

---

## 3. Current state / evidence

- `balloon-fresh` contains:
  - `tracker/firmware/components/lr2021_transport/` — C++ raw-SPI transport with host tests.
  - `firmware/e80-bypass/rp2040/` — proven RP2040 + E80 raw FLRC at 868 MHz.
  - `firmware/e80-stm32-bench/` — E80 STM32 bench firmware, 2 Mbaud console.
  - `mesh-stack/flrc-bench-espidf/` — prior ESP32-C3 FIPS-over-FLRC bridge using PTY.
- `microfips` branch `feat/lr2021-transport` has:
  - `lr2021_framing.rs` — chunking only, no sequence/reassembly.
  - `lr2021_transport.rs` — FIPS `Transport` adapter, but incomplete.
  - `lr2021_spi.rs` — trait + mock.
  - `lr2021_esp_hal.rs` — real SPI read path stubbed.
- `felixfelix-bot/fips` fork:
  - fork `master`: `d769e50`
  - upstream `master`: `6557961`
  - **0 ahead / 1,399 behind** — safe fast-forward.
- Hardware:
  - x280 currently unreachable from this session.
  - x240 reachable but no `/dev/ttyUSB*` or `/dev/ttyACM*`.
  - Hardware validation is therefore a documented gate, not a current result.

---

## 4. Architecture

```
Laptop A: FIPS
   │  native transports.lr2021   (or fips-lr2021d UDP fallback)
   ▼
USB CDC
   │
RP2040 bridge A  ── LR2021 FLRC ──  RP2040 bridge B  ── USB CDC ── Laptop B: FIPS
   │
   └── optional relay mode (same firmware)
```

### Data path

1. FIPS produces one FMP frame per `send()`.
2. Host link layer fragments the frame into LR2021-sized radio packets.
3. Bridge transmits each fragment as a raw FLRC packet.
4. Peer bridge receives the packet with RSSI/SNR/CRC metadata and forwards it over USB.
5. Peer host link layer reassembles and delivers one complete FMP frame to FIPS.
6. ACK/NACK frames provide best-effort retransmission; FIPS still tolerates loss.

---

## 5. Repository layout

```
reference/fips-lr2021/
├── README.md
├── ARCHITECTURE.md
├── docs/
│   ├── BRIDGE-PROTOCOL.md
│   ├── BANDS-AND-REGULATORY.md
│   ├── HARDWARE.md
│   ├── DEMO-RUNBOOK.md
│   ├── FORK-MAINTENANCE.md
│   ├── PORTING-ESP32.md
│   └── RESULTS.md
├── fips/
│   ├── FORK.md
│   ├── fips-pin.txt
│   ├── patches/
│   │   └── 0001-lr2021-transport.patch
│   └── configs/
│       ├── eu868.yaml
│       ├── eu868-high.yaml
│       ├── eu2400.yaml
│       ├── us915.yaml
│       ├── us915-robust.yaml
│       └── us2400.yaml
├── host/
│   ├── Cargo.toml
│   ├── fips-lr2021/          # link layer, bridge client, shared types
│   ├── fips-lr2021ctl/       # configure bands, read stats, run PER tests
│   └── fips-lr2021d/         # stock-FIPS UDP daemon fallback
├── firmware/
│   └── rp2040-bridge/        # reuses firmware/e80-bypass raw FLRC
├── scripts/
│   ├── bootstrap-fips.sh
│   ├── sync-fips-fork.sh
│   ├── build.sh
│   ├── flash-bridge.sh
│   ├── demo-2node.sh
│   └── demo-relay.sh
└── tests/
    ├── host/
    └── hardware/
```

The PR adds this tree plus a small link from the root README. Existing firmware trees are not rewritten.

---

## 6. Fork policy and sync

### Rules

- `upstream` is fetch-only. Never push, PR, or comment upstream.
- Fork `master` is a clean mirror of upstream `master`.
- Feature work is on `balloon-lr2021`, rebased onto synced `master`.
- Event builds use tag `event-2026-11`, not a moving branch.
- `bootstrap-fips.sh` clones the **fork at the event pin**, not `master`.

### Initial sync

```bash
git remote add upstream https://github.com/jmcorgan/fips.git
git fetch upstream master
git checkout master
git merge --ff-only upstream/master
git push origin master
git checkout -b balloon-lr2021
```

### Ongoing sync

`scripts/sync-fips-fork.sh`:

1. Fetch `upstream/master`.
2. Fast-forward fork `master`; abort if not an ancestor.
3. Rebase `balloon-lr2021` onto `master`.
4. Run `cargo test` and the transport suite.
5. Regenerate the patch.
6. Update `fips-pin.txt`.
7. Push `master` and `balloon-lr2021` to the fork.
8. On conflict/test failure: stop, preserve `event-2026-11`, create `sync/YYYYMMDD`, report.

Optional automation: daily/weekly systemd timer or cron calling the script; or `gh repo sync felixfelix-bot/fips --source jmcorgan/fips --branch master` plus the rebase step. Keep automation out of fork `master` so it remains a clean mirror.

### Pins

| Ref | Purpose | Moves? |
|---|---|---|
| `felixfelix-bot/fips:master` | upstream mirror | yes, fast-forward |
| `felixfelix-bot/fips:balloon-lr2021` | active development | yes, rebased |
| tag `event-2026-11` | frozen event build | no |
| `reference/fips-lr2021/fips/fips-pin.txt` | what the reference uses | only after tests pass |

`fips-pin.txt` format:

```
upstream_base: 6557961...
fork_commit:   <event tag commit>
branch:        balloon-lr2021
last_sync:     2026-11-02
sync_script:   scripts/sync-fips-fork.sh
```

---

## 7. Link layer design

### Radio frame

```
magic F1 50 | version/type | flags | src_id(4) | dst_id(4) |
epoch(2) | frame_seq(2) | frag_idx(1) | frag_count(1) |
payload_len(2) | payload | CRC32(4)
```

- `type`: DATA, ACK, NACK.
- `src_id` / `dst_id`: 4-byte link IDs; broadcast `0xFFFFFFFF`.
- `epoch`: link epoch, changes on restart.
- `frame_seq`: FIPS frame sequence, wraps.
- `frag_idx` / `frag_count`: fragment position.
- `CRC32`: covers header + payload.

### Fragmentation and reassembly

- FIPS MTU: 1400 bytes.
- Radio payload: 255 bytes baseline; 511 bytes optional after validation.
- Reassembly key: `(src_id, epoch, frame_seq)`.
- Bitmap of received fragments; max 16 fragments.
- Timeout: 500 ms, then drop.
- Deliver one complete FIPS frame per receive event.

### ACK / ARQ

- Receiver ACKs with the fragment bitmap.
- Sender retransmits missing fragments, up to 3 attempts.
- Drop after retries; FIPS sees loss.
- Duplicate fragments dropped by key + bitmap.
- Window: 1–4 frames (start with 1, measure, then increase).

### Addressing

- `TransportAddr` = `src_id` bytes.
- Local `src_id` derived from node key hash or configured explicitly.
- `send(addr, data)` sets `dst_id` from `addr`; broadcast if unknown.
- `recv` reports the frame's `src_id`.

### Bridge protocol

USB CDC framing:

```
[A5 5A][type][len_lo][len_hi][payload][CRC16]
```

Types:

| Type | Direction | Purpose |
|---|---|---|
| `HELLO` | host → bridge | protocol version, capabilities |
| `HELLO_ACK` | bridge → host | firmware version, chip ID, band support |
| `CFG` | host → bridge | band, frequency, bitrate, power, sync, relay, payload length |
| `CFG_ACK` | bridge → host | actual values or error |
| `TX` | host → bridge | raw radio packet |
| `RX` | bridge → host | raw packet + RSSI/SNR/CRC/timestamp |
| `STAT` | both | counters |
| `EVT` | bridge → host | reset/watchdog/config event |
| `PING` | host → bridge | liveness |

The bridge does not parse FIPS frames. It only carries raw radio packets.

---

## 8. FIPS integration

### Patch surface

- `src/config/transport.rs`
  - `Lr2021Config`: `port`, `baud`, `band`, `frequency_hz`, `bitrate_kbps`, `tx_power_dbm`, `sync_word`, `mtu`, `relay`, `local_id`, `peer_id`, `auto_connect`.
  - Add `lr2021` to `TransportsConfig`; merge and validation.
- `src/transport/lr2021/mod.rs`
  - `Lr2021Transport` with `TransportId`, config, bridge client, packet channel, stats.
  - Reader thread delivers `ReceivedPacket`s.
  - Writer thread drains TX queue.
- `src/transport/mod.rs`
  - `TransportType::LR2021` (connectionless, unreliable at FIPS level).
  - `TransportHandle::Lr2021` + all match arms.
- `src/node/mod.rs`
  - instantiate in `create_transports`.
- `src/config/mod.rs`
  - validation and merge.
- `src/control/...`
  - `show_transports` and snapshots if needed.

### Dependency

- Add `serialport` (blocking) or `tokio-serial` to the fork.
- Prefer a blocking worker thread + crossbeam channels to match FIPS's sync `Transport` trait.

### Daemon fallback

`fips-lr2021d`:

- Uses the same link layer and bridge client.
- Listens on a local UDP port.
- Forwards FIPS UDP payloads to/from the radio.
- Stock FIPS config points its UDP transport at the daemon.
- Clearly documented as a fallback/test harness, not the native transport.

---

## 9. Bridge firmware

`firmware/rp2040-bridge/`:

- Reuse `firmware/e80-bypass/common/e80_lr20xx_raw.h` and `e80_pinmap.h`.
- USB CDC binary protocol; UART for human logs.
- Runtime `CFG`:
  - band/path: LF (sub-GHz) / HF (2.4 GHz);
  - frequency Hz;
  - FLRC bitrate;
  - TX power;
  - sync word;
  - variable packet length;
  - relay mode.
- Single radio-owner task:
  - TX queue, RX re-arm, IRQ-driven TX/RX.
  - No concurrent `standby`/`startReceive` from multiple tasks.
- Relay mode:
  - Repeat unique received packets once.
  - Short hash cache to prevent immediate loops.
  - One relay only in MVP.
- Stats:
  - TX/RX packets, CRC errors, drops, timeouts, RSSI/SNR, reset reason.
- Watchdog:
  - Re-init after 15 s without valid frame/TX_DONE.
  - At most once per 60 s.
- Size check against RP2040 flash/RAM.
- `docs/PORTING-ESP32.md` for the ESP32-C3/S3 migration.

---

## 10. Band profiles

| Profile | Frequency | FLRC | TX power | Notes |
|---|---:|---:|---:|---|
| `eu868` | 868.1 MHz | 650 kbps | +14 dBm | EU 1% duty cycle; FLRC-650 fits 868.0–868.6 |
| `eu868-high` | 869.525 MHz | 650 kbps | +14 dBm | EU 869.4–869.65, 10% duty cycle; optional |
| `us915` | 915.0 MHz | 1300 kbps | +22 dBm | US DTS; 6 dB BW > 500 kHz |
| `us915-robust` | 915.0 MHz | 650 kbps | +22 dBm | Narrower, still DTS-compliant |
| `eu2400` | 2440 MHz | 2600 kbps | +12 dBm | 2.4 GHz ISM |
| `us2400` | 2440 MHz | 2600 kbps | +12 dBm | 2.4 GHz ISM |
| `custom` | operator | operator | operator | Warns; does not certify |

Docs must state these are starting points, not certification. EU duty cycle and measured 6 dB bandwidth need hardware verification.

---

## 11. Test plan

### Host tests

- Frame parser and CRC.
- Fragment/reassemble: exact, loss, reorder, duplicate, max size, sequence wrap.
- ACK/NACK retransmit logic.
- Mock bridge loopback with configurable loss/latency.
- Two FIPS `Node`s over mock LR2021: Noise handshake + encrypted payload.
- Fuzz/property tests for parser.
- Firmware protocol/config parser compiled natively.

### Hardware tests (when boards reachable)

- Two nodes at 2.4 GHz first.
- `fips-lr2021ctl` band switch and stats.
- FIPS Noise handshake, `ping6`, `iperf3 -u`.
- PER/RSSI/SNR at 1 m / 10 m / 100 m.
- Relay with third board; check duplicate/replay counters.
- 30-minute soak; 4-hour soak if time.

### Acceptance

- Handshake < 60 s.
- 100% ping at bench distance.
- >90% at 100 m.
- >100 kbps at 2.4 GHz.
- No radio lockup in 30 min.
- Documented band switch.
- Event build reproducible from the pin.

---

## 12. Event runbook

`docs/DEMO-RUNBOOK.md`:

1. Pre-flash all RP2040 boards before travel.
2. Connect USB and confirm `/dev/ttyACM*`.
3. Run `fips-lr2021ctl hello` and `fips-lr2021ctl cfg us915`.
4. Start FIPS node A/B with `transports.lr2021`.
5. Wait for handshake; run `ping6` and `iperf3`.
6. For relay: set third bridge to relay mode; repeat A/B tests.
7. Fallback: run `fips-lr2021d` with stock FIPS UDP config.
8. Capture stats and log results in `docs/RESULTS.md`.

---

## 13. Work sequence

### Day 0 — fork and scaffold

- Fast-forward fork `master`.
- Create `balloon-lr2021`.
- Scaffold `reference/fips-lr2021/`.
- Write README, ARCHITECTURE, FORK-MAINTENANCE, BANDS.
- Add checklist to this file.

### Day 1 — link layer and host tests

- Implement frame format, fragmentation, reassembly, ACK/ARQ.
- Implement mock bridge and loss/reorder/duplicate tests.
- Implement `fips-lr2021ctl` skeleton.

### Day 2 — bridge firmware and serial transport

- RP2040 bridge firmware with config, TX/RX, stats.
- Host serial bridge client and config handshake.
- Mock end-to-end loopback.
- Build size check.

### Day 3 — FIPS integration and daemon

- Fork patch: config, transport module, handle, node wiring.
- `fips-lr2021d` UDP daemon.
- Two-node mock FIPS handshake test.
- Config presets.

### Day 4 — hardware and PR

- Hardware validation if x280 reachable.
- Relay test if third board available.
- Results doc, demo runbook.
- Open draft PR; update with evidence.
- Final PR when host tests and any hardware tests pass.

---

## 14. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| x280 unreachable | No hardware results | Host tests first; hardware gate documented; request access. |
| RP2040 BOOTSEL manual | Slow field flashing | Pre-flash before event; document picotool/UF2; ESP32 port guide. |
| E80 2.4 GHz path unverified | 2.4 GHz fails | Verify antenna/jack; default to 868/915. |
| E80/RP2040 wiring mismatch | Bring-up fails | Reuse proven pinmap; continuity checks. |
| FIPS upstream drift | Patch breaks | Fork sync script; event pin; rebase tests. |
| ARQ tuning | Throughput/latency issues | Start stop-and-wait; measure; increase window. |
| Relay duplicates | FIPS replay counters | Link-layer dedup; one relay only. |
| EU regulatory | Non-compliant defaults | 868.1 +14 dBm; duty-cycle note; no certification claim. |
| Time | Event deadline | 2.4 GHz 2-node path first; relay/915/868 are increments. |

---

## 15. PR plan

- Branch: `pr/fips-lr2021-reference` in `balloon-fresh`.
- Base: `master`.
- Commits:
  1. `docs(reference): add fips-lr2021 plan and architecture`
  2. `feat(reference): link layer and host tests`
  3. `feat(reference): rp2040 bridge firmware`
  4. `feat(reference): fips lr2021 transport and daemon`
  5. `docs(reference): band configs, runbook, results`
  6. `test(reference): host integration and hardware scripts`
- PR text:
  - What it is.
  - How to build/run.
  - Test evidence.
  - Hardware status (honest: pending/passed).
  - Fork pin and no-upstream-PR statement.
- Open as draft early; final when host tests pass and hardware is either passed or explicitly pending.

---

## 16. Checklist

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked.

### Planning and fork

- [x] Read balloon-fresh, FIPS, microfips, event repos.
- [x] Confirm native transport + daemon fallback.
- [x] Confirm RP2040 + E80 first.
- [x] Confirm host-test-first / hardware gate.
- [x] Confirm fork-only policy (no upstream PRs).
- [x] Record fork is 1,399 commits behind upstream.
- [x] Fast-forward fork `master` to upstream.
- [x] Create fork branch `balloon-lr2021`.
- [x] Create tag `event-2026-11` after first working build.
- [x] Write `fips/FORK.md` and `fips-pin.txt`.
- [x] Write `scripts/sync-fips-fork.sh`.
- [x] Write `docs/FORK-MAINTENANCE.md`.

### Scaffolding

- [x] Create `reference/fips-lr2021/` tree.
- [x] Write root `README.md`.
- [x] Write `ARCHITECTURE.md`.
- [x] Write `docs/BRIDGE-PROTOCOL.md`.
- [x] Write `docs/BANDS-AND-REGULATORY.md`.
- [x] Write `docs/HARDWARE.md`.
- [x] Write `docs/DEMO-RUNBOOK.md`.
- [x] Write `docs/PORTING-ESP32.md`.
- [x] Write `docs/RESULTS.md` template.

### Link layer (`host/fips-lr2021`)

- [x] Define frame header and CRC32.
- [x] Implement parser/serializer with bounds checks.
- [x] Implement fragmenter.
- [x] Implement reassembly bitmap and timeout.
- [x] Implement duplicate suppression.
- [x] Implement ACK/NACK and retransmit.
- [x] Implement broadcast/unicast addressing.
- [x] Implement MTU 1400 handling.
- [x] Unit tests: exact roundtrip.
- [x] Unit tests: single fragment loss.
- [x] Unit tests: multiple fragment loss.
- [x] Unit tests: reorder.
- [x] Unit tests: duplicate.
- [x] Unit tests: sequence wrap.
- [x] Unit tests: max frame.
- [x] Unit tests: malformed frame.
- [ ] Property/fuzz tests.
- [ ] Mock bridge with loss/latency.
- [x] Two-transport loopback test.

### Serial bridge client

- [x] Open serial port with baud/config.
- [x] `HELLO`/`HELLO_ACK`.
- [x] `CFG`/`CFG_ACK`.
- [x] `TX` path.
- [x] `RX` path with metadata.
- [x] `STAT` parsing.
- [x] `EVT` logging.
- [ ] Reconnect on USB drop.
- [x] Timeout/error handling.
- [x] CLI `hello`, `cfg`, `status`, `monitor`, `per`.

### RP2040 bridge firmware

- [x] PlatformIO project scaffold.
- [x] Reuse E80 pinmap/raw FLRC.
- [x] USB CDC binary framing.
- [x] UART human log.
- [x] `HELLO`/`CFG`/`CFG_ACK`.
- [x] LF/HF band path selection.
- [x] Frequency/bitrate/power/sync config.
- [ ] Variable packet length.
- [x] Single radio-owner task.
- [x] TX queue.
- [x] RX IRQ + re-arm.
- [x] TX_DONE/timeout handling.
- [x] Stats counters.
- [x] Reset reason.
- [x] Watchdog.
- [x] Relay mode + dedup.
- [ ] Build size check.
- [x] Host tests for protocol/config.
- [x] Flash script/UF2 instructions.

### FIPS fork

- [x] Sync fork master.
- [x] Add `crates/fips-lr2021` or transport module.
- [x] Add `Lr2021Config`.
- [x] Add `TransportsConfig.lr2021`.
- [x] Add `TransportType::LR2021`.
- [x] Add `TransportHandle::Lr2021`.
- [x] Add all match arms.
- [x] Add `create_transports` wiring.
- [x] Add validation/merge.
- [ ] Add `show_transports`/control output.
- [x] Add `serialport` dependency.
- [x] Build `cargo check`.
- [x] Unit tests in fork.
- [x] Generate patch.
- [x] Tag `event-2026-11`.

### Daemon fallback

- [x] UDP listener.
- [x] FIPS peer address mapping.
- [x] Link layer integration.
- [x] Config file/CLI.
- [x] Stats.
- [x] Stock-FIPS config example.
- [ ] Host test.

### Configs

- [x] `eu868.yaml`.
- [x] `eu868-high.yaml`.
- [x] `eu2400.yaml`.
- [x] `us915.yaml`.
- [x] `us915-robust.yaml`.
- [x] `us2400.yaml`.
- [x] FIPS node A/B examples.
- [x] Sync word/network ID policy.
- [ ] Validation of unsupported combinations.

### Scripts

- [x] `bootstrap-fips.sh` clones fork at pin.
- [x] `sync-fips-fork.sh`.
- [x] `build.sh`.
- [x] `flash-bridge.sh`.
- [x] `demo-2node.sh`.
- [x] `demo-relay.sh`.
- [x] Failure messages with actionable next steps.

### Host tests

- [x] `cargo test` all green.
- [ ] Two-node mock FIPS handshake.
- [ ] Encrypted payload over mock.
- [x] Loss/reorder/duplicate integration.
- [x] Config handshake tests.
- [ ] CLI tests.
- [ ] Daemon tests.
- [ ] CI workflow for host tests.

### Hardware tests (gate)

- [ ] x280 reachable or alternate host provided.
- [ ] Two RP2040/E80 boards enumerate.
- [ ] `fips-lr2021ctl hello` on both.
- [ ] 2.4 GHz config and link.
- [ ] 2.4 GHz FIPS handshake.
- [ ] 2.4 GHz ping.
- [ ] 2.4 GHz iperf3.
- [ ] 2.4 GHz PER/RSSI/SNR at 1/10/100 m.
- [ ] 915 MHz config and link.
- [ ] 915 MHz FIPS handshake/ping.
- [ ] 868 MHz config and link.
- [ ] 868 MHz FIPS handshake/ping.
- [ ] Relay with third board.
- [ ] 30-minute soak.
- [ ] 4-hour soak (if time).
- [ ] No radio lockup.
- [ ] Record results in `docs/RESULTS.md`.

### Documentation

- [x] README quick start.
- [x] Architecture diagram.
- [x] Bridge protocol spec.
- [x] Band/regulatory table.
- [x] Hardware wiring.
- [x] Demo runbook.
- [x] Fork maintenance.
- [x] ESP32 porting guide.
- [x] Troubleshooting.
- [x] Results/limitations.

### PR

- [x] Create `pr/fips-lr2021-reference`.
- [x] Commit plan/docs.
- [x] Commit link layer/tests.
- [x] Commit firmware.
- [x] Commit FIPS patch/daemon.
- [x] Commit configs/scripts.
- [x] Commit results/runbook.
- [x] Push branch.
- [x] Open draft PR.
- [x] Update PR with test evidence.
- [x] Mark ready when host tests pass; hardware passed or explicitly pending. (PR open; hardware explicitly pending.)
- [x] Confirm no upstream PR/issue/comment was created.

---

## 17. Progress log

Append dated entries here as work proceeds.

| Date | What changed | Tests | Next |
|---|---|---|---|
| 2026-11-02 | Plan and checklist written | n/a | Sync fork; scaffold reference tree |
|  |  |  |  |
|  |  |  |  |

---

## 18. Open items / blockers

- **Hardware access:** x280 unreachable; x240 has no boards. Need device paths when available.
- **E80 2.4 GHz path:** verify which SMA jack/path is 2.4 GHz on the `-900` board.
- **RP2040 wiring:** confirm the E80 bypass pinmap on the actual boards.
- **Event band order:** 2.4 GHz bench first; 915 MHz event; 868 MHz EU. Confirm if this changes.
- **Fork sync cadence:** daily or weekly; decide before automation.
- **Sync word/network ID:** default `12 AD 10 1B`; confirm whether event nodes need a distinct network ID.
