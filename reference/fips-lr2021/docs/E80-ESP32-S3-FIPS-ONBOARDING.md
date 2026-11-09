# E80 ↔ ESP32-S3 SPI bypass — soldering, flashing and FIPS onboarding

Audience: a person building **two** E80-900MBL-02 + ESP32-S3 radio adapters and
using them as FIPS transports.

## Status — read before starting

| Stage | Status on 2026-11-07 |
|---|---|
| Exact E80 J2 ↔ ESP32-S3 wiring | **documented below** |
| Holding the E80 STM32 in reset is mandatory | **verified: leaving it enabled caused SPI contention** |
| ESP32-S3 `GET_VERSION` over the bypass | **verified: parsed firmware version `01 18`, reported chip `0x1801`** |
| SPI bypass without STM32 contention | **verified; S3 controls and reads the LR2021 directly** |
| First S3 → native-E80 frames | **verified: 20 valid frames at −46 to −49 dBm** |
| Full-size 255-byte native-E80 → S3 frames | **verified: `flrc_rx valid=20 crc=0`** |
| 128-byte payload delivery in each direction | **verified: 100/100 accepted by `echo` each way at the measured RF ceiling** |
| FIPS Noise handshake between independent radios | **verified: authenticated, connected peers in two namespaces** |
| FIPS end-to-end session | **verified: initiator and responder established on both nodes** |
| Deterministic fixed-size TX padding | **implemented in S3 0.4.21 / C3 0.5.11; 39/39 host tests pass** |
| Sustained, larger-payload bidirectional transfer | **not yet verified; needs a second working S3** |
| FIPS IPv6 ping | **fails so far; not claimed to work** |
| SSH over the radios | **not yet verified** |

You can solder and flash both adapters now. Stop after the checks that are marked
verified. The remaining sections will be updated as the radio link and FIPS are
validated; a green host-protocol response alone is **not** an over-the-air test.

**Radio rules:** EU operation only (`eu868` or `eu2400`; never `us915`). Fit the
correct 868 MHz antenna before transmitting. Keep 868 MHz test bursts short; the
868.0–868.6 MHz sub-band has a 1% duty-cycle limit. Use 868.1 MHz and FLRC-650 for
this design.

## Parts for one adapter (build two)

- one E80-900MBL-02 board (STM32F103 + LR2021 + CH340)
- one ESP32-S3 board with native USB-Serial/JTAG
- one suitable 868 MHz antenna for the E80's RF connector
- eight short, flexible signal wires (silicone-insulated wire is easiest)
- one removable STM32-reset jumper, or a 2-pin header plus jumper shunt
- two USB cables, one for each board; no SWD probe is needed for this design

Use two identical adapters. Each needs its own antenna and common ground between
its E80 and ESP32-S3.

## 1. Identify J2 — zigzag numbering, **not** ordinary row numbering

E80 J2 is a 2×9 header. Odd pins run down one column and even pins down the other:

```text
Row 1:   1  VIN          |  2  3V3
Row 2:   3  DIO11        |  4  DIO10
Row 3:   5  radio NRST   |  6  3V3
Row 4:   7  BUSY         |  8  DIO7
Row 5:   9  MISO         | 10  DIO8  (IRQ)
Row 6:  11  MOSI         | 12  DIO9
Row 7:  13  SCK          | 14  MCU_TXD
Row 8:  15  NSS          | 16  MCU_RXD
Row 9:  17  DIO6         | 18  DIO5
```

Find pin 1 from the square pad, dot or `1` silkscreen. Then confirm the header
electrically with the E80 powered by USB: **3.3 V must be present on pins 2 and 6**,
with pin 4 on the same even-numbered column. If 3.3 V is one column over, your
column assignment is flipped. Do not continue until this is unambiguous.

### Soldering technique

1. Disconnect USB and the battery/power source before soldering.
2. Tin each J2 pad and each wire separately, then join them with a short touch of
   the iron. Do not hold the iron against the radio module or header for several
   seconds at a time.
3. Keep wires short and route SCK, MOSI and MISO away from the antenna and RF
   connector. Avoid bare wire loops which can short neighbouring pins.
4. Inspect for solder bridges with magnification. On the unpowered board, measure
   every adjacent J2 pair in resistance/continuity mode and confirm there are **no
   shorts**, especially between a signal and 3V3.
