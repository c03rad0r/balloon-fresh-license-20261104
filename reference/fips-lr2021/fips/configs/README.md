# FIPS configs

`*.yaml` profiles are **transport snippets**: merge the `transports.lr2021`
block into your own `fips.yaml`.

`us915-node-a.yaml` and `us915-node-b.yaml` are complete two-node examples for
the bench. Replace `REPLACE_WITH_NSEC` with a real nsec, or use the identity
file form your deployment already uses.

Both ends must agree on `band`, `radio_payload`, `mtu` and `sync_word`, and must
use different `local_id` values.

## Seeed LR2021 EVK at 1 Mbaud

`seeed-eu2400-node-a.example.yaml` and `seeed-eu2400-node-b.example.yaml` are
complete two-node templates for the official Seeed/Semtech EVKs on their stock
USB-C path. That path is the nRF54L15 UART20 through the SAMD11 bridge, whose
maximum rate is **1 Mbaud**; the 2 Mbaud profiles above are for other bridge
hardware. The EVK templates use `radio_payload: 255` and EU 2.4 GHz.

Copy the templates to a private directory, replace the nsec and peer npub, and
set each station's stable `/dev/serial/by-id/...` path. Do not commit real keys.

The LR2021 FLRC driver accepts payloads up to 511 bytes, but this bridge's
511-byte multi-frame path was not stable in bench tests, and the harmonized
bench rules require a **≥40 ms gap** between radio packets longer than 256
bytes. Keep `radio_payload: 255` for FIPS until that path is separately
validated.

## Half-duplex link tuning (validated 2026-11-22)

The EVK link is half-duplex. Two nodes that both transmit whenever they have
data collide, and the resulting ACK loss makes FIPS retransmit continuously.
The validated profiles set:

```yaml
    mtu: 512
    radio_payload: 255
    ack_timeout_ms: 200
    ack_delay_ms: 10
    tx_pacing_ms: 2
    master: true      # node A; node B must be false
```

- `master: true` may initiate and poll. Exactly one end must be `false`; the
  slave transmits only after receiving a frame from the master.
- `ack_delay_ms` holds a _partial_ message ACK so a fragment burst can finish.
  A complete message is ACKed immediately.
- `tx_pacing_ms` spaces host-to-bridge frames so the bridge's 32-frame radio
  queue cannot overflow.

Both ends must run the same FIPS revision (`seeed-halfduplex`), because the
link frame set gained a poll kind.
