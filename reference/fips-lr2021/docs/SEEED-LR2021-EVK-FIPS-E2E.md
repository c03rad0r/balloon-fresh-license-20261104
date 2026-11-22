# Seeed LR2021 EVK — two-node FIPS end-to-end run

This is the reproducible harness for the FIPS-over-FLRC test on two official
Seeed/Semtech LR2021 EVKs. It uses two isolated Docker containers so both FIPS
nodes can run on one host without network namespaces or root.

**Status (2026-11-22):** the harness was run over the LR2021 transport. The
native transport, Noise peer authentication and `ping6` work. Bulk UDP does
**not**: 100k–1M offered delivered 0.45–5.1 kbit/s at 94–99% loss, and station B
intermittently reset under load. TCP and SSH did not pass. The container/FIPS
data plane itself is validated over a UDP transport (handshake, ping, iperf3,
SSH); do not present those UDP self-test numbers as radio results.

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

## LR2021 run result (2026-11-22)

| Gate | Result |
|---|---|
| `lr2021` transport | up |
| Noise peer authentication | connected |
| `ping6` over `fips0` | 9–10/10, 0–10% loss, RTT 54–306 ms |
| iperf3 UDP 100k–1M (300 B datagrams) | 94–99% loss, 0.45–5.1 kbit/s received |
| iperf3 TCP | not achieved |
| SSH over `fips0` | not achieved |
| Sustained load | station B intermittently reset; cause not captured |

The one-frame ICMP path works; the two-frame bulk path is not usable with the
pinned link layer. The bridge also resets intermittently under FIPS load. This
is an open blocker; the harness is preserved for the next attempt, not a
throughput result.

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
`$FIPS_E2E_CONFIG_DIR/id_ed25519`.

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
| iperf3 UDP | Record offered vs delivered bitrate, loss and jitter for 100k–1M |
| iperf3 TCP | Record throughput and retransmits separately |
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