5. Strain-relieve the finished loom. Do not let the signal wires carry the weight
   of either board.

## 2. Solder the seven radio signals and ground

The numbers in the ESP32 column are **raw GPIO numbers printed on its silkscreen**,
not Arduino `D<n>` aliases.

| E80 J2 pin | LR2021 signal | ESP32-S3 GPIO | Direction relative to S3 |
|---|---|---:|---|
| 13 | SCK | 6 | output |
| 11 | MOSI | 7 | output |
| 9 | MISO | 2 | input |
| 15 | NSS / chip select | 10 | output |
| 7 | BUSY | 4 | input |
| 10 | DIO8 / IRQ | 5 | input |
| 5 | radio NRST | 3 | output |
| board GND | ground | GND | common ground |

J2 has no ground pin. Use the board's debug-header GND or another verified board
ground, not the antenna sleeve as a signal ground.

**Do not connect 3V3, VIN or `V` between the two boards.** Each is powered from its
own USB supply. The E80's regulator remains active while its STM32 is held in reset.

For the two-adapter build, repeat exactly the same mapping on the second pair.

## 3. Permanently hold the E80 STM32 in reset

This is **not optional**. The E80 STM32 and the ESP32-S3 otherwise share SCK, MOSI,
NSS and radio NRST. With both active, the STM32 can reset or reconfigure the radio
and contend with the S3. On the reference adapter this produced `GET_VERSION =
00 00 00 00`; soldering the reset jumper changed it to a valid nonzero version.

The board RESET button is the **STM32** reset. J2-5 is the separate **radio** reset.
Do not confuse them.

1. Unpower the E80.
2. With a multimeter in continuity mode, identify the two sides of its momentary
   RESET switch. On a typical four-pin tactile switch, the pins are paired on each
   side; bridge one pin from **opposite sides**, not two pins already connected on
   the same side.
3. Confirm one side has continuity to board ground; the other is STM32 NRST.
4. Prefer soldering a two-pin header across the switch and fitting a removable
   jumper shunt. A soldered wire across the same two points also works and is
   easy to remove later.

Expected result with USB power applied: STM32 NRST ≈ 0 V and the CH340 console is
silent. This is correct—the STM32 is intentionally disabled.

**Radio-reset sanity check:** J2-5 must follow ESP32 GPIO3 when the bridge drives
radio reset. If your RESET jumper also forces J2-5 to 0 V, it is resetting the
radio too; remove it and locate the STM32-only NRST connection instead.

### Power-off continuity checklist for each adapter

- [ ] J2-13 ↔ GPIO6 has continuity
- [ ] J2-11 ↔ GPIO7 has continuity
- [ ] J2-9 ↔ GPIO2 has continuity
- [ ] J2-15 ↔ GPIO10 has continuity
- [ ] J2-7 ↔ GPIO4 has continuity
- [ ] J2-10 ↔ GPIO5 has continuity
- [ ] J2-5 ↔ GPIO3 has continuity
- [ ] Boards have a common GND
- [ ] No adjacent-header or signal-to-3V3 solder bridges
- [ ] STM32 reset jumper fitted; radio NRST is not permanently grounded
- [ ] 868 MHz antenna fitted before any TX test

## 4. Build the ESP32-S3 bridge firmware

The firmware is `reference/fips-lr2021/firmware/esp32-bridge` in
`felixfelix-bot/balloon-fresh`. It uses native USB-Serial/JTAG, not a separate USB
UART. The same binary is used on both S3 boards; their FIPS node identities are
configured on the host computers later.

Install ESP-IDF 5.5 locally, or use its Docker image. From the repository root:

```bash
cd reference/fips-lr2021/firmware/esp32-bridge
rm -f sdkconfig sdkconfig.old

docker run --rm \
  -v "$PWD/../../../..:/project" \
  -w /project/reference/fips-lr2021/firmware/esp32-bridge \
  espressif/idf:release-v5.5 \
  bash -lc 'idf.py set-target esp32s3 && idf.py build'
```

The three files needed for flashing are then:

```text
build/bootloader/bootloader.bin
build/partition_table/partition-table.bin
build/esp32-bridge.bin
```

Do not substitute an ESP32-C3 build: the S3 and C3 are different targets even
though their wiring maps look similar.

## 5. Install current esptool

`--after watchdog_reset` requires esptool 5.x. Use an isolated environment:

