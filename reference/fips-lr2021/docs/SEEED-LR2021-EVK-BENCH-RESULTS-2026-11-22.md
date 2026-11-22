# Seeed LR2021 EVK bench results — 2026-11-22

**Hardware:** two official Semtech/Seeed LR2021 LoRa Plus Evaluation Kits
**Stations:**

| Station | CMSIS-DAP probe | Serial |
|---|---|---|
| A | `7CDB5271` | `/dev/serial/by-id/usb-Seeed_Studio_Seeed_Studio_XIAO_nrf54_CMSIS-DAP_7CDB5271-if02` |
| B | `A8022EF0` | `/dev/serial/by-id/usb-Seeed_Studio_Seeed_Studio_XIAO_nrf54_CMSIS-DAP_A8022EF0-if02` |

**Software:** local bridge branch `feat/seeed-nrf54l15-bridge`, based on
`bd33ef0e`, plus Zephyr 4.4.0 and Zephyr SDK 1.0.1 from the pinned USP
workspace.

> These are bench measurements from the two attached EVKs. Raw logs are local
> build artefacts under `reference/fips-lr2021/build/` and are intentionally not
> committed. No FIPS-over-radio result or 2.6 Mbit/s application-throughput
> claim is made.

## USB/UART host-path measurement

The loopback bridge was built, flashed and measured with 255-byte payloads and a
four-frame outstanding window. H→device and device→H payload values are equal
because the firmware echoes each packet.

| Station / baud | Payload each direction | Wire each direction | Delivered | Loss |
|---|---:|---:|---:|---:|
| A / 115200 | 87.163 kbit/s | 89.968 / 91.655 kbit/s | 217/218 | 1 |
| A / 230400 | 160.540 kbit/s | 165.362 / 168.773 kbit/s | 397/398 | 1 |
| A / 460800 | 288.007 kbit/s | 296.330 / 302.739 kbit/s | 710/711 | 1 |
| A / 921600 | 468.765 kbit/s | 481.633 / 492.712 kbit/s | 1155/1155 | 0 |
| A / 1000000 | 495.022 kbit/s | 508.611 / 520.308 kbit/s | 1219/1219 | 0 |
| A / 1000000 clean reflash | 481.962 kbit/s | 495.192 / 506.582 kbit/s | 1187/1187 | 0 |
| A / 1000000 final alias build | 495.299 kbit/s | 508.896 / 520.599 kbit/s | 1220/1220 | 0 |
| B / 1000000, 10 s | 495.883 kbit/s | 509.496 / 521.213 kbit/s | 2437/2437 | 0 |

At 1 Mbaud:

- aggregate framed payload: approximately **0.99 Mbit/s**;
- aggregate wire traffic: approximately **1.03 Mbit/s**;
- device counters: no CRC errors, drops, timeouts or resets;
- loopback `HELLO_ACK`: protocol 1, firmware 0.1.0, chip 0, capabilities `0x0008`.

A larger window (8) reached the same rate; windows 16 and 32 exhausted the
current receive path. The stable documented window is 4.

### Why this bounds FIPS throughput

The nRF54L15 standard UART used by the stock XIAO USB/debugger path tops out at
1 Mbaud. The XIAO nRF54L15 has no native USB peripheral; its USB-C connector is
the SAMD11 CMSIS-DAP bridge. Therefore this path cannot carry a 2.6 Mbit/s FIPS
stream. 2.6 Mbit/s is the raw FLRC PHY rate and excludes coding, framing,
preamble, ARQ, USB/UART and FIPS overhead.

The theoretical raw serial capacity at 1 Mbaud is 100,000 B/s (800 kbit/s user
data) per direction. The measured aggregate framed payload is about 0.99 Mbit/s
across both directions. A future FIPS implementation must be measured; it will
be lower.

## Stock FLRC PER baseline

