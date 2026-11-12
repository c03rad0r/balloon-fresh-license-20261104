# Architecture

## Layers

```
FIPS node
  │  transports.lr2021
  ▼
Lr2021Transport (fork: src/transport/lr2021)
  │  submit(frame) / deliver(frame)
  ▼
fips-lr2021 link layer (fork: crates/fips-lr2021)
  │  fragment / reassemble / ACK / retransmit / dedup
  ▼
fips-lr2021 bridge protocol (A5 5A … CRC16)
  │  USB CDC
  ▼
RP2040 bridge (reference/fips-lr2021/firmware/rp2040-bridge)
  │  raw FLRC packets
  ▼
LR2021
```

The host owns the hard logic. The bridge owns the radio state machine and is
deliberately unaware of FIPS.

## Link frame

```
magic F1 50 | version/type | flags | src(4) | dst(4) |
epoch(2) | frame_seq(2) | frag_idx(1) | frag_count(1) |
payload_len(2) | payload | CRC32(4)
```

- `version=1`, `type` is DATA/ACK/NACK/BEACON.
- `src`/`dst` are 4-byte link IDs; `0xFFFFFFFF` is broadcast.
- `epoch` changes on restart, so a stale reassembly cannot collide with a new
  one.
- `frame_seq` identifies one FIPS frame.
- `frag_idx`/`frag_count` identify the fragment.
- CRC32 covers the header and payload.

With the validated E80/ESP32 128-byte radio packet the maximum fragment payload
is 104 bytes (20-byte link header + 4-byte CRC). A 1400-byte FIPS frame becomes
14 fragments. Other bridge profiles may use larger packets.

## Fragmentation and reassembly

- Sender splits each FIPS frame into `ceil(len / max_fragment_payload)` pieces.
- Receiver keys reassembly by `(src, epoch, frame_seq)`.
- A bitmap tracks received fragments.
- The final fragment's length gives the total frame length.
- Incomplete reassemblies expire after 500 ms.
- Completed frames are remembered for 5 s, so a retransmitted copy is ACKed but
  not delivered twice.

## ACK / ARQ

- Intermediate fragments do not immediately consume airtime with an ACK: the
  remainder of the batch is still arriving.
- An incomplete tail produces one NACK containing the cumulative bitmap. The
  sender immediately retransmits exactly the fragments missing from that map.
- A complete batch produces one completion ACK. Duplicate completed fragments
  also get an ACK but are never delivered again.
- ACKs are accepted only for the sender's own epoch, pending sequence and peer
  ID; a same-numbered transmission in the opposite direction cannot complete it.
- An ordinary partial ACK records progress without duplicating an in-flight
  batch. The configurable retry timer is the backstop for a missing final ACK or
  tail. The measured bench configuration uses 300 ms and 15 retries; protocol
  defaults are separate and configurable.
- The transport application queue is capped at 64 FIPS frames. A background
  scheduler submits one FIPS frame at a time and waits for final ACK or retry
  exhaustion before submitting the next. This prevents NACK repairs from
  starving behind new application bursts without blocking FIPS event handling.
- `packet_gap_ms` optionally spaces individual USB TX commands; the measured
  E80/ESP32 benchmark uses 20 ms. It defaults to zero and is not a TDMA slot.

The resulting stop-and-wait data path deliberately favors reliable completion
on one half-duplex air lane. Handshake frames are one or a few fragments, while
larger data frames use tail-NACK repair. A sliding window is a later measured
optimization, not a prerequisite for correctness.

## Bridge protocol

```
[A5 5A][type][len_lo][len_hi][payload][CRC16]
```

| Type | Direction | Purpose |
|---|---|---|
| HELLO | host → bridge | protocol version |
| HELLO_ACK | bridge → host | protocol, firmware, chip, capabilities |
| CFG | host → bridge | band, frequency, bitrate, power, sync, payload, relay |
| CFG_ACK | bridge → host | applied values or status |
| TX | host → bridge | one raw radio packet |
| RX | bridge → host | raw packet + RSSI/SNR/CRC |
| STAT | bridge → host | counters |
| EVT | bridge → host | reset/watchdog event |
| PING/PONG | both | liveness |

There is exactly one writer on the host side. The serial reader only reads; ACKs
and retransmits go through the writer channel. That removes the interleaved-frame
bug the old PTY bridge had.

## Radio configuration

CFG carries:

- band selector (for logging and profile defaults),
- frequency in Hz,
- FLRC bitrate,
- TX power in dBm,
- 4-byte sync word,
- raw packet size,
- relay flag,
- sub-GHz/HF path flag.

The bridge re-initializes the LR2021 and ACKs the values it actually applied.
The host refuses to start if they do not match, so a wrong band is a loud
failure rather than a silent deaf link.

### 511-byte packets on the E80/ESP32 bridge

The FLRC length field is 16-bit, but the default LR2021 FIFOs are only 256 bytes.
The bridge therefore:

- writes the FLRC payload length as two big-endian bytes;
- relocates TX and RX FIFOs to their documented 1024-byte regions with 9-byte
  `WriteRegMem32` commands (2-byte opcode + 3-byte address + 4-byte value);
- reads oversized RX FIFOs in bounded 128-byte SPI transactions.

The 868 MHz 128-byte configuration remains the validated baseline. The
2.4 GHz/511-byte experiment demonstrated 20/20 reciprocal smoke delivery but has
not passed its strict 100-packet gate; see `../docs/HANDOVER-2026-11-12.md`.

## Relay mode

The relay repeats each unique received packet once, with a short hash cache to
prevent an immediate loop. It does not decrypt or parse FIPS. It is a single
relay for the event; multi-relay scheduling is future work.

FIPS will see duplicated frames when a relay is present. The link layer drops
duplicate fragments; FIPS's own replay window also sees them, but the link-layer
dedup keeps the duplicate count away from the session layer.

## FIPS integration

The fork adds:

- `crates/fips-lr2021` — link layer, bridge, config, daemon and CLI.
- `src/transport/lr2021/mod.rs` — `Lr2021Transport`.
- `TransportType::LR2021` and `TransportHandle::Lr2021`.
- `transports.lr2021` in `TransportsConfig`.
- instantiation in `Node::create_transports`.

The transport is connectionless and advertises `reliable: false`: the link layer
does best-effort ARQ, but a frame can still be dropped after its retry budget.

## Daemon fallback

`fips-lr2021d` exposes a UDP socket to stock FIPS. It uses the same link layer
and bridge, so the radio path is identical. It exists so the event has a working
path even if the native transport build is blocked.

## Why not put the link layer in the bridge?

The RP2040 has enough RAM, but host-side logic is easier to test, easier to
update, and keeps the bridge small enough for the 64 KB STM32 path if that is
ever used. The bridge only needs to move packets and report metadata.
