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

## Conclusions

1. The stock official-EVK USB path is measured and stable at 1 Mbaud.
2. It provides about 0.99 Mbit/s aggregate framed loopback payload, not 2.6.
3. A 2.6 Mbit/s end-to-end FIPS link is not possible over this stock path.
4. Stock FLRC PER and FLRP both work consistently after their first-series
   warm-up issue; no steady RF failures were observed at bench range.
5. Reaching multi-megabit FIPS requires a different host link: high-speed UART,
   direct USB-SPI to the radio, or a different host board. Wiring, pogo/clip
   adapters and purchases require separate review and approval.

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

Both stations were left running the **non-transmitting 1 Mbaud loopback**
firmware. The PER transmitter was explicitly replaced after capture so it is not
continuing scheduled RF transmissions. The 4 Mbaud UARTE00 image was only built;
it was not flashed because no external USB-UART adapter was attached.

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