Stock 866.5 MHz FLRC-2600 CR-3/4 +14 dBm, 255-byte payload, 200 ms cadence.
Receiver and transmitter were reset with the receiver first. RSSI was −79 dBm in
the steady run; no CRC errors were reported.

| Run | Completed RX series | PER by series |
|---|---:|---|
| First cold attempt | 3 | 38%, 0%, 0% |
| Second cold attempt, 12 s RX warm-up | 3 | 92%, 0%, 0% |
| Uninterrupted follow-up | 4 | 0%, 0%, 0%, 0% |

The first series after a cold reset is reproducibly lossy even while TX reports
100 successful transmissions; four subsequent uninterrupted series were
100/100. Treat this as an unresolved startup/warm-up artifact, not as steady RF
PER. Do not average it away. Raw logs:

- `build/radio-baseline/per-rx.log`, `per-tx.log`
- `build/radio-baseline/per-rx-clean.log`, `per-tx-clean.log`
- `build/radio-baseline/per-rx-steady.log`, `per-tx-steady.log`

## Stock FLRP bulk baseline

Stock SubGig, crypto/MIC enabled, 20 KiB requested transfer size, at close bench
range. Six initiator periods produced at least five transfers in each direction:

| Direction | Successful callbacks | Packet stats | RSSI / SNR |
|---|---:|---|---|
| A(initiator)→B(slave) | 6 TX / 6 RX | `74/0/0` every transfer | −78/−79 dBm, 13 dB |
| B(slave)→A(initiator) | 5 TX / 5 RX | `74/0/0` every transfer | −78/−79 dBm, 13 dB |

- Reported application size: `20482` bytes (20 KiB plus framing counter).
- No failed TX/RX callbacks were logged.
- The stock log timestamps the initiation event, but completion lines have no
  timestamp. **Whole-transfer goodput is therefore not measurable from the
  stock logs** without additional host/firmware instrumentation. Do not
  substitute the 20-second trigger interval or the FLRC raw rate.
- Raw logs: `build/radio-baseline/flrp-initiator.log`,
  `build/radio-baseline/flrp-slave.log`.

## Direct-FLRC bridge (2026-11-22)

The loopback was replaced with a raw LR2021 FLRC backend using the official
Semtech RAC transaction API. The host framing, link-layer ARQ/reassembly and
FIPS transport are unchanged. Both stations report protocol 1, firmware 0.2.0,
chip `0x0118` (LR2021 1.24) and capabilities `0x000a`.

Test profile: EU 2.4 GHz, 2440 MHz, FLRC 2600 kbps, CR 3/4, 12 dBm, 255-byte
radio payload, 1 Mbaud host UART. Each row is a 100-message link-layer PER run.

| Direction | App payload | Sent | Delivered | Loss | RSSI |
|---|---:|---:|---:|---:|---:|
| B→A | 64 B | 100 | 100 | 0% | −20.6 dBm |
| A→B | 64 B | 100 | 100 | 0% | −20.6 dBm |
| B→A | 255 B | 100 | 100 | 0% | −20.6 dBm |
| A→B | 255 B | 100 | 100 | 0% | −20.6 dBm |

The final four runs used the isolated pinned link layer and the 2 ms inter-frame
guard. RSSI varied between about −16 and −21 dBm as the bench hardware was moved;
the final runs were all near −20.6 dBm.

Soak image: **85,124 bytes**, SHA256
`52308113d589b422728961622f8b87f79a38cb7fd9720ad994f978dbcd86926e`.
Final image after the 2 ms inter-frame guard and reset diagnostics:
**85,516 bytes**, SHA256
`fb781d1a2a5becfac8236b556b6492deea94feecc32cc3cf1a10dfa41fa29f37`
(built from the bridge working tree before the follow-up commit).

A 255-byte application message is two radio frames at `radio_payload: 255`.
Two faults were found and fixed:

1. The bridge TX queue was four packets deep; the host delivered fragments faster
   than the radio drained them. Raising it to 16 removed over 1,000 drops per
   short run.