```bash
python3 -m venv /tmp/esptool-venv
/tmp/esptool-venv/bin/pip install esptool
/tmp/esptool-venv/bin/esptool version
```

Use `/tmp/esptool-venv/bin/esptool` in the commands below. `/tmp` is cleared on
reboot; recreate the environment if necessary.

## 6. Flash each ESP32-S3

List stable port names instead of guessing `ttyACM` numbers:

```bash
ls -l /dev/serial/by-id/
```

Set the port for the first board, for example:

```bash
PORT=/dev/ttyACM0   # replace with the S3's actual port
```

Try buttonless USB reset first:

```bash
/tmp/esptool-venv/bin/esptool \
  --chip esp32s3 -p "$PORT" -b 460800 \
  --before usb_reset --after watchdog_reset \
  write-flash \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0x10000 build/esp32-bridge.bin
```

Expected: hash verification succeeds and the tool reports a watchdog reset.

If `usb_reset` cannot reach the ROM, put the S3 into download mode manually once:
**hold BOOT, tap RESET, release BOOT**, then repeat the command with
`--before no_reset`. Firmware which owns the USB PHY can require this first manual
entry; firmware using USB-Serial/JTAG can subsequently use `usb_reset`.

Verify the flashed chip before moving to the second board:

```bash
/tmp/esptool-venv/bin/esptool \
  --chip esp32s3 -p "$PORT" --before usb_reset --after no_reset chip-id
```

Repeat the build-directory flash command for the second S3 after changing `PORT`.
Keep track of each S3's USB `ID_SERIAL_SHORT` (its MAC); Linux may reorder
`/dev/ttyACM*` after reset.

## 7. Basic bridge check

Build the matching `fips-lr2021ctl` host utility from the FIPS LR2021 branch, then:

```bash
fips-lr2021ctl --serial "$PORT" hello
fips-lr2021ctl --serial "$PORT" status
```

The reference adapter answered:

```text
protocol=1 firmware=0.4.21 chip=0x1801 capabilities=0x0007
pong
tx=0 rx=0 crc=0 drops=0 timeouts=0 resets=0
```

A nonzero chip value proves the USB protocol path and that the S3 can read the
LR2021. `00 00 00 00` is not success: check the STM32 reset jumper and MISO first.
A successful `hello` still does **not** prove RF interoperability.

For a fresh version read, configure both adapters identically:

```bash
fips-lr2021ctl --serial "$PORT" --sync-word 2dd4d4b2 cfg --band eu868 --radio-payload 128
```

Expected reference event and configuration:

```text
lr2021 bridge event: ver 01 18 00 00 err=0
configured band=eu868 freq=868100000 Hz flrc=650 kbps power=14 dBm payload=255B relay=false
```

## 8. RF smoke test before starting FIPS

Use two adapters with antennas fitted. Run an `echo` listener on adapter B (its
link ID is **2** by default in `fips-lr2021ctl echo`):

```bash
fips-lr2021ctl --serial "$PORT_B" --sync-word 2dd4d4b2 \
  echo --band eu868 --seconds 30
```

While it listens, send five 64-byte payloads from adapter A, addressed to its
link ID. Keep the radio and USB port roles distinct:

```bash
fips-lr2021ctl --serial "$PORT_A" --sync-word 2dd4d4b2 \
  per --band eu868 --count 5 --size 64 --peer-id 2
```

The useful acceptance signal is **`echo: 5 frames` on B**, proving five valid
payloads crossed and passed the link CRC. Swap A/B and repeat for the other
direction. Do not count unsolicited `Stat` frames as RF reception.

Short packets may report `crc=false` at the bridge while still delivering the
correct data. This bench's LR2021 chips flag short packets even though the FIPS
link's independent CRC32 accepts them; the S3 forwards them with that fact
visible in the counters. Full 255-byte radio frames provide a useful control:
one measured native-E80-to-S3 burst reported `flrc_rx valid=20 crc=0`.

## 9. Build FIPS and `fips-lr2021ctl`

Use the FIPS **fork and feature branch** which contains the native `lr2021`
transport and its tested textual peer-ID handling:

```bash
git clone --branch balloon-lr2021 https://github.com/c03rad0r/fips.git
cd fips
cargo build --release -p fips-mesh --bin fips --bin fipsctl
cargo build --release -p fips-lr2021 --bins
```

