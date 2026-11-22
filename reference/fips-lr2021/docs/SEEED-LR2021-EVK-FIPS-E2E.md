# Seeed LR2021 EVK — two-node FIPS end-to-end run

This is the reproducible harness for the FIPS-over-FLRC test on two official
Seeed/Semtech LR2021 EVKs. It uses two isolated Docker containers so both FIPS
nodes can run on one host without network namespaces or root.

**Status (2026-11-22, updated):** the half-duplex link now works. With the
`seeed-halfduplex` FIPS revision and the tuning below, `ping6` is 5/5 at 0%
loss, UDP at 10k and 25k offered is **0% loss** (24.9 kbit/s delivered at 25k),
50k is 3.4% loss, a 10-minute 25k soak lost 0.08%, and SSH completes over
`fips0`. A 4 KiB raw TCP transfer completes in ~4.5 s. `iperf3` **TCP bulk** still reports 0 bytes and is not a
usable throughput result. The earlier 94–99% UDP loss was caused by per-fragment
ACK collisions and a vendor modem panic on a stale RX IRQ; both are fixed.

The container/FIPS data plane is also validated over a UDP transport
(handshake, ping, iperf3, SSH); do not present those UDP self-test numbers as
radio results.

## Prerequisites

1. Both EVKs flashed with the direct-FLRC bridge at 1 Mbaud:

   ```bash
   make seeed-bridge-flrc-build BRIDGE_BAUD=1000000
   make seeed-bridge-flrc-flash BRIDGE_BAUD=1000000 PROBE='<station-A-probe>'
   make seeed-bridge-flrc-flash BRIDGE_BAUD=1000000 PROBE='<station-B-probe>'
   ```

2. A private config directory containing `node-a.yaml` and `node-b.yaml`. Start
   from `fips/configs/seeed-eu2400-node-a.example.yaml` and
   `...node-b.example.yaml`, replace the nsecs and peer npubs, and keep the
   directory out of git. The harness defaults to `build/fips-e2e/`.

3. Docker with permission to add `NET_ADMIN` and map character devices. The
   image is built once:

   ```bash
   cd build/fips-e2e
   cp <isolated-build>/release/fips .
   cp <isolated-build>/release/fipsctl .
   docker build -t seeed-fips-e2e:latest .
   ```

   Build the FIPS binaries from the pinned checkout in an isolated
   `CARGO_TARGET_DIR`; a shared target directory can reuse artifacts from a
   different checkout.

4. `iperf3` and `ping6` are available inside the image (installed by the
   Dockerfile). `openssh-server` is installed for the optional SSH gate.

## Link tuning (validated)

| Setting | Value | Why |
|---|---|---|
| `mtu` | 512 | keeps a FIPS frame to about three radio fragments |
| `radio_payload` | 255 | validated bridge payload |
| `ack_timeout_ms` | 200 | covers the 10 ms ACK delay plus turnaround |
| `ack_delay_ms` | 10 | partial-message ACK only; complete messages ACK immediately |
| `tx_pacing_ms` | 2 | matches the bridge's inter-frame guard; no queue overflow |
| `max_retries` | 5 | bounded recovery |
| `master` | `true` on A, `false` on B | only one end initiates on a half-duplex link |

Both nodes must run the `seeed-halfduplex` FIPS revision. The link frame set
gained a poll kind, so a mismatched peer will not interoperate.

## LR2021 run result (2026-11-22)

| Gate | Result |
|---|---|
| `lr2021` transport | up |
| Noise peer authentication | connected |
| `ping6` over `fips0` | 5/5, 0% loss, RTT 66–1746 ms |
| iperf3 UDP 10k offered | 0% loss, 9.1 kbit/s |
| iperf3 UDP 25k offered | 0% loss, 24.9 kbit/s (20 s) |
| iperf3 UDP 50k offered | 3.4% loss, 34.6 kbit/s (20 s, queue tail) |
| iperf3 UDP 100k offered | 46% loss, 36.3 kbit/s delivered |
| 10-minute UDP soak, 25k | 0.08% loss (5/6251), no reset |
| Raw TCP | 4 KiB in ~4.5 s (~7 kbit/s) |
| SSH over `fips0` | `SSH_OVER_FIPS_OK` |
| iperf3 TCP bulk | 0 bytes over 30 s; not usable |
| Reset stability | both stations stayed at boot #2 through 25k/50k/100k tests |

The stable operating point is **25 kbit/s at 0% loss**; ~35 kbit/s is the
approximate ceiling before loss rises. The limiter is per-message half-duplex
turnaround and FIPS queuing, not CRC or radio loss.

## Run

The caller must hold the external board lock. The script maps station A to
`/dev/ttyACM0` and station B to `/dev/ttyACM1` inside the containers:

```bash
FIPS_E2E_CONFIG_DIR="$PWD/build/fips-e2e" \
SERIAL_A=/dev/ttyACM0 SERIAL_B=/dev/ttyACM1 \
tests/hardware/run_fips_e2e.sh
```

Set `KEEP=1` to leave the containers running for inspection and `RUN_SSH=1`
to run the SSH gate. `SSH_KEY` defaults to
`$FIPS_E2E_CONFIG_DIR/id_ed25519`. `IPERF_RATES` defaults to `10k 25k 50k`;
`IPERF_SECONDS` and `IPERF_TIMEOUT` control each run and its timeout.

Each container runs with:

- `--network none` — no host or Docker network can create a false positive;
- one serial device only — each FIPS node owns one radio;
- `CAP_NET_ADMIN` and `/dev/net/tun` — for `fips0`;
- the private config mounted read-only at `/config`.

## Expected gates

| Gate | Pass condition |
|---|---|
| FIPS transport | `fipsctl show transports` reports `lr2021` `up` |
| Peer auth | `fipsctl show peers` contains the peer npub with `connectivity: connected` |
| ping6 | 10/10 replies over `fips0`, 0% loss |
| iperf3 UDP | 10k and 25k offered: 0% loss. 50k: record the loss/queue tail |
| iperf3 TCP | **Not a gate on this link**: bulk reports 0 bytes. Record raw TCP (4 KiB) separately |
| SSH | `echo SSH_OVER_FIPS_OK` over the peer's `fips0` address |
| Soak | No resets, no unexplained drops, counters reconciled |

The host UART is 1 Mbaud. Expect aggregate FIPS application throughput well
below 1 Mbit/s; do not report the raw FLRC 2.6 Mbit/s PHY rate as throughput.

## UDP self-test (validated)

A separate pair of containers on a Docker bridge network, using
`transports.udp`, validated the non-radio path:

- peer authenticated;
- `ping6` 5/5, 0% loss, ~1.3 ms RTT;
- `iperf3` UDP 1 Mbit/s offered, 1.00 Mbit/s delivered, 0% loss;
- `iperf3` TCP ~755 Mbit/s (Docker UDP path, not radio);
- SSH returned `SSH_OVER_FIPS_OK` after fixing container key ownership.

These numbers validate the harness and the FIPS data plane only. They are not
LR2021 results.

## Security and cleanup

- Never commit the private `node-*.yaml` files, nsecs or generated SSH keys.
- The committed `*.example.yaml` files contain placeholders only.
- The harness removes both containers on exit unless `KEEP=1`.
- Restore both EVKs to a non-transmitting image after testing, or leave the
  documented FLRC bridge with no host traffic.
