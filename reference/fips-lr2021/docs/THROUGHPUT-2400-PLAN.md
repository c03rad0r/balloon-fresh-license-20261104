# EU 2.4 GHz / 511-byte throughput maximization plan

Written 2026-11-10. This is the active checklist for the next throughput
experiment. It does not rewrite the previously verified 868 MHz results.

## Baseline and decision record

Measured with `c03rad0r/fips@8155e5ff` on S3 `0.4.22` / C3 `0.5.12`:

- `eu868`, 868.1 MHz, FLRC 650 kbps, 14 dBm, sync `2dd4d4b2`.
- 128-byte air packets; 104 bytes of application data after the 20-byte link
  header and 4-byte CRC.
- `packet_gap_ms: 20`, `ack_timeout_ms: 300`, `max_retries: 15`, randomized
  8–16 ms firmware CSMA guard, one asynchronous application frame in flight.
- 50/50 IPv6 replies each direction, before and after a real rekey.
- Three 128 KiB HTTP runs; mean 0.0070 Mb/s.
- Three 1 MiB HTTP runs (1275–1313 s); mean 0.0065 Mb/s.
- Public-key `RADIO_SSH_OK`, exit 0.

Why it was slow: 1 MiB needs about 10,082 104-byte fragments. The 20 ms host
pacing alone contributes about 202 s; CSMA guards, ACK turnarounds, retries,
and TCP/IP/FIPS overhead account for the remainder. The baseline was chosen for
delivery correctness, not speed.

### Decisions

1. Merge this verified baseline before attempting the speed experiment.
2. Use `eu2400`, 2440 MHz, FLRC 2600 kbps, 12 dBm, sync `2dd4d4b2`, and 511-byte
   radio packets for the speed candidate. Never select `us2400` on this bench.
3. Support 511 bytes in firmware explicitly. Current `main/main.cpp` has 255-byte
   RX and USB payload buffers, so an unmodified image cannot be qualified at
   511 bytes merely by changing YAML.
4. Do not advertise raw 2.6 Mb/s as HTTP goodput. Record measured goodput and
   the percentage of raw FLRC capacity separately.
5. Change pacing and retry settings only after 511-byte delivery is proven.
   Retain the corrected tail-NACK/provenance/scheduler fixes, RX priority and
   receive-in-progress deferral. Do not introduce TDMA or FEC for this test.
6. Keep a speed experiment off `master` if it regresses any mandatory gate.

Change these decisions only with measurements on the same physical carrier pair
and explicit reconciliation against the baseline, including HF carrier support.

## Stage A — preserve validated work

- [ ] PR the validated reference work into `felixfelix-bot/balloon-fresh` default
      `master`; wait for required CI, merge only when green.
- [ ] PR `balloon-lr2021` into the fork `c03rad0r/fips` default `master`; merge
      only when green. No action against `jmcorgan/fips`.
- [ ] Confirm the committed pin and vendored patch match the validated host.
- [ ] Preserve the non-secret evidence archive at
      `/home/archipelago/fips-results/2026-11-10/`.

## Stage B — make 511 bytes safe

- [ ] Replace the 255-byte ESP32 RX and USB payload buffers with an explicit
      511-byte-capable bounded representation.
- [ ] Test 255-, 256-, 511-, and over-limit inputs, including exact payload
      preservation, zero padding and host USB framing.
- [ ] Confirm LR2021 radio configuration and `CfgAckPayload` handles 511 without
      narrowing/truncation in the actual driver.
- [ ] Run all host tests and both ESP-IDF target builds.
- [ ] Obtain required orchestrator flash approval and device ownership/locks.
- [ ] Stop daemon serial users before any bridge probe/flash; use by-id devices,
      not guessed `/dev/ttyACM*` numbers.
- [ ] Flash versioned S3/C3 images and record hashes/HELLO responses.

## Stage C — qualify EU 2.4 GHz

- [ ] Verify HF carrier support on the actual S3/E80 and NiceRF C3 hardware,
      not merely that the LR2021 chip reports a version.
- [ ] Apply exactly this baseline speed candidate on both nodes:

      ```yaml
      band: eu2400
      frequency_hz: 2440000000
      bitrate_kbps: 2600
      tx_power_dbm: 12
      radio_payload: 511
      sync_word: "2dd4d4b2"
      ```

- [ ] Confirm CFG ACK frequency/rate/payload on both nodes.
- [ ] Run bounded 20-packet smoke PER in each direction with unique sequences.
- [ ] Require reciprocal 100/100 payloads with zero unexplained CRC/framing
      errors before FIPS tests.
- [ ] Require both authenticated XK sessions and 50/50 IPv6 replies each way.
- [ ] If any gate fails, record it and do not label a fallback result as a
      511-byte or 2.6 Mb/s success.

## Stage D — maximize passing throughput

Start with `packet_gap_ms: 20` and `ack_timeout_ms: 300` to isolate the new
radio profile, then change one variable at a time.

- [ ] Sweep host pacing: 10, 5, 2, 0 ms.
- [ ] Sweep retry backstop if needed: 200, 100 ms.
- [ ] Retain only settings that preserve the strict 50/50 bidirectional gate.
- [ ] If the 8–16 ms firmware guard dominates, compare a versioned shorter-guard
      build while retaining RX draining and receive-in-progress deferral.
- [ ] Require 1000-byte IPv6 payloads in both directions on the selected config.
- [ ] Keep TDMA off; leave Wirehair/FEC out of this experiment.

## Stage E — authoritative HTTP comparison

Use exactly the same host fixture, deterministic files, isolated namespaces and
route constraints as the EU-868 baseline. No LAN/WAN result is a substitute.

- [ ] 128 KiB, A→B, three runs.
- [ ] 128 KiB, B→A, three runs.
- [ ] 1 MiB, A→B, three runs.
- [ ] 1 MiB, B→A, three runs.
- [ ] Record exact response lengths/status, TTFB, total time, per-run and mean
      goodput, CRC/retry/drop counters and firmware/config hashes.
- [ ] Report Mb/s and percentage of raw 2.6 Mb/s FLRC capacity.
- [ ] If transfers are short enough for meaningful steady-state measurement, add
      a bounded larger transfer without relaxing the per-run checks.
- [ ] Optional MCP/WAN remains unrun unless a real MCP tool and isolated routed
      fixture are available; do not manufacture a comparison over LAN.

## Stage F — integrate

- [ ] Update architecture, onboarding, results, pin/patch and hardware runbook.
- [ ] Re-run all host tests, `param_ssot_check.py` and shell syntax checks.
- [ ] PR/merge only the validated speed configuration and evidence to `master`.
- [ ] If the experiment regresses, merge the baseline only and preserve the
      failing measurements on the experiment branch.
