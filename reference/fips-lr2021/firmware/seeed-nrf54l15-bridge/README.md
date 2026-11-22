# Seeed nRF54L15 bridge — loopback and direct-FLRC modes

**Status: direct LR2021 FLRC bridge implemented and bench-validated on two EVKs.
FIPS-over-radio validation is still in progress.**

The application has two build modes:

- **Loopback** (`seeed-bridge-loopback-*`): the original offline codec/UART
  regression path. It never opens the radio. `CFG` returns a nonzero "radio
  unavailable" status.
- **FLRC** (`seeed-bridge-flrc-*`): a raw LR2021 FLRC packet bridge using the
  official Semtech RAC transaction API. It preserves the host framing and
  counters; FIPS fragmentation, ARQ, deduplication, Noise and IPv6 remain in
  the host.

Both modes report protocol 1. The FLRC build reports firmware 0.2.0, the real
LR2021 version (observed `0x0118`), and capabilities `0x000a` (2.4 GHz +
variable length). Sub-GHz is implemented but not advertised as verified; relay
is rejected.

A `CFG` request is accepted only when the radio backend validates and applies
the requested band, frequency, path, power, bitrate, payload length and sync
word. Applied values are echoed in `CFG_ACK`; invalid requests return a nonzero
status. `TX` payloads are queued to the radio and `RX` frames arrive
asynchronously with measured RSSI/SNR and `crc_ok`. The firmware does not parse
FIPS or hold keys.

## Build and test

From `reference/fips-lr2021`, using the setup described in the EVK onboarding
guide:

```bash
make seeed-bridge-host-test

# Loopback regression mode
make seeed-bridge-loopback-build BRIDGE_BAUD=1000000
make seeed-bridge-loopback-flash BRIDGE_BAUD=1000000 PROBE='<full-CMSIS-DAP-id>'
make seeed-bridge-usb-bench PORT='/dev/serial/by-id/<console>' BRIDGE_BAUD=1000000

# Direct LR2021 FLRC mode
make seeed-bridge-flrc-build BRIDGE_BAUD=1000000
make seeed-bridge-flrc-flash BRIDGE_BAUD=1000000 PROBE='<full-CMSIS-DAP-id>'
```

The flash target refuses to flash if the built UART baud differs from
`BRIDGE_BAUD`. The FLRC build requires the USP/LoRa Basics Modem driver through
`prj-flrc.conf`; the loopback build stays radio-free.

The build uses the normal `xiao_nrf54l15/nrf54l15/cpuapp` board and the LoRa Plus
Expansion Board plus Wio-LR2021 shields. The host UART baud defaults to 115200
and is a build-time Kconfig value, `SEEED_BRIDGE_UART_BAUD`.

## Direct-FLRC bench result (2026-11-22)

EU 2.4 GHz, 2440 MHz, FLRC 2600 kbps, CR 3/4, 12 dBm, 255-byte radio payload,
1 Mbaud host UART. 100 link-layer messages per run:

| Direction | App payload | Delivered | Loss | RSSI |
|---|---:|---:|---:|---:|
| B→A | 64 B | 100/100 | 0% | −16 dBm |
| A→B | 64 B | 100/100 | 0% | −20.9 dBm |
| B→A | 255 B | 100/100 | 0% | −16 dBm |
| A→B | 255 B | 100/100 | 0% | −16.8 dBm |

A 255-byte application message is two radio frames at `radio_payload: 255`. The
bridge TX queue is 16 packets deep; a four-packet queue dropped the second
fragment under back-to-back host delivery.

### 511-byte payloads are not adopted

The LR2021 driver documents FLRC payload lengths of 6–511 bytes and the radio
FIFO is 1023 bytes. We raised the bridge limit to 511 and tested it: single-frame
480-byte traffic was intermittent, and multi-frame 500/1000-byte traffic
intermittently reset the MCU or stalled the sender. The harmonized-bench rules
also require a **≥40 ms gap** between packets longer than 256 bytes. The
production bridge is capped at 255 bytes. 511 is a hardware capability, not a
validated FIPS configuration, and it would not lift FIPS above the ~1 Mbit/s
host-UART ceiling.

The radio-free loopback remains suitable for validating:

- bridge framing, CRC and resynchronization;
- HELLO/CFG capability and rejection behavior;
- PING/PONG, STAT and counters;
- UART chunking and output bounds.

## Host validation (2026-11-22)

Measured on the attached official EVKs with 255-byte payloads and a bounded
four-frame window. This is a framed loopback measurement, not RF throughput.