The binaries are:

```text
target/release/fips
target/release/fipsctl
target/release/fips-lr2021ctl
target/release/fips-lr2021d
```

All bridge/FLRC host knobs are local; **do not send a PR or issue to
`jmcorgan/fips` for this bench work**. The radio setup here is EU-only.

## 10. Give each adapter a serial port and a FIPS node ID

Use two separate values for each of these:

| Value | Node A | Node B |
|---|---|---|
| Serial device | A's S3 `/dev/serial/by-id/...` | B's S3 `/dev/serial/by-id/...` |
| `transports.lr2021.local_id` | **1** | **2** |
| Peer address `peers[].addresses[].addr` | **"2"** | **"1"** |
| TUN name | `fipsa0` | `fipsb0` |
| control socket | `/tmp/fips-a.sock` | `/tmp/fips-b.sock` |

The peer address is a **decimal string containing the peer's link ID**. It is
not the USB path, an IP address, or the raw ASCII bytes of a four-byte integer.
The fork converts both directions consistently.

Both nodes share this radio profile:

```yaml
band: eu868              # 868.1 MHz, FLRC-650, +14 dBm
radio_payload: 128
sync_word: "2dd4d4b2"
mtu: 1400
ack_timeout_ms: 200
max_retries: 8
auto_connect: true
```

Native USB-Serial/JTAG uses `baud: 2000000`; this setting does not limit the
on-air FLRC rate. Use `band: eu868`, never `us915`.

## 11. Generate two identities and their YAML

Generate a separate directory for each host/node. Keep the private `fips.key`
files secret. This example puts them under `/tmp` for a disposable bench test;
use persistent service directories for deployment.

```bash
FIPS_ROOT=/path/to/fips
B="$FIPS_ROOT/target/release"
WORK=/tmp/fips-two-node
mkdir -p "$WORK/a" "$WORK/b"
"$B/fipsctl" keygen --dir "$WORK/a"
"$B/fipsctl" keygen --dir "$WORK/b"
```

Create `$WORK/a/fips.yaml`, substituting **B's npub** from `$WORK/b/fips.pub`:

```yaml
node:
  identity:
    persistent: true
  leaf_only: true
  control:
    enabled: true
    socket_path: /tmp/fips-a.sock

tun:
  enabled: true
  name: fipsa0
  mtu: 1280

dns:
  enabled: false

transports:
  lr2021:
    port: /dev/serial/by-id/REPLACE_WITH_NODE_A_S3_PORT
    baud: 2000000
    band: eu868
    local_id: 1
    radio_payload: 128
    sync_word: "2dd4d4b2"
    mtu: 1400
    ack_timeout_ms: 200
    max_retries: 8
    auto_connect: true

peers:
  - npub: "REPLACE_WITH_NODE_B_NPUB"
    alias: node-b
    addresses:
      - transport: lr2021
        addr: "2"
    connect_policy: auto_connect
```

Create `$WORK/b/fips.yaml` with these substitutions only:

- B's S3 port in `port`;
- `socket_path: /tmp/fips-b.sock` and TUN `name: fipsb0`;
- `transports.lr2021.local_id: 2`;
- **A's npub** in the peers block and `addr: "1"`.

Use `/dev/ttyUSB0` plus `baud: 115200` **only** when B is the alternative,
already-flashed native E80 STM32 bridge. A second S3/E80 SPI adapter always uses
its own native S3 USB device and 2,000,000 baud.

## 12. Start the two isolated FIPS nodes

One host with two adapters can be tested using separate network namespaces. For
two hosts, run only the local node's command on each host instead.

```bash
sudo ip netns add fips-lr-a
sudo ip netns add fips-lr-b
sudo ip netns exec fips-lr-a ip link set lo up
sudo ip netns exec fips-lr-b ip link set lo up

sudo ip netns exec fips-lr-a \
  "$B/fips" -c "$WORK/a/fips.yaml" >"$WORK/a/fips.log" 2>&1 &
sudo ip netns exec fips-lr-b \
  "$B/fips" -c "$WORK/b/fips.yaml" >"$WORK/b/fips.log" 2>&1 &
```

Check the reports:

```bash
sudo "$B/fipsctl" -s /tmp/fips-a.sock show peers
sudo "$B/fipsctl" -s /tmp/fips-b.sock show peers
sudo ip netns exec fips-lr-a ip -6 addr show dev fipsa0
sudo ip netns exec fips-lr-b ip -6 addr show dev fipsb0
```

