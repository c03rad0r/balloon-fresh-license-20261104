# Seeed nRF54L15 bridge — offline loopback only

**Status: offline host-loopback skeleton. No LR2021 radio path is implemented.
No hardware, RF, host-throughput or FIPS result is claimed.**

This application validates the existing bridge wire codec and UART transport on
the official Seeed/Semtech LR2021 EVK. It deliberately does **not** load or
configure the LR2021 radio yet. Its `HELLO_ACK` reports:

- protocol 1;
- firmware 0.1.0;
- chip ID 0;
- capabilities `0x0008`, meaning variable packet length only. Sub-GHz, 2.4 GHz
  and relay capability bits are clear.

`CFG` is decoded and acknowledged with a nonzero "radio unavailable" status; it
is never reported as successfully applied. `TX` packets of 1–255 bytes are
returned locally as `RX` frames with zero RSSI, zero SNR and `crc_ok=1`. This
proves framing and counters, not radio transmission.

## Build and test

From `reference/fips-lr2021`, using the setup described in the EVK onboarding
guide:

```bash
make seeed-bridge-host-test
make seeed-bridge-loopback-build BRIDGE_BAUD=115200
make seeed-bridge-loopback-flash BRIDGE_BAUD=115200 PROBE='<full-CMSIS-DAP-id>'
make seeed-bridge-usb-bench PORT='/dev/serial/by-id/<console>' BRIDGE_BAUD=115200
```

The flash target refuses to flash if the built UART baud differs from
`BRIDGE_BAUD`. The benchmark echoes framed 255-byte payloads and reports both
directions and wire overhead. Build and flash at each rate under test. A window
of 4 is stable at high rates; larger windows overrun the current receive ring.

The build uses the normal `xiao_nrf54l15/nrf54l15/cpuapp` board and the LoRa Plus
Expansion Board plus Wio-LR2021 shields. The host UART baud defaults to 115200
and is a build-time Kconfig value, `SEEED_BRIDGE_UART_BAUD`. A raw `west build`
may supply an application config overlay when a deliberately supported rate is
being investigated. Do not assume a higher baud is supported or delivers useful
throughput until it has been measured.

The radio-free loopback is suitable for validating:

- bridge framing, CRC and resynchronization;
- HELLO/CFG capability and rejection behavior;
- PING/PONG, STAT and counters;
- UART chunking and output bounds.

With the host utility running on the UART, `fips-lr2021ctl hello` should report
protocol 1, firmware 0.1.0, `chip=0x0000` and `capabilities=0x0008`. A subsequent
`cfg` command **must fail** with a nonzero rejection because no radio is present;
that is expected, not a regression to work around.

It is **not** suitable for RF, range, throughput, FIPS handshake, IPv6, SSH or
iperf claims. The direct-FLRC radio implementation and hardware validation are
deferred until the bench baseline exists.

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
