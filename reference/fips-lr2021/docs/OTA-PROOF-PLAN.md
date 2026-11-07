# Proving an over-the-air frame on archipelago — staged plan

Written 2026-11-05. Goal: prove two LR2021 radios exchange frames **before**
asking for a manual test. Everything here is doable without physical access,
except where noted.

## Prerequisites for a manual SSH-over-FIPS test

| # | Prerequisite | Status |
|---|---|---|
| 1 | Two radios exchange a frame over the air | **not demonstrated** |
| 2 | FIPS peer addressing over `lr2021` (peer addr = 4-byte link id) | code exists, never exercised |
| 3 | Two FIPS instances with TUN, matching radio config | not attempted |
| 4 | FIPS handshake over the radio | blocked by 1 |
| 5 | SSH over the FIPS IPv6 address | blocked by 1–4 |

## Three distinct problems, only one of which is interop

| # | Problem | Evidence | Nature |
|---|---|---|---|
| 1 | Is anything transmitted at all? | ESP32 `timeouts=40` | instrumentation or TX fault |
| 2 | Do the radio parameters match? | framing, bitrate table, encoding | interop |
| 3 | Can any node receive? | no frame ever observed | RX unproven |

Problems 1 and 3 must be settled before 2 is testable: a link that does not exist
cannot be tuned.

## Stage 0 — self-reception (settles problems 1 and 3, one board)

Configure one node, transmit, and check whether its **own** bridge `rx` counter
increments. Self-reception means the radio demonstrably transmits *and* receives,
with no peer involved.

- [x] **RP2040: `tx=20 rx=20 timeouts=0` — transmits AND receives.** The radio,
      the wiring and the bridge firmware all work. This is the first confirmed
      working node in the project.
- [x] **ESP32 `88:56`: `tx=20 rx=0 timeouts=20` — no TX completion, no RX.**
- [x] **ESP32 `B0:A6`: identical failure** after flashing the same build.

### Consequence

Both ESP32 carriers fail identically while the Pico succeeds on the same host, so
the fault is specific to the ESP32 carrier, not to the transport or the protocol.

Crucially: **`cfg` no longer proves anything.** The version gate was removed, so
`cfg` returns success unconditionally. `chip=0x0000` on both boards may mean the
SPI bus is not reaching the radio at all — i.e. the ESP32 carriers may not use the
tracker reference board's pin map (GPIO6/2/7/10/3/4/5).

The pin map of the original firmware on `B0:A6` was overwritten when we flashed
the bridge, so it cannot be read back from the device.

Two further findings narrow this down:

- The `TX: seq=… rssi=OK` output that looked like proof of transmission is **not**
  evidence. In `tracker/firmware/radio_test/main/main.cpp` that line is printed
  whenever `send_packet()` returns `Ok`, which only means the SPI command was
  accepted — never that the radio transmitted.
- The module on these carriers is a **G-NiceRF LoRa2021-868**, i.e. a real LR2021.
  So the zeros are not a "wrong chip" problem.

**Pin map hypothesis: DISPROVED.** The NiceRF variant's own build flags
(`mesh-stack/meshcore-lr2021/patches/variant/platformio.ini`) confirm exactly the
pins we used:

```
P_LORA_SCLK=6  P_LORA_MISO=2  P_LORA_MOSI=7
P_LORA_NSS=10  P_LORA_RESET=3 P_LORA_BUSY=4  P_LORA_DIO_1=5
```

So the ESP32 carriers are wired to the pins the driver expects, yet two separate
boards return zeros for every SPI read and fail both TX and RX. With the software
explanations now exhausted — pins correct, module is a real LR2021, framing
aligned, sequence taken from a proven driver — the remaining candidates are
hardware-side:

- the radio module is not powered (an enable pin or jumper not asserted)
- the SPI bus is damaged on both carriers
- both carriers are faulty in the same way

None of these can be resolved without a meter on the board.

