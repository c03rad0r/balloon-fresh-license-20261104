# Semtech/Seeed LR2021 EVK onboarding for PER, FLRP and later FIPS work

**Audience:** a colleague with two official Semtech LoRa Plus Evaluation Kit
stations: Seeed **XIAO nRF54L15 + LoRa Plus expansion board + Wio LR2021**.
**Scope:** no-soldering vendor samples, RF/PER and bulk-transfer baselines, and
measurements needed before a future nRF54 FIPS bridge.

> **No local board, RF, host-throughput or FIPS success is claimed.** This is a
> runbook plus pinned source tooling. Commands become evidence only when the
> operator saves their actual output. The implementation status and validation
> log are in [the implementation checklist](SEEED-LR2021-EVK-IMPLEMENTATION-PLAN.md).

## 1. Status and evidence boundaries

| Milestone | What counts as evidence | Current status |
|---|---|---|
| Documented | Exact URLs, immutable USP Zephyr commit, commands and cautions reviewed | **Done for this document** |
| Host-tested | Bash/lint/Make dry-runs or actual host builds/test output recorded in the checklist | **Limited; see the checklist, not a board result** |
| Board-tested | Probe IDs and controlled flash/boot logs from these exact boards | **Not run here** |
| RF-tested | Complete, repeatable TX and RX logs with regulatory/setup metadata | **Not run here** |
| Host-link-tested | Error-checked delivered USB/UART byte counts and timing | **Not run; stock path is not a throughput test** |
| FIPS-tested | Existing FIPS protocol over a direct-FLRC nRF54 bridge, followed by Noise/IP/SSH/iperf evidence | **Not implemented or run** |

Semtech's upstream **validated** label describes Semtech's validation; it is not
validation of this worktree's boards. Keep README examples, successful compile,
flash, RF and FIPS as separate claims.

## 2. Source of truth

