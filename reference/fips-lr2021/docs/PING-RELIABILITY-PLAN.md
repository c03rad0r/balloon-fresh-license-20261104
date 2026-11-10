# Ping reliability plan — from working PER bursts to stable IPv6

Written 2026-11-09. Owner checklist for making FIPS IPv6 reliable before HTTP,
SSH or ContextVM/MCP speed measurements.

## Current state — measured 2026-11-10

- S3/E80 firmware: `0.4.22`; NiceRF C3: `0.5.12`; both report `chip=0x1801`.
- 128-byte radio packets, sync `2dd4d4b2`, EU-868, 14 dBm, CSMA-only;
  TDMA and FEC remain disabled.
- Measured host configuration: `packet_gap_ms: 20`, `ack_timeout_ms: 300`,
  `max_retries: 15`, minimal link/session MMP, heartbeat 300 s. The long rekey
  (3600 s) is a benchmark isolation setting, not a production recommendation.
- Host revision `c03rad0r/fips@8155e5ff` with batch-tail NACKs, peer/epoch ACK
  validation and bounded asynchronous one-frame scheduling passes **50/50 IPv6
  replies in both directions** (0% loss), logs `/tmp/ping-gate-async.log` and
  `/tmp/fips-ping-gate.yV9EmH/` on `archipelago`.
- 128 KiB radio-only HTTP completed 3/3 runs and 1 MiB completed 3/3 runs;
  both sizes returned the exact expected bytes with HTTP 200.
- Isolated public-key SSH over the FIPS IPv6 address completed `RADIO_SSH_OK`
  and exited 0. The reusable `tests/hardware/ssh-smoke.sh` passed independently.
- A real rekey at 15:50–15:51 occurred during the third 1 MiB run; that transfer
  completed, and a subsequent 50/50 gate also passed in both directions.
- The current FIPS daemon on `archipelago` is stock `0.4.1`, disabled, inactive,
  and configured with `peers: []`; it is not yet onboarded to either the public
  test mesh or the private Hermes mesh. This is independent of the isolated
  LR2021 test namespaces.

## Resolution from the 2026-11-10 bench session

Controlled 56/128-byte IPv6 payloads were reliable while 512-byte payloads
became lossy and 1000/1200-byte payloads failed. HTTP requests reached the far
server (`200` logged) but sustained TCP streams stalled. This separated the
bulk-delivery defect from the earlier small-ping collision problem.

### DECISIONS — host transport repair

1. **Acknowledge a coherent fragment batch, not every intermediate fragment.**
   Intermediate fragments now produce no response; an incomplete tail produces
   one bitmap NACK, and a complete batch produces one completion ACK. Ordinary
   partial ACKs do not immediately retransmit an already in-flight batch.
   Evidence: `crates/fips-lr2021/src/link.rs`, test
   `nacks_once_at_batch_tail_and_repairs_missing_fragment`.
2. **Authenticate ACK provenance.** Sequence numbers restart at one in both
   directions, so acceptance now includes both peer ID and epoch. Evidence:
   test `rejects_ack_for_wrong_peer_or_epoch`.
3. **Serialize application messages asynchronously.** A bounded 64-frame queue
   submits the next FIPS frame only when the previous batch is complete or has
   exhausted retries. NACK repairs can no longer starve behind a TCP window of
   new frames. Blocking the FIPS thread instead was rejected: it caused 44%
   packet loss and RTT up to 20 s. The asynchronous scheduler retained 0%-loss
   ping and repaired TCP.
4. **Pace fragment commands at 20 ms with a 300 ms retry timer.** A 40 ms /
   1000 ms experiment repaired large pings but regressed the 50-packet gate to
   20% loss; 20/300 passed both large-payload and 0%-loss gates.
5. **Keep CSMA, Wirehair/FEC and production TDMA unchanged.** These were queue,
   ACK and scheduling defects, not a reason to add FEC or fixed slots.

Test evidence from the validated host build:

- FIPS link tests: **25/25**.
- Native LR2021 transport tests: **4/4**.
- Tracker driver tests: **39/39**.
- 50/50 A→B and 50/50 B→A: **0% loss both ways**.
- 1000-byte IPv6 payloads: successful in both directions.
- HTTP 128 KiB, three valid runs:

  | Run | Bytes | TTFB | Total | Goodput |
  |---:|---:|---:|---:|---:|
  | 1 | 131072 | 64.730 s | 147.019 s | 0.0071 Mb/s |
  | 2 | 131072 | 51.854 s | 167.250 s | 0.0063 Mb/s |
  | 3 | 131072 | 21.008 s | 138.060 s | 0.0076 Mb/s |

  Mean goodput: **0.0070 Mb/s**. All responses were HTTP 200 with the exact
  expected length. Result log: `/tmp/http-128k-async-results.log`.