2. Back-to-back fragments could start before the peer re-armed RX. With the
   isolated pinned link layer, 255-byte traffic was 69/100 without a guard. A
   **2 ms inter-frame transmit guard** made it 100/100 in both directions.

No CRC errors or TX timeouts were recorded in the final runs.

### 511-byte FLRC payloads

The LR2021 driver documents an FLRC payload range of **6–511 bytes**, and the
radio FIFO is 1023 bytes, so the hardware can send 511-byte packets. We raised
the bridge limit to 511 and tested it. Single-frame traffic (480-byte
application payload) passed only intermittently, and multi-frame 500/1000-byte
traffic intermittently reset the MCU or stalled the sender despite a 16 KB main
stack and 4 KB system workqueue stack. The repository's harmonized-bench rules
also require a **≥40 ms gap** between packets longer than 256 bytes.

The production bridge is therefore capped at 255 bytes. 511 is a real hardware
capability but not a validated FIPS configuration. Even if stabilized, it
cannot lift FIPS above the ~1 Mbit/s host-UART ceiling; it only reduces radio
framing/ACK overhead.

## FIPS over the direct-FLRC bridge (2026-11-22, updated)

Two EVKs run as isolated Docker containers (`--network none`, one serial device
each, `CAP_NET_ADMIN` for `fips0`). Config: 1 Mbaud, EU 2.4 GHz,
`radio_payload: 255`, link `mtu: 512`, `ack_timeout_ms: 200`,
`ack_delay_ms: 10`, `tx_pacing_ms: 2`, `max_retries: 5`, node A `master: true`
and node B `master: false`.

The FIPS revision is `78b76d45c71f443099ff7bc5f89ecab4260495d5` on
`c03rad0r/fips` branch `seeed-halfduplex`. Both ends must run it: the link frame
set gained a poll kind.

### Reset root cause and fix

The earlier "intermittent reset" was **not** a Zephyr fatal, watchdog or
brownout. A persistent `.noinit` boot record and the modem crash log showed a
vendor planner panic: `rp_irq_get_status:1036` processed a stale `RX_DONE`
while the current task was `TX_FLRC`, so `rp_get_pkt_payload` returned
`ID_ERROR` and the panic macro rebooted the MCU. A second path was an oversize
RX length in `rp_get_pkt_payload`.

Fixes in the bridge:

- clear the radio IRQ status before every RX/TX submit, so a stale `RX_DONE`
  cannot be attributed to a TX task;
- give the RAC a 511-byte RX buffer and drop frames above the 255-byte
  application payload in the callback, so a corrupt length cannot trip the
  RAL/panic path;
- keep a 100 ms RX window and abort to TX only after 5 ms of radio silence, so
  a fragment burst is never truncated.

The record is readable with `fips-lr2021ctl diag` or over SWD. Both stations
stayed at **boot #2** through 20 s each at 25k/50k/100k offered; the old build
had reset 14 times in a comparable run.

### Link-layer changes

The EVK medium is half-duplex. The previous link layer ACKed every fragment
immediately and allowed many messages in flight, so data and ACKs collided:
94–99% UDP loss. The revised link layer:

- adds a link poll and a **master/slave role**; only the master initiates, the
  slave transmits after receiving a frame;
- ACKs a **complete** message immediately and delays only a partial-message
  ACK by 10 ms;
- keeps **one link message in flight**, paces host→bridge frames at 2 ms, and
  gives ACKs priority over queued data;
- logs frames, ACKs, retransmits, drops and ACK-match counts every second.

### Measured results

