# Ping reliability plan — from working PER bursts to stable IPv6

Written 2026-11-09. Owner checklist for making FIPS IPv6 reliable before HTTP,
SSH or ContextVM/MCP speed measurements.

## Current state

- S3/E80 firmware: `0.4.18`; NiceRF C3: `0.5.8`; both report `chip=0x1801`.
- 128-byte air packets pass controlled PER: 100/100 in each direction.
- FIPS Noise peers and both end-to-end XK sessions establish.
- IPv6 ping is still unreliable. Best observed:
  - CSMA-only: 2/3 replies in each direction.
  - A later default run: A→B 0/5, B→A 3/5.
  - Optional TDMA slots: one reply at 159 ms but worse delivery, so disabled.
- HTTP benchmark correctly refuses to run unless its ping preflight is 0% loss.
- SSH has reached `SSH2_MSG_SERVICE_ACCEPT` but has not completed a remote command.

## Why it is unreliable

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
- [ ] Prevent ACK/retry traffic from overlapping the next queued data burst.
- [ ] Serialize one coherent message/fragment batch before yielding the air.
- [ ] Apply the quiet interval after receiving, not only before our own TX.
- [ ] Keep optional fixed slots disabled unless they beat CSMA on unique delivery.

## Phase 4 — acceptance gates

- [ ] 100/100 unique PER round trips each direction: `per delivered=100`,
      not merely repeated echo transmissions.
- [ ] Zero unexplained `bad magic`/`bad crc32` over 100 packets each way.
- [ ] Both FIPS peers connected and both XK sessions established.
- [ ] 50/50 IPv6 replies each direction with sequential requests.
- [ ] A second 50/50 run after at least one session rekey.
- [x] No ping-gate bypass in benchmark scripts (`ping-gate.sh` requires 0% in
      both directions; `http-speed.sh` refuses without a 0%-loss preflight).

Only then:

- [ ] 128 KiB HTTP over the radio-only path, 3 runs.
- [ ] 1 MiB HTTP over the radio-only path, 3 runs.
- [ ] Record TTFB, total, goodput, loss and counters.
- [ ] SSH command returns `RADIO_SSH_OK` over the FIPS address.
- [ ] Optional ContextVM/MCP public-internet run in an isolated namespace.
- [ ] Compare against the local radio-only baseline; do not call an unverified
      CDN result a bridge improvement.

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