- HTTP 1 MiB, three valid runs:

  | Run | Bytes | TTFB | Total | Goodput |
  |---:|---:|---:|---:|---:|
  | 1 | 1048576 | 48.909 s | 1275.047 s | 0.0066 Mb/s |
  | 2 | 1048576 | 23.274 s | 1272.223 s | 0.0066 Mb/s |
  | 3 | 1048576 | 15.859 s | 1313.169 s | 0.0064 Mb/s |

  Mean goodput: **0.0065 Mb/s**. All responses were HTTP 200 with the exact
  expected length. The complete window was 14:51:15–15:55:38Z. Result log:
  `/tmp/http-1m-async-results.log`.

- Rekey and SSH:
  - Link and FSP rekeys completed around 15:50–15:51 during run 3, including
    dual-initiation resolution; run 3 still completed with exact length.
  - `/tmp/ping-gate-post-rekey.log` then passed 50/50 each direction (0% loss),
    logs `/tmp/fips-ping-gate.KjySLN/`.
  - `tests/hardware/ssh-smoke.sh` returned `RADIO_SSH_OK`, exit 0; logs
    `/tmp/fips-radio-ssh.CEHMa1/`, and temporary credentials were absent after
    cleanup.

Change this decision only with a measured regression comparison that preserves
bidirectional 0%-loss ping and completes 128 KiB/1 MiB HTTP, or with a proven
The validated implementation is committed and pinned at
`c03rad0r/fips@8155e5ffd4baada469ada15eeaa0a3d5bac83c6f`; the reference tree
records the same hash in `fips/fips-pin.txt` and vendors the complete patch.

Raw non-secret evidence is archived outside `/tmp` on the bench in
`/home/archipelago/fips-results/2026-11-10/`; its `README.md` and `SHA256SUMS`
identify the configuration, results and exact host binary. The final host binary
hash matched the local rebuild.

## Results from the 2026-11-09 bench session

- Switching both endpoints to `node.mmp.mode: minimal` and
  `node.session_mmp.mode: minimal` sharply reduced background loss.
- At 14 dBm with minimal MMP, one 20-packet run achieved **20/20 both ways**;
  at 3 and 6 dBm the best was 19–20/20 one way and 20/20 the other.
- A 50-packet gate at 14 dBm/minimal MMP still failed: **49/50 (2%)** one
  direction, with nine raw `bad magic` drops logged across both ends. Missing
  sequences included 1–4 (route warm-up) and later isolated packets.
- `ack_timeout_ms=100, max_retries=15` produced 20/20 both ways in one run;
  `50 ms` regressed one 50-packet run to 43/50. The later batch/pacing work
  superseded this with 300 ms for the validated 20 ms-gap configuration.
- Re-enabling the fixed-slot experiment under minimal MMP gave 55%/25% loss,
  so TDMA is rejected again and stays disabled.
- Shortening the bridge USB host wait from 20 ms to 1 ms did not by itself make
  50-packet ping reliable; direct PER remained 20/20 but FIPS startup can still
  fail to exchange Noise frames.
- The repeated failure mode is **not** merely low RSSI: valid 128-byte frames
  arrive around −42 dBm while `bad magic`/CRC spans occur in bursts. It is not
  yet proven whether the remaining cause is RX FIFO sequencing, FIPS control
  bursts, or incomplete bridge RX event handling.

## Why it was unreliable

A ping requires a sequence of radio frames and ACKs in both directions. The
same radios also carry heartbeats, session/rekey, tree and bloom announcements.
Independent retry clocks can make both ends transmit together, and a lost
control frame triggers further delay and retries.

Observed evidence:

- `bad magic` frames are not merely weak-signal CRC failures; they indicate
  stale/garbage FIFO data or a packet boundary/interleaving fault.
- `bad crc32` frames have valid `F1 50` link headers, so bytes are being
  corrupted after a plausible frame start.
- Near-field RSSI around −29 to −35 dBm is high enough that receiver overload
  must be tested rather than assumed away.