| Gate | Result |
|---|---|
| Native `lr2021` transport | **up** |
| Noise peer authentication | **connected** |
| `ping6` over `fips0` | **5/5, 0% loss**, RTT 66–1746 ms |
| iperf3 UDP 10k offered | **0% loss**, 9.1 kbit/s delivered |
| iperf3 UDP 25k offered | **0% loss**, 24.9 kbit/s delivered (20 s) |
| iperf3 UDP 50k offered | **3.4% loss**, 34.6 kbit/s delivered (20 s, queue tail) |
| iperf3 UDP 100k offered | 46% loss, 36.3 kbit/s delivered |
| 10-minute UDP soak, 25k | **0.08% loss** (5/6251), 24.9 kbit/s, no reset |
| Raw TCP, 4 KiB | completed in ~4.5 s (~7 kbit/s) |
| SSH over `fips0` | `SSH_OVER_FIPS_OK`; `uname -s` returned Linux |
| iperf3 TCP bulk | **0 bytes over 30 s**; not usable |
| Reset stability | both stations at boot #2 through 25k/50k/100k |

A 10-minute 25k UDP soak delivered 6,251 datagrams with 5 lost (0.08%) and no
MCU reset. The stable operating point is **25 kbit/s at 0% loss**. The delivered rate
saturates around 35 kbit/s before loss rises. The limiter is now per-message
half-duplex turnaround and FIPS queuing, not CRC, radio loss or host UART.

`iperf3` TCP bulk remains an open failure: the control connection establishes
and SSH works, but the bulk data stream delivers 0 bytes at 30 s with the
default, 8 KiB and 4 KiB socket windows. Raw 4 KiB TCP does complete, so this
is a throughput/window problem rather than a broken TCP path.

### Direct-FLRC log hashes

```text
27c5011ab13ad708fa68ade5355229ee9ec88c767dc9cf0610b14cd5f8c20da4  guard-64b.log
31c08aa9684bdb91001f0d25885cf6b6e07692c34260029504049c316a770167  guard-255.log
f913294518be05607225a10a9536e2166f8e0482084e5902afaab9919c901b50  soak-part1-BtoA.log
0aca10d10619973a9d1ed9dfbdfe8f5c781398abe9ca60acf1c7a6cafedf9466  soak-part2-AtoB.log
900d7c9acdcdf1a90a2c4d980aa7dea91cafae6bb9b51c4c549236d4cbdc4664  phase2-irqclear-rates.log
422f7678d893da483a1cdd8989f18e0af0c076584f49bf782f5ef2ec99c3d804  phase2-final-rates.log
6cfb4097910652c41244865bd284098bbb7830145d679762e0efaef89683cac5  phase2-complete-ack.log
6a600c134db2a05b5fde397cb27b4ffcd6ff9f792c25a8d19d05ca7e95cb39d6  phase2-master-slave.log
96a82785154334ba00fd7aee6ef3d21937dfc5a75a0fdfc5554f09f4aeb882ba  phase2-soak-25k-10min.log
```

The firmware image for these runs is 87,780 bytes, SHA256
`526ba7f571fe0cb505c1354a8c2320683ba5d506dfff3bf31c90b8e42e40318a`.
## Conclusions

1. The stock official-EVK USB path is measured and stable at 1 Mbaud.
2. It provides about 0.99 Mbit/s aggregate framed loopback payload, not 2.6.
3. A 2.6 Mbit/s end-to-end FIPS link is not possible over this stock path.
4. Stock FLRC PER and FLRP both work consistently after their first-series
   warm-up issue; no steady RF failures were observed at bench range.
5. Reaching multi-megabit FIPS requires a different host link: high-speed UART,
   direct USB-SPI to the radio, or a different host board. Wiring, pogo/clip
   adapters and purchases require separate review and approval.
6. The direct-FLRC bridge is reliable at the packet level: 64 B and 255 B are
   100/100 one-at-a-time with the 2 ms inter-frame guard, and 30,000 × 64 B
   messages over ~35 minutes had 0% loss.