### What this means for a two-node test

The only confirmed working node is the Pico. The only other candidate is the E80,
which is running old firmware without a `BRIDGE` command and needs SWD to reflash.
So **no two-node test is currently possible on this bench** without either:

- recovering an ESP32 carrier's pin map, or
- reflashing the E80 over SWD (physical access).

If a node hears itself, the fault is purely parameter interop. If it does not,
the parameter question is premature.

## Parameter table — what must match exactly

| Parameter | RP2040 carrier | ESP32 driver | E80 STM32 |
|---|---|---|---|
| Frequency encoding | FRF | FRF | **plain Hz** |
| Bitrate code @650 | 0x04 | 0x03 | 0x04 |
| Bitrate code @2600 | 0x00 | 0x00 | 0x00 |
| Framing byte0/byte1 | 0x0C/0x4C | 0x0E/0x4D → now 0x0C/0x4C | 0x0C/0x4C |
| CRC | off | now off | off |
| Sync word | cfg | cfg | hardcoded 0x2DD4D4B2 |

Two consequences:

- **At FLRC-2600 both bitrate tables agree (0x00).** At 650 they do not. Test at
  2440 MHz / FLRC-2600 where the discrepancy disappears.
- **RP2040 and ESP32 now agree on everything** (FRF, 0x00, aligned framing, CRC
  off, same sync), so a null result from that pair is meaningful.
- **The E80 is the odd one out** (plain Hz). Mixing it with the NiceRF modules is
  the hardest case and goes last.

## Stage 1 — can a radio transmit at all?

The DIO line never asserts on the ESP32 carrier, so `timeouts` is ambiguous. Two
possible causes: the IRQ pin is not wired, or the radio is not transmitting.

**Finding while preparing this stage:** the two firmware families use *different
FLRC packet framing*, so they could never have interoperated regardless of IRQ:

| Family | Packet params |
|---|---|
| E80 driver (RP2040 carrier, STM32) | `{0x0C, 0x4C, len}` |
| Proven NiceRF driver (ESP32) | `{0x0E, 0x4D, len}` |

Byte 1 differs in the CRC bit, byte 0 in the sync/preamble field. **Both ends must
use the same framing.** Since the ESP32 can be reflashed remotely and the RP2040
cannot (BOOTSEL), alignment must be applied to the ESP32 side.

- [x] Add a compile-time packet-framing override to the shared driver
- [x] Build the ESP32 bridge with the E80-compatible framing `{0x0C, 0x4C}`
- [x] Flash remotely via `usb_reset`
- [ ] `per` from the ESP32, `echo` on the RP2040 → **still `rx=0`**

### Result 2026-11-05

Framing aligned, still nothing:

```
esp32: tx=40 rx=0 crc=0 timeouts=40
pico : tx=0  rx=0 crc=0 timeouts=0 resets=3
```

The ESP32 never sees the DIO line assert, so it never reports TX completion. Two
possibilities remain, and they need a measurement rather than another guess:

1. **GPIO5 is not wired to the radio's IRQ on this carrier.** Then `timeouts` is a
   false alarm and the radio may be transmitting perfectly.
2. **The radio is not entering TX at all.**

The decisive measurement is the **FLRC packet status register (0x024B)** read over
SPI immediately after `SET_TX`, which reports TX progress without depending on the
DIO pin. The current driver does not expose it for TX, so this needs a small
addition.

Equally unresolved: **the RP2040 has never been shown to receive anything.** Its
TX is confirmed, its RX is not. Until one node demonstrably receives, a null
result from it proves nothing about the other side.

## Stage 2 — does a radio receive?

The RP2040's TX is confirmed (`timeouts=0`); its RX has **never** been shown to
work. One successful `per`/`echo` proves both directions of one pair.

- [ ] RP2040 → ESP32 frames received
- [ ] ESP32 → RP2040 frames received

## Stage 3 — two independent pairs, easiest first