- Controlled one-direction PER does not reproduce the failure as often as
  FIPS's interleaved bidirectional control traffic.

Do not attribute multi-second RTT to airtime: a 128-byte FLRC-650 frame is only
about 1.6 ms. Retries/backoff/queueing dominate.

## Phase 1 — duplicate-aware instrumentation

- [x] Count unique delivered sequences, not just attempts or echo frames
      (`per.sh` now prints and enforces `unique_payloads`).
- [x] Record bad-magic/CRC with frame length and 12-byte header prefix in host debug logs.
- [ ] Record first differing byte for CRC-failed deterministic payloads.
- [x] Capture send/receive and failed-frame events in the native transport debug log.
- [x] Record CCA deferrals/capped waits/guard and RSSI per PER run.
- [x] Freeze firmware, payload 128, sync and peer IDs for the completed comparisons.
- [ ] Add commit/version/config to every benchmark record.

## Phase 2 — isolate the cause

Run each experiment independently, changing one variable:

- [ ] One-direction-only traffic; other side quiet.
- [ ] Simultaneous bidirectional traffic.
- [ ] FIPS control traffic with minimal application traffic.
- [ ] TX power sweep: 6, 8, 10, 12, 14 dBm at fixed board distance.
- [ ] Guard sweep: 0, 2, 4, 8, 16, 32 ms at fixed power.
- [ ] Board separation / antenna orientation check for RSSI changes.
- [ ] Compare S3→C3 and C3→S3 separately; never average away a one-way failure.

Decision rule:

- One-way clean + simultaneous bad → media access.
- Lower TX power fixes RX errors → near-field saturation.
- Both directions fail at equal RSSI → shared frame handling, not collision.
- Only longer frames fail → FIFO/packet-length path.

## Phase 3 — transmission and receive ordering

- [x] Drain completed RX before TX.
- [x] Bounded idle wait plus randomized 8–16 ms guard in CSMA mode.
- [x] RX pumping during any optional slot wait (TDMA remains disabled).
- [ ] Keep RX events intact until `RX_DONE`; never clear a preamble-only event.
- [x] Prevent ACK/retry traffic from overlapping the next queued data burst.
- [x] Serialize one coherent message/fragment batch before yielding the air.
- [x] Schedule later application frames asynchronously behind the active batch.
- [ ] Apply the quiet interval after receiving, not only before our own TX.
- [ ] Keep optional fixed slots disabled unless they beat CSMA on unique delivery.

## Phase 4 — acceptance gates

- [ ] 100/100 unique PER round trips each direction: `per delivered=100`,
      not merely repeated echo transmissions.
- [ ] Zero unexplained `bad magic`/`bad crc32` over 100 packets each way.
- [x] Both FIPS peers connected and both XK sessions established.
- [x] 50/50 IPv6 replies each direction with sequential requests.
- [x] A second 50/50 run after at least one session rekey (following the real
      15:50–15:51 link and FSP rekey, with 0% loss both directions).
- [x] No ping-gate bypass in benchmark scripts (`ping-gate.sh` requires 0% in
      both directions; `http-speed.sh` refuses without a 0%-loss preflight).

Only then:

- [x] 128 KiB HTTP over the radio-only path, 3 runs.
- [x] 1 MiB HTTP over the radio-only path, 3 runs.
- [x] Record final TTFB, total, goodput, loss and counters for both sizes.
- [x] SSH command returns `RADIO_SSH_OK` over the FIPS address.
- [ ] Optional ContextVM/MCP public-internet run in an isolated namespace:
      **not run** — no MCP speed-test resource/tool or WAN route is registered
      in the measuring namespace. Do not bypass the radio path to manufacture
      this result.
- [ ] Compare an optional public-internet result against the completed local
      radio-only baseline if a routed ContextVM fixture becomes available.

## Deferred

Wirehair/FEC, MTU increases and fixed-slot production use remain deferred until
the acceptance gates pass. FEC does not repair bad framing, session loss or
collisions, and adds airtime.

## Relevant files

- `docs/CARRIER-RECOVERY-PLAN.md`
- `docs/IPV6-DATA-PLANE-PLAN.md`
- `tests/hardware/per.sh`
- `tests/hardware/http-speed.sh`
- `firmware/esp32-bridge/main/main.cpp`
- `tracker/firmware/components/lr2021_transport/src/lr2021_spi.cpp`
