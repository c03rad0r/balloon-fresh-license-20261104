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

## Measured outcome, 2026-11-11/12 — partial, not accepted

The 2.4 GHz experiment reached working 511-byte RF delivery but did **not** clear
the strict link gate, so no FIPS, HTTP or maximum-throughput claim is valid.

What was measured:

- The 128-byte 2.4 GHz control passed 20/20 in both directions, proving HF
  carrier operation and isolating the fault to longer packets.
- The original 511-byte path returned correct-length frames with bad FIPS
  headers. The extended-FIFO setup commands were malformed: they used a 4-byte
  address where `WriteRegMem32` requires 3 address bytes. Correcting the four
  commands changed the first received bytes to the expected `F1 50`.
- Reading a 511-byte RX FIFO in one SPI transaction still corrupted the later
  payload. Bounded 128-byte FIFO reads fixed that path for the tested bursts.
- With the corrected register setup and bounded reads, reciprocal 20-packet
  tests passed 20/20 with zero link errors at 511 bytes and CR 3/4.
- Strict 100-packet CR 3/4: both directions delivered 100/100 unique payloads,
  but recorded 1 and 6 host-link CRC/framing errors respectively.
- Strict 100-packet CR-none: one direction delivered 100/100 with 12 link
  errors; the reverse delivered 99/100 with 13 link errors. A subsequent run
  also failed to start delivering on one direction.
- No 50/50 IPv6 gate, XK test, HTTP transfer, or validated 2.6 Mbps application
  goodput has been completed at 2.4 GHz.

Engineering decisions from this outcome:

1. Keep CR 3/4 as the default. CR-none is compile-time opt-in because it showed
   more link errors and no completed application benchmark.
2. Keep the bounded 128-byte SPI RX read and corrected extended-FIFO setup.
3. Do not claim the 20-packet result as stability; the strict 100-packet gate is
   still open.
4. Do not continue by adding FEC or TDMA. First resolve residual radio/link
   errors and complete the FIPS/IPv6/HTTP gates.
5. Firmware source now versions default-profile S3 `0.4.30` / C3 `0.5.20`. The
   bench was last flashed with the CR-none experiment (`0.4.29`/`0.5.19`), so
   source HEAD and the physical bench state are deliberately distinguished.

## Stage A — preserve validated work

- [x] PR #544 merged the validated reference work into
      `felixfelix-bot/balloon-fresh` default `master` (`ca8fbead`), with
      host-tests, pcb-pipeline and test all green.
- [x] PR #1 merged `balloon-lr2021` into fork `c03rad0r/fips` default `master`
      (`482ee781`). No upstream `jmcorgan/fips` action; that repository has no
      configured checks, so the recorded local 25+4 host suites were required.
- [x] Committed pin and vendored patch match validated host `8155e5ff`.
- [x] Non-secret evidence remains at
      `/home/archipelago/fips-results/2026-11-10/`.

## Stage B — make 511 bytes safe

- [x] Replace the 255-byte ESP32 RX and USB payload buffers with a bounded
      511-byte-capable representation.
- [x] Test 255-, 256-, 511-, and over-limit inputs, including payload
      preservation, zero padding and host USB framing.
- [x] Confirm LR2021 configuration uses a 16-bit FLRC length field without
      narrowing; bridge CFG metadata already carries an unsigned 16-bit size.
- [x] Run all host tests and both ESP-IDF target builds
      (43/43 driver tests, 27/27 FIPS LR2021 tests, 4/4 native transport tests;
      both default images link). The broader legacy `make test-unit` run is 93
      passed, one unrelated dependency failure because `mbedtls/sha256.h` is
      absent from the host environment; this is not recorded as a green full-suite
      result.
- [x] Obtain required orchestrator flash approval and device ownership/locks.
- [x] Stop daemon serial users before every bridge probe/flash; use by-id
      devices, not guessed `/dev/ttyACM*` numbers. Locks were released after
      each session.
- [x] Flash versioned images and record HELLO responses. The final physical
      bench state is the CR-none experiment S3 `0.4.29` / C3 `0.5.19`; the
      default-profile source at HEAD is `0.4.30` / `0.5.20` and has not been
      flashed.

## Stage C — qualify EU 2.4 GHz

- [x] Verify HF carrier support on the actual S3/E80 and NiceRF C3 hardware:
      a 128-byte EU2400 control passed 20/20 in both directions.
- [x] Apply the 511-byte candidate and confirm CFG ACK frequency, rate and payload
      on both nodes.
- [x] Run bounded 20-packet smoke PER in each direction with unique sequences:
      reciprocal 20/20 and zero link errors after correcting FIFO register
      encoding and bounding SPI RX reads.
- [ ] Require reciprocal 100/100 with zero unexplained CRC/framing errors before
      FIPS tests. **FAILED:** one CR 3/4 run saw 1 and 6 link errors; CR-none saw
      12 and 13, with a 99/100 delivery in one direction.
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

- [x] Update architecture, onboarding, results, pin/patch and hardware runbook.
      The shareable overview is `HANDOVER-2026-11-12.md`.
- [x] Re-run driver, FIPS link/native and SSOT checks for the tested source.
- [ ] Merge only a validated speed profile to `master`. Current merge is the
      explicit experimental handover: default build retains CR 3/4; CR-none is
      opt-in and remains unaccepted for performance claims.
- [x] Preserve the failing measurements rather than presenting 20-packet success
      as stable.
