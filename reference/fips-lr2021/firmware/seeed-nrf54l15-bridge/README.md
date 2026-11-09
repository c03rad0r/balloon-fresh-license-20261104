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
make seeed-bridge-loopback-build
```

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

## Host validation (2026-11-08)

- Host unit tests pass, including AddressSanitizer/UndefinedBehaviorSanitizer.
- The Zephyr image builds cleanly against USP-Zephyr `64f416bddd5c95ec4504b00627aa932eb88c7bd5`,
  Zephyr 4.4.0 and SDK 1.0.1: 27,332-byte `zephyr.bin`, SHA256
  `2648c8d0b26e63c71e64b44e70a45ab12c9f345e7643a555cba39309a49223bf`.
- No board was attached, flashed or exercised.