| Station / baud | H→device payload | Device→H payload | H→device wire | Device→H wire | Loss |
|---|---:|---:|---:|---:|---:|
| A / 115200 | 87.16 kbit/s | 87.16 kbit/s | 89.97 kbit/s | 91.66 kbit/s | 1/218 |
| A / 230400 | 160.54 kbit/s | 160.54 kbit/s | 165.36 kbit/s | 168.77 kbit/s | 1/398 |
| A / 460800 | 288.01 kbit/s | 288.01 kbit/s | 296.33 kbit/s | 302.74 kbit/s | 1/711 |
| A / 921600 | 468.77 kbit/s | 468.77 kbit/s | 481.63 kbit/s | 492.71 kbit/s | 0/1155 |
| A / 1000000 | 495.02 kbit/s | 495.02 kbit/s | 508.61 kbit/s | 520.31 kbit/s | 0/1219 |
| A / 1000000 (clean reflash) | 481.96 kbit/s | 481.96 kbit/s | 495.19 kbit/s | 506.58 kbit/s | 0/1187 |
| A / 1000000 (final alias build) | 495.30 kbit/s | 495.30 kbit/s | 508.90 kbit/s | 520.60 kbit/s | 0/1220 |
| B / 1000000, 10 s | 495.88 kbit/s | 495.88 kbit/s | 509.50 kbit/s | 521.21 kbit/s | 0/2437 |

At 1 Mbaud this is approximately **0.99 Mbit/s aggregate payload** and
**1.03 Mbit/s aggregate wire traffic**. The nRF54L15 standard UART tops out at
1 Mbaud, so the stock USB/SAMD11/UART path cannot carry 2.6 Mbit/s FIPS
throughput. A higher-speed path requires a separate hardware/transport decision.

Earlier host validation: unit tests and ASan/UBSan passed, and Zephyr built with
USP-Zephyr 4.4.0 and SDK 1.0.1.

## Implementation notes from live bring-up

- The nRF UARTE receive path must be interrupt-driven; `uart_poll_in()` did not
  deliver host bytes in this configuration.
- With a user UART ISR installed, TX must also be serviced from the interrupt
  callback. The bridge uses a bounded TX ring and retains a pending byte when
  the hardware FIFO is full.
- Function-local C++ static objects need libstdc++ guard symbols under Zephyr's
  minimal C++ runtime; the loopback core is namespace-scoped instead.
- A framed byte stream can split between the two magic bytes. Host decoders must
  preserve a trailing `0xA5` across reads.
- Window 4 is stable at 115200 through 1 Mbaud. Larger windows overran the RX
  path; do not treat a high “offered” rate as successful delivery.

## High-speed UARTE00 option — built, not hardware-tested

The standard nRF54L15 UART used by the built-in SAMD11 USB bridge is limited to
1 Mbaud. The SoC also has UARTE00, which supports up to 4 Mbaud on dedicated P2
pins. On XIAO those are:

| UARTE00 signal | XIAO pin | SoC pin |
|---|---|---|
| TX | D6 | P2.08 |
| RX | D7 | P2.07 |
| GND | GND | GND |

This is the exposed user UART; it is not connected internally to the USB-C
connector. Testing it requires an external **3.3 V-logic** USB-UART adapter
connected as adapter TX → D7, adapter RX → D6, and grounds joined. Do not inject
5 V logic or power the board through the adapter. A Grove UART cable or jumper
wires are sufficient; no soldering is required if those pins/connector are
accessible.

Use an adapter actually rated above the target baud (for example FT232H/FT2232H
or another adapter with a documented 3.3 V high-speed UART mode). Many common
CP2102/CH340 variants do not meet this requirement. Which adapter will be used
must be recorded with the result.

Build/flash the high-speed variant only after wiring:

```bash
make seeed-bridge-loopback-highspeed-build BRIDGE_BAUD=4000000
make seeed-bridge-loopback-highspeed-flash BRIDGE_BAUD=4000000 PROBE='<probe>'
make seeed-bridge-usb-bench PORT='<external USB-UART port>' BRIDGE_BAUD=4000000
```

The 4 Mbaud image builds successfully (31,660 bytes, SHA256
`34faf9ba3ef0b47f5009209708f4152d5c0f4fb80b391ca3af33bdd5ccf6abfb`) and the
devicetree confirms UARTE00 on P2.07/P2.08 with UART21 disabled. **No adapter
was attached, so 4 Mbaud throughput and even electrical operation remain
unverified.** Start at lower rates and increase only after error-free delivery.

The theoretical 4 Mbaud 8N1 ceiling is 3.2 Mbit/s of user bytes per direction,
before framing and turnaround. Even if that host path works, it does not make
2.6 Mbit/s end-to-end FIPS possible: the radio payload and FIPS/link overhead
remain below the raw FLRC PHY rate.