The helper and examples use USP Zephyr commit
[`64f416bddd5c95ec4504b00627aa932eb88c7bd5`](https://github.com/Lora-net/usp_zephyr/tree/64f416bddd5c95ec4504b00627aa932eb88c7bd5),
whose README identifies stable USP release v1.2.1. Its
[`west.yml`](https://github.com/Lora-net/usp_zephyr/blob/64f416bddd5c95ec4504b00627aa932eb88c7bd5/west.yml)
selects Zephyr v4.4.0 and `Lora-net/usp` v1.2.1. The SDK default is the Semtech
validated 1.0.1. `USP_ZEPHYR_REF` accepts only a full commit ID: the helper never
silently substitutes current `main`.

Pinned primary references:

- [USP Zephyr README, build/flash/prerequisites and console](https://github.com/Lora-net/usp_zephyr/blob/64f416bddd5c95ec4504b00627aa932eb88c7bd5/README.md)
- [LoRa Plus EVK and LR2021/LR2022/LR2012 differences](https://github.com/Lora-net/usp_zephyr/blob/64f416bddd5c95ec4504b00627aa932eb88c7bd5/doc/LORA_PLUS_EVK.md)
- [FLRC PER sample](https://github.com/Lora-net/usp_zephyr/tree/64f416bddd5c95ec4504b00627aa932eb88c7bd5/samples/usp/sdk/packet_error_rate_flrc) and its [pinned implementation in USP v1.2.1](https://github.com/Lora-net/usp/blob/v1.2.1/examples/main_examples/packet_error_rate_flrc_example/app_per_flrc.c)
- [FLRP API sample](https://github.com/Lora-net/usp_zephyr/tree/64f416bddd5c95ec4504b00627aa932eb88c7bd5/samples/usp/rac/flrp_api), [compile-time header](https://github.com/Lora-net/usp/blob/v1.2.1/examples/main_examples/flrp_api_example/app_flrp_api.h), [protocol phases](https://github.com/Lora-net/usp_zephyr/blob/64f416bddd5c95ec4504b00627aa932eb88c7bd5/doc/FLRP_principles.md), and [configuration/integrity limitations](https://github.com/Lora-net/usp_zephyr/blob/64f416bddd5c95ec4504b00627aa932eb88c7bd5/doc/FLRP_guidelines.md)
- [Semtech validation methodology and SPI clocks](https://github.com/Lora-net/usp_zephyr/blob/64f416bddd5c95ec4504b00627aa932eb88c7bd5/doc/VALIDATION_AND_PERFORMANCES.md)
- Existing project transport: [`docs/BRIDGE-PROTOCOL.md`](BRIDGE-PROTOCOL.md), not FLRP framing

The sample source and generated tools live under the ignored
`reference/fips-lr2021/build/seeed-usp-workspace/`. Nothing is installed globally,
no `sudo` is run, no udev rule is written, and there is no `rm -rf` cleanup in the
helper. Zephyr's official `--pristine` build may regenerate only the selected
role-specific build directory. Do not put secrets or LoRaWAN credentials in any
command or log.

## 3. Hardware, SKU, antennas and regulatory stop checks

### Identify before connecting TX equipment

1. Photograph each kit label, order SKU, XIAO revision, expansion-board revision,
   Wio radio label/revision and supplied antennas. Record the exact bundle; do
   not infer it from the case or from another kit.
2. This procedure requires **Wio LR2021**, board
   `xiao_nrf54l15/nrf54l15/cpuapp`, and both shields
   `semtech_loraplus_expansion_board` and `semtech_wio_lr2021` in that order.
   LR2022 and LR2012 variants do not provide the LR2021 FLRC/FLRP capability;
   `_cn` shields are not interchangeable defaults.
3. Label the two physical stations **A** and **B**. Keep a written association:
   physical label ↔ probe unique ID ↔ serial by-id symlink ↔ flashed role.
4. Power off before seating the XIAO and Wio boards. Check connector orientation
   and full engagement against the kit quick-start guide. No wiring or soldering
   is needed for the stock shield combination.
5. Inspect both radios for damage and fit the correct, matched antenna for every
   enabled RF path **before any TX**. Do not transmit into an open connector, an
   antenna for the wrong band, or a connector whose RF path is unknown. Follow
   the kit guide for which antenna/port serves sub-GHz versus 2.4 GHz; do not
   guess from connector appearance.
6. Start with physically separated stations and avoid antenna-to-antenna
   co-location overload. Increase separation/attenuation if RSSI is unexpectedly
   high or receivers behave only at very close range. Do not use a close-range
   “successful” packet as evidence of a good RF link.

### EU/region requirement — transmission is operator-gated

The operator must identify the exact jurisdiction, hardware SKU/antenna gain,
frequency plan, **EIRP**, duty cycle/dwell/listen-before-talk rules and any other
conditions for the test. The vendor defaults are not regulatory approval, and
FLRP explicitly leaves compliance to the application. Do **not** select US915 or
reuse the older E80 `us915` examples for this EU work.

Use short initial tests at the lowest power explicitly verified and configured
for the local setup. Important: the pinned stock PER and FLRP defaults include
+14 dBm TX power; this tooling does **not** silently lower them. If that stock
setting is not lawful or suitable, do not transmit. A reviewed, recorded vendor
source/configuration change is then a separate experiment, not this unmodified
baseline. Keep sub-GHz and 2.4 GHz runs in separate result tables.

## 4. Understand the host boundary before setting a throughput goal

**USB-C is not a direct SPI connection to the LR2021.** On this kit the XIAO's
SAMD11 provides a CMSIS-DAP debug/probe interface and a CDC serial connection.
The stock Zephyr nRF54L15 application chooses `uart20` as console/shell at
**115200 baud, 8N1, no flow control**; the serial traffic therefore traverses the
SAMD11 path. The nRF54 talks to the LR2021 over the internal shield SPI bus.

The [Zephyr board DTSI](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/boards/seeed/xiao_nrf54l15/xiao_nrf54l15_common.dtsi)
sets UART20 to 115200, and the [CPU application DTS](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/boards/seeed/xiao_nrf54l15/xiao_nrf54l15_nrf54l15_cpuapp.dts)
chooses it for console/shell. Semtech validated this platform's internal SPI at
8 MHz (with some other examples lightly tested at 16 MHz). Neither SPI clock nor
USB-C capability proves PC-to-board streaming throughput.

At 115200 baud with ten serial bits per 8N1 byte, the serial-link arithmetic
ceiling is 11,520 byte/s = 92.16 kbit/s before software/protocol losses. That is
**not measured goodput**. No high-rate host-streaming firmware is included in the
stock PER/FLRP samples, so sustained high host throughput is unverified.

## 5. Host setup

Run from the reference root:

```bash
cd reference/fips-lr2021
make seeed-doctor   # inventory only; missing items are not hardware failures
make seeed-setup
make seeed-doctor
```

Setup creates a Python venv, local HOME/cache, source checkouts, minimal SDK and
ARM GNU toolchain below `build/seeed-usp-workspace/`. It uses the Zephyr v4.4.0
supported `west sdk install --install-dir ... --gnu-toolchains arm-zephyr-eabi`
interface rather than a system SDK. `west update` is a large multi-repository
download; even the minimal SDK/toolchain is substantial. Allow time and disk
space. The helper deliberately stops on clone, pinned-checkout, manifest,
Python-package, SDK or compiler errors instead of printing a false success.

Before creating the workspace or downloading source, `make seeed-setup` checks
for `git`, `python3`, `cmake`, `ninja`, `cc`, `gperf` and `dtc`. If any is
absent it stops immediately with a **host-prerequisite error**, before the
large downloads below; this says nothing about board health.
`make seeed-doctor` reports the same inventory plus `picocom` and other optional
diagnostic context. Python also needs working `venv` support. Install missing
OS packages using the colleague's normal administrator process; this helper
will not do so. No existing bootstrap script is required.

Useful overrides (all paths are quoted and may contain spaces):

```bash
make seeed-setup SEED_USP_WORKSPACE="$PWD/build/my seeed workspace"
make seeed-doctor SEED_USP_WORKSPACE="$PWD/build/my seeed workspace"
```

Keep the same workspace override on every later command. Do not point it at an
unrelated West workspace; an existing USP checkout at the wrong commit is
rejected, never reset.

### Stable probe and console identification

1. Connect one station at a time initially. Run `make seeed-doctor` and save its
   output. Copy the **full probe unique ID** from `pyocd list`; never accept an
   implicit “only probe” selection.
2. On Linux, use `/dev/serial/by-id/*` symlinks rather than `/dev/ttyACM0` or
   `/dev/ttyACM1`, which can change after replug/reboot. On another OS use its
   persistent USB serial/device identity mechanism.
3. Reconnect both and repeat. Ensure IDs are distinct and update the physical
   A/B association. If needed, flash one at a time with the other disconnected;
   the explicit `PROBE` remains mandatory even then.
4. The helper does not choose a probe or serial port for you. `PROBE` is required
   for every flash and `PORT` for every monitor. Verify both immediately before
   use.

For permission errors, ask the host administrator for current pyOCD CMSIS-DAP
udev rules plus the pinned checkout's
`usp_zephyr/boards/seeed/xiao_nrf54l15/support/99-xiao-nrf54l15.rules`.
Replug afterwards. This runbook does not copy rules or invoke `sudo`.

## 6. Baseline A — unmodified FLRC packet error rate (sanity, not maximum rate)

### What the pinned code actually does

The PER receiver/transmitter is a packet-integrity/sanity baseline, **not a PHY
maximum-throughput benchmark**. The v1.2.1 implementation has fixed 255-byte TX
and RX buffers, a fixed `INTER_EXCHANGE_DELAY = 200` ms, a 400 ms RX timeout, and
100-exchange series separated by 10 s. The README's broader configurable wording
does not make those C constants safe command-line controls. This PR therefore
exposes only `ROLE`; it does not offer unsupported size/delay variables.

The pinned sample README lists 866.5 MHz, +14 dBm and 2.6 Mbit/s FLRC among its
defaults. Those values must be captured in the run metadata and checked against
local rules; neither 2.6 Mbit/s nor `255 bytes / 200 ms` is an end-to-end maximum.
Do not change optimization flags: although FLRP's `prj.conf` mentions speed
optimization earlier, the pinned PER/FLRP configurations also contain later
debug/no-optimization settings. Preserve the complete stock files.

### Build and flash

Use the correct physical probe from the A/B map:

```bash
make seeed-per-build-rx
make seeed-per-build-tx

make seeed-per-flash-rx PROBE='FULL_CMSIS_DAP_UNIQUE_ID_FOR_RX'
make seeed-per-flash-tx PROBE='FULL_CMSIS_DAP_UNIQUE_ID_FOR_TX'
```

Equivalent helper calls are:

```bash
./scripts/seeed-usp.sh build per-rx
./scripts/seeed-usp.sh build per-tx
PROBE='...' ./scripts/seeed-usp.sh flash per-rx
PROBE='...' ./scripts/seeed-usp.sh flash per-tx
```

Builds are independent: `build/seeed-usp-workspace/build/seeed-per-rx/` and
`.../seeed-per-tx/`. Flashing does not rebuild a different role and never uses a
default probe.

### Run and capture

Open two terminals, substituting persistent paths. Start the receiver first and
retain complete boot-to-series logs:

```bash
# Receiver terminal
make seeed-monitor PORT='/dev/serial/by-id/RX_PERSISTENT_ID' \
  2>&1 | tee build/seeed-usp-workspace/logs/per-rx-run01.log

# Transmitter terminal, after receiver is ready
make seeed-monitor PORT='/dev/serial/by-id/TX_PERSISTENT_ID' \
  2>&1 | tee build/seeed-usp-workspace/logs/per-tx-run01.log
```

The stock settings are `BAUD=115200`, 8N1, no flow control; picocom exits with
Ctrl-a Ctrl-x. Reset as appropriate while preserving logs. Record several full
100-packet series, TX counters, successful/failed/CRC counts, RSSI where present,
and resets/restarts. A final integer PER percentage alone is insufficient.

## 7. Baseline B — FLRP bulk transfer, 20 KiB, both data directions

FLRP-BURST is a four-phase **bulk/file-transfer protocol**: LoRa wake-up,
adaptive-link setup, FLRC burst/ACK and retry. Initiator/slave describes session
control; transmitter/receiver describes each payload direction. The initiator
always sends the WOR but does not always send bulk data.

FLRP is **not the existing FIPS bridge**. It does not implement
`docs/BRIDGE-PROTOCOL.md` raw framing/ACK semantics. With
`FLRP_API_CRYPTO_ENABLED=true`, packets use an AES-CMAC message-integrity check
(MIC) in place of radio CRC; the payload is **not encrypted**. MIC provides
integrity only: it does not provide FIPS transport, Noise, IPv6 or
confidentiality.

### Stock compile-time configuration

The pinned header defaults are:

| Macro | Stock default | Helper variable |
|---|---|---|
| `FLRP_API_ROLE` | `FLRP_API_ROLE_SLAVE` | selected by target |
| `FLRP_API_DATA_SIZE` | `(20 * 1024)` = 20 KiB | `FLRP_DATA_SIZE='(20*1024)'` |
| `FLRP_API_CRYPTO_ENABLED` | `true` | `FLRP_CRYPTO=true` |
| `FLRP_API_IS_LOW_FREQUENCY` | `true` | `FLRP_LOW_FREQ=true` |
| `FLRP_API_IS_LISTENING` | `true` | intentionally not exposed |

The initiator automatically alternates TX then RX on its stock periodic timer
(20 s); the slave listens. The helper explicitly supplies role, size, MIC and
band-selection macros with their stock values while leaving source/config files
unmodified. Compact numeric expressions avoid shell/CMake whitespace splitting;
boolean values must be exactly `true` or `false`.

### Build and flash initiator A / slave B

```bash
make seeed-flrp-build-initiator
make seeed-flrp-build-slave
make seeed-flrp-flash-initiator PROBE='FULL_CMSIS_DAP_UNIQUE_ID_FOR_A'
make seeed-flrp-flash-slave     PROBE='FULL_CMSIS_DAP_UNIQUE_ID_FOR_B'
```

Build directories are `seeed-flrp-initiator` and `seeed-flrp-slave` below the
workspace `build/` directory. Monitor both persistent ports as in the PER
example, naming logs `flrp-initiator-run01.log` and `flrp-slave-run01.log`.
Start the slave console/listening before allowing the initiator schedule to
proceed; save output from both devices for the same wall-clock run.

Explicit baseline command for both roles, if desired for audit logging:

```bash
make seeed-flrp-build-initiator \
  FLRP_DATA_SIZE='(20*1024)' FLRP_LOW_FREQ=true FLRP_CRYPTO=true
make seeed-flrp-build-slave \
  FLRP_DATA_SIZE='(20*1024)' FLRP_LOW_FREQ=true FLRP_CRYPTO=true
```

Changing any of these values changes the experiment; rebuild **both** roles
consistently and flash the resulting matching builds. In particular,
`FLRP_LOW_FREQ=false` selects 2.4 GHz, not a validated EU default and not US915.
`FLRP_CRYPTO=false` selects radio CRC rather than MIC. Do not perform these later
runs until the unmodified sub-GHz baseline is lawful and repeatable.

### Capture initiator → slave

For an initiator `[TX #... OK]` event and its corresponding slave `[RX #... OK]`:

1. Mark run start/end with host UTC and monotonic timestamps.
2. Save initiator and slave logs, configured size, actual received `size=`, retry
   and status counters, RSSI/SNR if logged, band/channel plan and transfer number.
3. Measure requested 20 KiB whole-transfer goodput only across an identifiable
   transfer boundary:

   `goodput_bit_per_s = 8 * 20480 / whole_transfer_seconds`.

   If the sample log reports a different payload size (for example, application
   framing/counter bytes), record requested and delivered bytes separately and
   state which numerator is used. Do not force them to match.

### Capture slave → initiator

Use the next alternating transfer, identified by slave `[TX #... OK]` and
initiator `[RX #... OK]`. Apply the same timing/size method and link it to the
same two logs. Do not swap these directions merely because the initiator always
starts the WOR.

Repeat each direction several times and report every trial including timeouts,
retries and restarts. If stock logs do not expose start/end timestamps sufficient
to reconstruct whole-transfer time, write **not measurable from stock logs**;
do not infer time from the 20 s periodic trigger. Data-phase goodput may be added
only if data-phase timestamps are actually present. Semtech's gross-burst table
and the raw 2.6 Mbit/s FLRC rate are different quantities and must not be copied
into application-goodput cells.

## 8. Separate RF, host-link and FIPS ceilings

| Layer | Required measurement | What must not be substituted |
|---|---|---|
| RF/vendor bulk | Delivered FLRP bytes and complete start/end time (plus data phase if available), retries/loss logged | 2.6 Mbit/s PHY rate, gross-burst values, PER packet size |
| nRF54↔LR2021 SPI | Driver/bus timing with instrumentation if an SPI ceiling is needed | 8 MHz validation clock labelled as application throughput |
| USB/SAMD11/UART host link | Error-checked bytes delivered at each tested baud/rate and logging overhead | USB-C connector, SPI clock, 115200 baud arithmetic labelled “measured” |
| Future direct-FLRC bridge | Existing bridge-protocol packets, loopback then two-node loss/goodput | FLRP session/file semantics or PER sanity |
| End-to-end FIPS | Distinct-node Noise handshake, IPv6 ping, SSH, iperf3 ramp and application goodput | RF or serial-theoretical rate, mock-E2E alone |

The eventual FIPS ceiling can be no higher than the slowest relevant host,
framing/retry, radio and FIPS processing stage, but that is a measurement model,
not a result. The stock samples cannot decompose all these stages by themselves
because their UART logging can also affect application timing. Decide and record
instrumentation before comparing results. A future direct-FLRC implementation of
`BRIDGE-PROTOCOL.md` remains a separate PR.

A later controlled 2.4 GHz table can be generated with
`FLRP_LOW_FREQ=false` on both builds, but it is not part of the first sub-GHz
success gate. Likewise FLRP radio timing/PA/interframe/packet sweeps need a
reproducible source patch and paired settings; they are intentionally not Make
variables in this baseline.

## 9. Troubleshooting

| Symptom | Check / safe next step |
|---|---|
| `USP_ZEPHYR_REF ... could not be fetched` | Verify network/proxy and the exact pinned commit. The helper stops rather than floating to `main`. Do not copy a newer command into a baseline run. |
| Existing checkout has a different HEAD | Use a fresh ignored workspace or deliberately align that source yourself. The helper never resets a checkout. |
| West looks for `application/` or cannot resolve the sample | The pinned `west.yml` has `self.path: application`, while its standalone README clones as `usp_zephyr` and uses `usp_zephyr/samples/...`. Setup writes local `manifest.path=usp_zephyr` to match its actual clone. Inspect `.west/config` and `west manifest --resolve`; record any upstream failure instead of renaming files blindly. |
| `west packages`, venv or pip failure | Confirm the command uses `build/seeed-usp-workspace/.venv`, not global Python. Check OS `venv` support and the actual network/package error. Do not use `sudo pip`. |
| SDK release discovery returns HTTP 403 / `API rate limit exceeded` | This was observed once during host validation. Wait for the reset time advertised in the error, then rerun `make seeed-setup`; the completed local checkout is preserved. It is not a board fault. Do not put personal-access tokens in commands, committed files or logs. |
| SDK missing/wrong version or compiler absent | Rerun `make seeed-setup`; inspect `sdk/zephyr-sdk-1.0.1/sdk_version` and the ARM compiler path. The helper does not borrow a system SDK or install udev rules. |
| CMake/API failure | Confirm USP HEAD equals the pin and Zephyr is v4.4.0. Save complete output. Do not hide a changed sample by switching to current upstream. |
| pyOCD finds no probe | Check data-capable USB cable, power, CMSIS-DAP inventory and pyOCD >=0.38. Connect one board at a time. Do not try another runner/probe implicitly. |
| pyOCD permission denied | Install current pyOCD and XIAO udev rules through the host administrator, then replug. The helper never uses `sudo`. |
| More than one probe / flashed wrong role | Disconnect one station, rebuild the A/B mapping, and always pass the full unique `PROBE`. Confirm matching build directory and boot banner. |
| Empty or garbled serial output | Reidentify `/dev/serial/by-id`, use 115200 8N1 no flow control, close competing terminals, check shield seating/reset. Do not assume another baud is “faster and safe”. |
| PER never starts | Start RX first, verify both roles and pins/defaults, inspect RX timeout/CRC logs and antennas. Check regulatory/setup stop conditions before further TX. |
| FLRP no WOR/ACK, transfer errors or MIC failure | Ensure initiator/slave roles, listening slave, identical DATA_SIZE/CRYPTO/LOW_FREQ builds, correct antennas and sufficient separation. MIC keys/config must match; payload is still unencrypted. Preserve both logs over the same transfer numbers. |
| Result looks implausibly high | Verify actual byte numerator/time boundary and band. Separate whole-transfer/data-phase/gross/PHY/UART numbers; look for UART logging or retries. Never publish an unverified board success claim. |

## 10. Results template — copy to a dated local results record

Leave unavailable cells **not run** or **not measurable**; never replace them with
upstream example values.

### Run identity and evidence

```text
Run ID / operator / host OS:
Date, timezone and monotonic clock source:
USP_ZEPHYR_REF: 64f416bddd5c95ec4504b00627aa932eb88c7bd5
Zephyr / USP / west / pyOCD / SDK versions:
USP and Zephyr worktree diffs (empty for unmodified baseline):
Exact kit/order SKU, XIAO and board revisions, radio labels:
Purpose-built vs stock antennas; connector and RF path used:
Physical A/B ↔ probe unique ID ↔ serial by-id mapping:
USB cables/hubs, host power state:
Country/jurisdiction and operator-verified EIRP/duty/LBT conditions:
Station separation/orientation/environment:
Exact build/flash/monitor commands:
Raw TX/RX log paths and hashes:
Flash success log path (does not imply RF success):
Unexpected resets, edits, omissions or prior firmware:
```

### FLRC PER (one table per band/configuration)

| Run | Band/freq/power/SKU | TX series/counters | RX processed/success/fail/CRC | PER and method | RSSI/SNR | Raw logs | Notes |
|---|---|---|---|---|---|---|---|
| not run |  |  |  |  |  |  |  |

### FLRP 20 KiB whole-transfer goodput (sub-GHz baseline)

| Run | Data direction (A/B and roles) | Requested bytes | Received bytes | Start/end source | Whole seconds | Whole goodput kbit/s | Data-phase kbit/s if measurable | ok/err/nok/retries | RSSI/SNR | Logs |
|---|---|---:|---:|---|---:|---:|---:|---|---|---|
| not run | initiator A → slave B | 20480 |  |  |  |  |  |  |  |  |
| not run | slave B → initiator A | 20480 |  |  |  |  |  |  |  |  |

Use a **separate** 2.4 GHz table after a deliberate paired `LOW_FREQ=false`
experiment. Record any changed MIC/CRC/radio settings in a new configuration ID,
not as “stock”. Do not merge gross-burst values into these goodput columns.

### Host-path characterization (future, not supplied by stock samples)

| Firmware/test protocol | Port/baud/flow | Bytes sent/delivered/errors | Elapsed seconds | Delivered kbit/s | CPU/logging conditions | Evidence |
|---|---|---|---|---:|---|---|
| not run | SAMD11 CDC + nRF54 UART20 |  |  |  |  |  |

### FIPS follow-up (not this PR)

| Gate | Result/evidence |
|---|---|
| Direct-FLRC `BRIDGE-PROTOCOL.md` host loopback | not run |
| Bridge-to-bridge raw packets / loss | not run |
| Distinct-node FIPS Noise handshake | not run |
| IPv6 ping / SSH | not run |
| iperf3 ramp, delivered goodput and loss | not run |