### Proven milestone

On 2026-11-07 this configuration produced a Noise-authenticated peer in **both**
namespaces, each with `connectivity: connected` and the other node's FIPS IPv6
address. That is the verified milestone to reach. It is not a claim that all
packet traffic is reliable.

## 13. IPv6 and SSH — currently an open validation gate

After both peers are connected, ping B from A using **B's actual reported IPv6
address**, not a copied example:

```bash
sudo ip netns exec fips-lr-a \
  ping -6 -c 3 -W 4 REPLACE_WITH_NODE_B_FIPS_IPV6
```

Measured status as of this guide's latest update:

- [x] S3 can read a nonzero LR2021 version through the E80 bypass
- [x] First cross-node S3 → native-E80 frames
- [x] Native-E80 → S3 full-size frames with zero CRC errors
- [x] 64-byte payload delivery, 5/5 each way
- [x] Bidirectional FIPS peer authentication/connection
- [ ] Repeated larger-payload and fragmented-packet validation
- [ ] Bidirectional IPv6 ping (latest default run: A→B 0/5, B→A 3/5)
- [ ] An interactive SSH connection over the FIPS IPv6 address

**Do not debug SSH before ping works.** Do not debug ping before both peers
authenticate. Do not assume a correct `hello`, CFG ACK, or nonempty peer list
alone proves SSH will work. The active duplicate-aware reliability gates and
transmission-ordering plan are in `docs/PING-RELIABILITY-PLAN.md`; broader
session/tooling context remains in `docs/IPV6-DATA-PLANE-PLAN.md`.

## 14. Shutdown and common failures

```bash
sudo pkill -f '/tmp/fips-two-node/'
sudo ip netns del fips-lr-a
sudo ip netns del fips-lr-b
```

Delete only these test namespaces. Keep the two E80 STM32 reset jumpers fitted
while using the S3 bypass.

| Symptom | First check |
|---|---|
| `chip=0x0000` or no HELLO_ACK | S3 port, STM32 reset jumper, MISO, common ground |
| Version works but no RF peer control | antenna, shared `eu868` profile, two different node IDs |
| `crc=false` but valid `echo` frames | expected on some short packets here; trust the separately counted link deliveries, not PHY CRC alone |
| A peer authenticates but the other does not | retry only after measuring both radio directions; it is half-connected |
| Both authenticate but ping fails | inspect `bad magic`, `bad crc32`, larger-payload/fragment losses in daemon logs and LR2021 FLRC counters |
| CH340 native E80 goes silent | stop host processes, power-cycle **that E80**, and re-enter `BRIDGE`; the S3 bypass does not use CH340 |
| Ordinary Internet/ssh works but radio does not | use the namespaces so local networking cannot create a false positive |

## Reference measurements on this bench

| Test | Measured result |
|---|---|
| Reset jumper omitted | version read returned zeros due to STM32/SPI contention |
| Reset jumper fitted | parsed `01 18`, `HELLO chip=0x1801` |
| First S3 → native-E80 RF | native monitor received 20 valid frames, RSSI about −49 dBm |
| Native-E80 → S3, 255-byte frames | FLRC counters: 20 packets, 0 CRC errors |
| Native-E80 → S3, 64-byte PER payloads | 5/5 delivered and echoed after correct peer addressing |
| S3 → native-E80, 64-byte PER payloads | 5/5 delivered and echoed |
| Two FIPS namespaces | Noise-authenticated, connected peers in both directions |
| IPv6 ping | 0/3 in each direction in the latest run; work remains |

## Where the implementation and supporting notes live

- Bridge firmware: `reference/fips-lr2021/firmware/esp32-bridge/`
- Shared LR2021 driver: `tracker/firmware/components/lr2021_transport/`
- Original bypass notes: `reference/fips-lr2021/docs/SPI-BYPASS-ESP32-S3.md`
- Buttonless flashing details: `reference/fips-lr2021/docs/FLASHING-WITHOUT-BUTTONS.md`
- Consolidated hardware lessons: `reference/fips-lr2021/docs/LEARNINGS.md`
- OTA validation plan and exact measurements: `reference/fips-lr2021/docs/OTA-PROOF-PLAN.md`