- [ ] RP2040 ↔ ESP32 at 2440 MHz / FLRC-2600 (same encoding, same bitrate code,
      aligned framing) — the most likely pair to work
- [ ] E80 (`ttyUSB1`) ↔ RP2040 (`ttyACM0`) — cross-family, expect the frequency
      encoding to fight back

Both pairs must pass before believing the transport is sound.

## Structural fix (prevents recurrence)

The bench has three firmware families, each carrying its own copy of "the air
configuration", and they drifted. The durable fix is a **single canonical
air-config definition** — frequency, bitrate, framing, CRC, sync — shared by all
three bridges, plus a self-test that transmits and confirms reception. Worth
writing down even if the event build stays pragmatic.

## Stage 4 — FIPS over the radio, same host

- [ ] Two network namespaces on archipelago
- [ ] `fips` in each, `transports.lr2021` on a different bridge, same band/sync,
      distinct `local_id`
- [ ] Peer configured with the other node's 4-byte link id
- [ ] Handshake completes
- [ ] `ping6` between namespaces
- [ ] `ssh` between namespaces over the FIPS address

## Stage 5 — only then the manual test

- [ ] One radio on the T14, one on archipelago
- [ ] `fips` on both, handshake, `ping6`, `ssh`

## Constraints

- Bench is in the EU: `eu868` or `eu2400` only, never `us915`.
- ESP32 flashing works remotely (`esptool --before usb_reset`).
- RP2040 reflashing needs BOOTSEL — physical access.
- E80 reflashing needs SWD — physical access.
- Prefer 2440 MHz for sustained testing; 868.0–868.6 MHz has a 1% duty cycle.


## E80 UART ROM bootloader — tried and failed (2026-11-05)

The E80 accepts `FLASH` and answers `OK JUMPING TO BOOTLOADER`, but
`stm32flash` cannot complete the handshake over the onboard CH340:

```
stm32flash -b 115200 -w e80_bridge.bin -v /dev/ttyUSB1
  -> Failed to init device, timeout.

-i none            -> Failed to send boot enter sequence
-i -dtr&-rts       -> Failed to init device, timeout
-b 9600            -> Failed to init device, timeout
```

The STM32 ROM bootloader requires 8E1; the CH340 path does not appear to deliver
it. This confirms the earlier result on a different host, so it is a property of
the onboard CH340, not of one machine.

**Consequence:** the E80 cannot be reflashed without SWD. It currently sits in the
ROM bootloader and needs a **power cycle** to return to the application. Note that
`uhubctl` is not installed on `archipelago.local`, so a remote power cycle is not
available there.

## Remaining physical actions

1. Power-cycle the E80 (returns it to the old bench firmware).
2. Wire the Pico debugprobe to the E80's debug header and reflash over SWD — the
   only route to a second working node.
3. Meter one ESP32 carrier: radio module supply, and continuity on SCK/MOSI/MISO
   between the ESP32 and the module.


## Cross-node results, 2026-11-05 late

Two nodes now transmit and self-receive:

```
Pico : tx=40 rx=40 crc=0 timeouts=0   (self-reception)
E80  : tx=140 rx=0 crc=4 timeouts=0   (transmits; 4 CRC errors seen)
```

But **neither hears the other**:

- E80 transmitting → Pico `echo` receives 0 frames
- Pico transmitting → E80 `echo` receives 0 frames

Both are internally consistent (they hear their own packets), which proves the
radio and firmware work but says nothing about the absolute frequency.

### Framing variants already tried against the E80

| Pico encoding | Pico framing | Result |
|---|---|---|
| FRF | 0x0C / 0x4C | no cross-node frames |
| plain Hz | 0x0E / 0x4D | no cross-node frames |

### Remaining suspects, in order

1. **Bitrate code.** The E80 driver maps 650 kbps to `0x04`; the NiceRF driver
   maps it to `0x03`. If the E80's vendor HAL uses a third mapping, the two
   transmit at different rates and cannot decode each other. At 2600 both tables
   agree on `0x00`, which argues for testing at 2.4 GHz where the table
   discrepancy disappears.
