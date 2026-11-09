# Hardware tests

These scripts assume the patched FIPS fork is built and both bridges answer
`fips-lr2021ctl hello`.

The bench is in the EU. Defaults are **`eu868`** and a fixed 128-byte radio
payload, which is the measured stable setting for the current S3/C3 pair.
Do not use `us915` or `us2400` here.

```bash
export FIPS_DIR=/path/to/fips-fork
export SERIAL_A=/dev/serial/by-id/...s3...
export SERIAL_B=/dev/serial/by-id/...c3...

BAND=eu868 RADIO_PAYLOAD=128 ./per.sh 20
```

`per.sh` starts the echo responder, sends a bounded burst, prints the link-layer
delivery count and both device status counters, and fails unless every transmitted
payload was accepted **and every accepted payload was unique**. This prevents
retransmissions from being mistaken for distinct successful frames. To test the
reverse direction, swap `SERIAL_A` and `SERIAL_B` and set `DIRECTION=B_TO_A`.

## Strict ping gate

A successful one-way ping is not enough. Before any HTTP, SSH or ContextVM/MCP
measurement, both directions must pass with 0% loss:

```bash
NETNS_A=fips-lr-a NETNS_B=fips-lr-b \
IP_A=fd99:3df2:2781:3573:7113:64b4:f4e8:df04 \
IP_B=fdf6:54a7:a4e3:59f:e36e:cd9e:d101:8c08 \
COUNT=50 INTERVAL=2 ./ping-gate.sh
```

Use `REKEY_WAIT=130 ./ping-gate.sh` to repeat the gate after at least one rekey
cycle. A nonzero result blocks benchmarking. Record the ping logs when it fails.

For a sample of each direction:

```bash
DIRECTION=A_TO_B RADIO_PAYLOAD=128 ./per.sh 100 104

DIRECTION=B_TO_A SERIAL_A=<c3> SERIAL_B=<s3> \
  RADIO_PAYLOAD=128 ./per.sh 100 104
```

## HTTP/radio-only throughput

The HTTP meter runs **inside a FIPS network namespace**, checks that ping to the
far FIPS address has 0% loss, and refuses otherwise. Start a small HTTP server
bound to the peer's FIPS IPv6 address first.

```bash
NETNS=fips-lr-a \
PING_IP=fdf6:54a7:a4e3:59f:e36e:cd9e:d101:8c08 \
URL=http://[fdf6:54a7:a4e3:59f:e36e:cd9e:d101:8c08]:18080/fips-128k.bin \
RUNS=3 ./http-speed.sh
```

Use 128 KiB and 1 MiB files first. Large public-CDN or MCP speed tests are only
a downstream end-to-end check: the measuring process must have no Wi-Fi/Ethernet
fallback route, or its result does not demonstrate the LR2021 path. The full
metric and ContextVM/MCP sequence is in
[`../../docs/IPV6-DATA-PLANE-PLAN.md`](../../docs/IPV6-DATA-PLANE-PLAN.md),
Phase 4b.

`soak.sh` remains available for long liveness checks once the link passes the
radio and ping gates. Record measured values, firmware versions and counters in
`../../docs/RESULTS.md`; never record a speed number without its test conditions.