7. FIPS over the bridge is now **usable at low rate**: `ping6` is 5/5 at 0%
   loss, 25 kbit/s UDP is 0% loss, 50k is 3.4% loss, SSH works, and both
   stations stay at boot #2 through 25k/50k/100k traffic. The old 94–99% loss
   and the intermittent resets were caused by half-duplex ACK collisions and a
   vendor modem panic on a stale RX IRQ; both are fixed.
8. `iperf3` **TCP bulk is still not usable** (0 bytes over 30 s), although a raw
   4 KiB TCP transfer and SSH succeed. The current limiter is the half-duplex
   link layer's per-message turnaround, not the radio or host UART.

## High-speed UARTE00 build (not hardware-tested)

The nRF54L15 UARTE00 high-speed peripheral can use dedicated P2.07 RX / P2.08 TX,
which correspond to XIAO D7/D6. A compile-tested overlay for 4 Mbaud exists in
`firmware/seeed-nrf54l15-bridge/overlays/uart00.overlay`. It disables UART21 to
avoid pin contention and builds successfully:

- artifact: `build/seeed-usp-workspace/build/seeed-bridge-loopback-hs/zephyr/zephyr.bin`
- size: 31,660 bytes
- SHA256: `34faf9ba3ef0b47f5009209708f4152d5c0f4fb80b391ca3af33bdd5ccf6abfb`
- devicetree: UARTE00 status okay, current-speed 4,000,000, alias
  `seeed-bridge-uart = &uart00`; UART21 disabled.

No external 3.3 V USB-UART adapter was attached, so no 4 Mbaud electrical or
throughput result exists. The XIAO's built-in USB-C path does not reach these
pins. A Grove/jumper connection to an external high-speed adapter is required
and remains unverified.

## Bench state after this run

Both stations were left running the **direct-FLRC 1 Mbaud image in receive
mode**: 87,780 bytes, SHA256
`526ba7f571fe0cb505c1354a8c2320683ba5d506dfff3bf31c90b8e42e40318a`.
The FIPS containers are stopped and no host is sending traffic, so the radios
are not transmitting. The earlier loopback image was replaced by the FLRC image
during this test. The 4 Mbaud UARTE00 image was only built; it was not flashed
because no external USB-UART adapter was attached.

## Log hashes

```text
de4770a8467fcd653db92800132526a2ca0fa029d2abd057b2547b3c61a51e5c  bench-A-115200.log
6d9a0575c2a4e71f5713a0043541a4ccecafa42f67d72975575c9c0353a0910e  bench-A-230400.log
ffcb1969223b703845cec6a25306d924d7fbc3a1813c071ed2b6f8f35aac57bf  bench-A-460800.log
72815dae649a36380a095ab5d8dab70fb7430c474c9337b51729be6228c7f4e8  bench-A-921600.log
d744c3f0976590d654a4e82aa934c9cd49e83b67d2d5826630773338c00600de  bench-A-1000000.log
c3f546b5ce1f458fc19ee6058b5d941488b40dcdc618f68e0a2fa14d3ba1b4ea  bench-A-final-1000000.log
ecb1faecb167ca2983cbfabff3841c4cf74a2e44790c68d3d255087edf67f5ea  bench-B-1000000.log
12fe111a3c89f9cf323d5927afedb403940589722ba0c37cfc9b2d2cdc85b68c  per-rx-steady.log
5938b6d30a3ac949f0e40ebb44e3c6b69e7efabc1928fdbc53599d3950dbd7fa  per-tx-steady.log
d96d19aa93abafa0b2aaf0c348bdea3c3f1dd623a6c6177c9a921c218af77650  per-rx-clean.log
573d33ec7b337612d4ce83d9c086279e5c3890dbc289f148bbc3601523666470  per-tx-clean.log
96ea4fcd115ec120adeed3336b16943906dcafa904072a8fb569d58bc3b5021d  flrp-initiator.log
d10bb6613aca66379e945480a4782bdace35bbbcadaa8ca7f47434f64769a140  flrp-slave.log
```
