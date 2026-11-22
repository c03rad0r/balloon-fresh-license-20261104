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