2. **Absolute frequency.** Pico self-reception is consistent under either
   encoding, so it cannot distinguish them. Only a known-good receiver or a
   spectrum analyser can.
3. **Framing bytes inferred rather than read.** The `0x0E/0x4D` values were
   derived from the vendor's preamble/sync/CRC settings; they were not read back
   from the E80's actual SPI traffic.

### Next step that removes guesswork

Read the exact FLRC command bytes the E80's firmware sends
(`firmware/e80-stm32-bench/src/radio_bench.c` and the vendor HAL it calls), and
mirror those bytes literally in the RP2040 bridge rather than deriving them from
the packet-parameter encoding.


## Vendor-exact FLRC bytes extracted and applied (2026-11-05)

Read from the E80's vendor driver (`third_party/Radio/lr20xx_driver`), not inferred:

| Command | Vendor bytes | Our driver had |
|---|---|---|
| `SET_RF_FREQ` (0x0200) | `freq` as 4-byte big-endian Hz | same (correct) |
| `SET_MOD_PARAMS` (0x0248) @650 | `04 17` — br_bw 0x04, (CR_3_4<<4)\|BT_1.0 | `04 25` |
| `SET_PKT_PARAMS` (0x0249) | `1E 7D` — sync4B+(pre32<<2), CRC2\|FIX<<2\|match123<<3\|txsw1<<6 | `0C 4C` / `0E 4D` |

The RP2040 bridge now sends the vendor bytes exactly (`E80_PKT_BYTE0=0x1E`,
`E80_PKT_BYTE1=0x7D`, `E80_MOD_BYTE1=0x17`, plain-Hz frequency).

### Result: still no cross-node frame

```
E80 : tx=192 rx=0 crc=5 timeouts=0
Pico: tx=0   rx=0
```

The E80 transmits cleanly (`timeouts=0`) and occasionally sees CRC errors, but no
valid frame from the Pico. The Pico only transmits after receiving, so it stayed
silent.

With framing now copied literally from the vendor driver, the remaining
explanations are no longer software-parameter drift:

1. **The two modules are on different absolute frequencies** — different band
   variants, or one of them not actually tuning where we think.
2. **The Pico side is not radiating usefully** at 868 (its module may be a
   2.4 GHz-only part, or the LF PA config is wrong for it).

Both need a measurement, not another parameter change: an SDR (or any third
receiver) to see where each radio actually transmits.


## SPI bypass validation, 2026-11-07

The ESP32-S3 driving an E80's LR2021 through `J2` (STM32 held in reset) was
measured with a `GET_VERSION` read reported in an `EVT` frame.

### Result

| Check | Result |
|---|---|
| SPI transaction completes | **yes** (`err=0`) |
| Version bytes returned | **`00 00 00 00`** |
| Init sequence (writes + BUSY + RST) | completes |

### What that means

- **SCK, MOSI, NSS, BUSY and RST are functional** — command writes complete and
  the BUSY handshake releases.
- **MISO is returning nothing.** A working LR2021 answers `GET_VERSION` with real
  version bytes; all zeros means the host is reading a line that the radio is not
  driving, or the radio is unpowered.

### Two driver fixes were needed to get this far

1. With `SPI_DEVICE_HALFDUPLEX`, a receive-only transaction is rejected
   (`Lr2021Error::SpiError`, `err=1`). Full-duplex (flags = 0) with hardware CS
   fixes it.
2. `GET_VERSION` was not exposed by the driver; it was added and is now reported
   in `HELLO_ACK` and as an `EVT` frame.

### Next step for the bypass

Check **J2-9 (MISO) → ESP32 GPIO2** for continuity, and confirm the radio module
is powered (the E80 has an RF module power jumper). Until the version reads
non-zero, the bypass is not usable.
