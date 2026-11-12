# BENCH Console Protocol — Normative Cross-Board Specification

**Spec ID:** BENCH-CONSOLE-SPEC v1.0
**Status:** Normative (HARM-T1, harmonization plan 2026-08-21)
**Consumers:** E80 bench fw (STM32F103C8 + LR2021), RP2040 bench fw, ESP32-C3 bench fw, all host sweep/ctl tools
**Normative sources:** `firmware/e80-stm32-bench/src/{bench_cmd.c,bench_pkt.c,prbs.c,bench_payload.c}` — freestanding C, port VERBATIM (see §11)

> **EXTERNAL REFERENCE (2026-11-08):** an independent ESP32-S3 + SX1280 FLRC implementation with
> its own PlatformIO throughput/attenuation bench projects is published at
> `10.5281/zenodo.21159006` (CC-BY-4.0). Useful as a **cross-check on FLRC configuration
> parameters**, not as a base — see
> [`docs/external/OPENFLRC-ZENODO-21159006.md`](external/OPENFLRC-ZENODO-21159006.md).

This document is the single source of truth for the console protocol shared by all
three bench boards. Where a board's firmware and this spec disagree, the spec wins;
where this spec and the harmonization plan (`docs/bench/harmonization-plan-20260821.md`)
disagree, this spec wins (it is the T1 deliverable the plan calls for).

---

## 1. Transport and line framing

| Property | Value |
|---|---|
| Physical | UART 115200 baud, 8N1 (E80: USART1). USB-CDC consoles MUST sustain an equivalent line rate (see §7 for why). |
| Framing | Newline-terminated ASCII lines. `\r` tolerated and stripped; a lone `\r` after `\n` is skipped. |
| Tokenization | Space-separated tokens; commands case-INSENSITIVE (`loRa`, `LoRa`, `LORA` all accepted). |
| Line limits | ≤ 8 tokens, ≤ 24 chars per token (`E80_CMD_ARG_MAX`), line buffer ≥ 96 chars (`E80_CMD_MAX_CHARS`). Hosts MUST keep command lines ≤ 96 chars. |
| Reply forms | `OK [...]` on success, `ERR <REASON>` on failure. Parse errors use the fixed reasons `SYNTAX`, `ARG`, `RANGE`, `UNKNOWN`. |
| Async lines | `PKT,...`, `CONFIG_START,...`, `TX DONE (RADIO ASLEEP)`, boot banner, `WDG RESET (...)`, `NOTE ...` may interleave with replies at any time. **Hosts MUST ignore unrecognized lines, never treat them as fatal** (forward-compat rule). |

Unit conventions: `rssi_dbm` / `snr_db` are signed integers (chip half-dBm / quarter-dB
values truncated to whole units); `ts_ms` is ms since boot (u32, wraps ~49.7 d);
`per_x1e6` is PER × 10⁶; `bw_khz` = Hz/1000; `kbps` integer.

---

## 2. Command set (normative cross-board minimum)

Reply strings below are EXACT (verbatim from `bench_cmd.c` / `bench.c`). Porters must
reproduce them character-for-character — host tools pattern-match on them.

### 2.1 `ID?` — identity (board tag REQUIRED)

```
ID <BOARD> v<maj.min> fw=<sha7> role=<TX|RX|NONE> armed=<0|1> mod=lora sf=<sf> bw=<hz>|mod=flrc br=<bps> freq=<hz> band=<label> pa=<dbm> pcap=<label> chip=<maj.min> radio=<asleep|awake> boot=<label> buf=<n>
```

- `<BOARD>` is the registered board tag (see §10). This is the cross-board
  discriminator: hosts key the tag to select the frequency-allowed set (§9).
- `mod=lora sf= bw=` and `mod=flrc br=` are alternatives, exactly one present.
- E80 example: `ID E80BENCH v1.2 fw=6ff1292 role=TX armed=1 mod=flrc br=650000 freq=868000000 band=863-870MHz pa=10 pcap=+10dBm chip=2.1 radio=awake boot=jump-ok buf=4096`
- Informational fields other boards may localize: `band=` (their allowed set),
  `pcap=` (their PA cap), `boot=`, `buf=`.

### 2.2 `ROLE TX|RX|NONE`

| Command | Reply |
|---|---|
| `ROLE TX` | `OK ROLE TX (TX INHIBITED - SEND 'ARM TX' TO ENABLE)` |
| `ROLE RX` | `OK ROLE RX (CONTINUOUS)` |
| `ROLE NONE` | `OK ROLE NONE (RADIO ASLEEP)` |

RX enters continuous RX immediately and resets stats. NONE parks the radio asleep.

### 2.3 `ARM TX` — two-step TX enable

Preconditions: role is TX. Reply: `OK ARMED (TX ENABLED)`.
Wrong role: `ERR ROLE NOT TX`.
(Two-step design is a hard safety gate: no command line can go from idle to radiating.)

### 2.4 `MOD loRa <sf> <bw_khz>` | `MOD flrc <br_kbps> <dbm>`

```
OK MOD lora sf=<sf> bw=<bw_hz>
OK MOD flrc br=<br_bps> pa=<dbm>
```

- loRa: `sf` 5..12, `bw` ∈ {125, 250, 500} (kHz token; emitted in Hz). Parse violations → `ERR RANGE`.
- flrc: `br` ∈ {260, 325, 520, 650, 1040, 1300, 2080, 2600} (kbps token; emitted in bps); `dbm` −20..+22 parse range.
- **PA semantics differ:** `MOD flrc` sets TX power in the same command; `MOD loRa` does not (use `PA`).
- Runtime PA cap (E80, recommended for all boards): 0..+10 dBm indoor; outdoor unlock
  raises to +22. Violation → `ERR RANGE (INDOOR CAP 0-10 DBM; UNLOCK: POWER MODE OUTDOOR 2026)`
  (or `ERR RANGE (0-22 DBM)` once unlocked).

### 2.5 `FREQ <hz>`

`OK FREQ <hz>`, or `ERR BAND (EU SRD 863-870MHZ ONLY, SEE 'BAND OVERRIDE <PIN>')` on E80.
Allowed set per board: §9. Hosts MUST NOT send out-of-band frequencies.

### 2.6 `PA <dbm>`

`OK PA <dbm> DBM`. Range violations as in §2.4 (indoor cap message identical).

### 2.7 `START [N=<pkts>] [LEN=<bytes>] [GAP=<us>]`

Keys order-independent, case-insensitive. Defaults `N=100 LEN=255 GAP=5000`.
Parse ranges: `N` 1..1,000,000; `LEN` 6..511; `GAP` 100..100,000,000 (µs).

- **TX board:** `OK START n=<n> len=<len> gap_us=<gap> src=PRBS|BUF`
  (`src=BUF` iff a staged buffer was loaded — E80 BUF extension, §3.3).
  Burst completion is an async line: `TX DONE (RADIO ASLEEP)`.
- **RX board** (identical command line goes to both boards): `OK RX ARMED len=<len>`
  — configures the FLRC FIX_LEN window and re-arms continuous RX.
- Errors, in order checked:
  - `ERR ROLE NOT TX` (on a TX-expecting board whose role isn't TX)
  - `ERR NOT ARMED (SEND 'ARM TX')`
  - `ERR LEN (MAX 255 LORA / 511 FLRC)` — mod-dependent cap, see §6.

### 2.8 `STOP`

`OK STOP (RADIO ASLEEP)` — any role; ends the session and parks the radio.

### 2.9 `SESSION <id>` / `CONFIG <id> <replicate>`

```
OK SESSION <id>
OK CONFIG <id> <replicate>
CONFIG_START,<config_id>,<replicate>,<ts_ms>      <- async marker line, follows the OK
```

`SESSION`/`CONFIG` tag every subsequent `PKT` line (fields 1-3) for lossless
host-side joins. `CONFIG_START` brackets each config segment in the capture log.

### 2.10 `STAT?`

```
STAT role=<TX|RX|NONE> sent=<n> sent_ok=<n> rx=<n> crc_err=<n> per_x1e6=<n> [per_ci_x1e6=[<lo>,<hi>]] elapsed_s=<s.s> kbps=<n> rssi_avg_dbm=<d.d> rssi_min_dbm=<d.d> rssi_max_dbm=<d.d> snr_avg_db=<d.d> cr=<n> session=<id> config=<id> replicate=<n> drops=<n> gap_us=<n> buf=<n>
```

- `per_ci_x1e6=[lo,hi]` present only when a valid RX sequence was seen (Wilson
  score interval, expressed on the 10⁶ scale).
- `kbps`: RX role counts received bytes; TX role counts `sent_ok × len`.
- `drops` = radio event-mailbox drops (host-side watch item; >0 means console/IRQ starvation).

### 2.11 `PRBS ON|OFF`

`OK PRBS ON` / `OK PRBS OFF`. Toggles PRBS-15 RX verification (default OFF).
When ON, `PKT` lines carry real `bit_err`/`bytes_bad` (§4).

### 2.12 `HELP`

Single line starting `CMDS:` listing the command words. Content is informational.

### 2.13 E80 vendor extensions (NOT required for cross-board compliance)

`PRBS9 ON|OFF` (chip-level TX test mode; guards: `ERR TX ARMED (STOP OR DISARM FIRST)`,
`ERR TX BURST ACTIVE (STOP FIRST)`), `FLASH`, `BAND OVERRIDE <pin>`,
`POWER MODE OUTDOOR <pin>`, `BUF CLEAR`, `BUF LOAD <n> <crc16_hex>` (binary phase:
`OK BINARY <n>` ack, then n raw bytes, then `OK BUF <n> 1` / `ERR CRC` / `ERR TIMEOUT`),
`BUF STATUS`. Porters MAY implement or omit; hosts MUST NOT require them.
`BUF LOAD` staging is recommended for identical-payload A/B tests.

---

## 3. `PKT` per-packet line — 25 columns, append-only

Emitted by the RX board on **every** `RX_OK` **and** every `RX_CRC` event:

```
PKT,<session>,<config>,<replicate>,<pkt_idx>,<ts_ms>,<rssi_dbm>,<snr_db>,<crc_ok>,<bit_err>,<bytes_bad>,<freq_hz>,<mod>,<sf>,<bw_khz>,<cr>,<pa_dbm>,<len>,<gps_fix>,<gps_lat>,<gps_lon>,<gps_alt>,<gps_sats>,<gps_hdop>[,<pcrc16>]
```

| Idx | Field | Type | Semantics |
|---|---|---|---|
| 0 | (tag) | str | `PKT` |
| 1 | session | u32 | from `SESSION` cmd |
| 2 | config | u32 | from `CONFIG` cmd |
| 3 | replicate | u32 | from `CONFIG` cmd |
| 4 | pkt_idx | u32 | TX sequence number from the payload header (§4); **0 on CRC-fail rows** |
| 5 | ts_ms | u32 | ms since boot at RX event |
| 6 | rssi_dbm | int | chip half-dBm / 2 (signed truncation) |
| 7 | snr_db | int | chip quarter-dB / 4 (signed truncation) |
| 8 | crc_ok | 0/1 | chip CRC verdict |
| 9 | bit_err | u32 | PRBS-15 Hamming distance (PRBS ON; else 0) |
| 10 | bytes_bad | u32 | bytes with ≥1 bit error (PRBS ON; else 0) |
| 11 | freq_hz | u32 | session frequency |
| 12 | mod | str | `LORA` or `FLRC` (uppercase) |
| 13 | sf | u32 | LoRa SF 5-12; FLRC rows echo the stored value — **hosts ignore it for FLRC** |
| 14 | bw_khz | u32 | bw_hz/1000; FLRC rows: 0 |
| 15 | cr | u32 | LoRa: denominator 5-8 (default 5 = 4/5). FLRC: raw code (1 = 3/4 default) |
| 16 | pa_dbm | int | TX power echo |
| 17 | len | u32 | payload bytes received |
| 18-23 | gps_* | 0 | reserved GPS placeholders, always 0 on bench boards (future trackers may populate) |
| 24 | pcrc16 | u16 | §5; **0 on CRC-fail rows** (no payload read). May be OMITTED entirely by firmware without BUF-T5a → 24-column line |

**Host contract:** parsers key indices **1-17 and 24** (the reference host parser
`tools/e80_sweep_full.py:parse_pkt` does exactly this) and MUST accept both 24- and
25-column lines (`pcrc16` absent ⇒ treat as not-verified). Fields are APPEND-ONLY:
new fields go after index 24; reordering is a spec break.

CRC-fail rows (`crc_ok=0`): `pkt_idx=0`, `len=0`, `bit_err=0`, `bytes_bad=0`,
`pcrc16=0`, but `rssi_dbm`/`snr_db` ARE populated — the chip measures signal
strength before the CRC check. Do not filter CRC-fail rows from RSSI statistics.

`CONFIG_START,<config_id>,<replicate>,<ts_ms>` (3 CSV fields + tag) is emitted after
every `OK CONFIG` and is the host-side capture segmentation marker.

---

## 4. Payload and PRBS-15 (port `prbs.c` verbatim)

Payload layout (LEN bytes total):

```
[0..3]  TX sequence number, BIG-ENDIAN u32 (buf[0]=MSB)
[4..LEN-1] PRBS-15 fill, seeded by that sequence number
```

- `LEN ≥ 6` always (4-byte header + ≥1 PRBS byte; actually ≥2 fill bytes).
- PRBS-15 generator: Fibonacci LFSR, taps x¹⁵+x¹⁴+1:
  `state₁₅→ state = ((state<<1) | newbit) & 0x7FFF` with
  `newbit = ((state>>14) ^ (state>>13)) & 1`, bits assembled MSB-first into bytes.
- Seed: `state = (seq ^ 0x5A5A) | 1` (odd, non-zero for all seq).
- Verification (PRBS ON): extract `seq` from the header, regenerate the fill,
  XOR against received, `bit_err` = popcount, `bytes_bad` = count of non-zero XOR bytes.
- Normative implementation: `src/prbs.c` / `src/prbs.h` — freestanding C, no deps.

**Golden vectors** (mirror `prbs.c`; computed 2026-08-21):

| seq | header | PRBS fill, first 8 bytes |
|---|---|---|
| 0 | `00 00 00 00` | `DD D8 CC D2 AA EF FE 60` |
| 1 | `00 00 00 01` | `DD D8 CC D2 AA EF FE 60` (identical — seed folds the seq LSB) |

32-byte payload (header + 28 fill) pcrc16: seq=0 → `0x997E`, seq=1 → `0x6998`.

---

## 5. `pcrc16` — payload CRC (BUF-T5a, field 24)

- Algorithm: **CRC-16/CCITT-FALSE** — poly 0x1021, init 0xFFFF, MSB-first,
  no input/output reflection, no final XOR.
- Scope: the FULL received payload (`e.len` bytes, including the 4-byte sequence header).
- CRC-fail rows: `pcrc16 = 0` (no payload is read out on CRC failure).
- Reference (bitwise, from `buffer.c`):

```c
uint16_t crc16_ccitt_false(const uint8_t* data, uint32_t len) {
    uint16_t crc = 0xFFFF;
    for (uint32_t i = 0; i < len; i++) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (int bit = 0; bit < 8; bit++)
            crc = (crc & 0x8000u) ? (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u)
                                  : (uint16_t)(crc << 1);
    }
    return crc;
}
```

**Golden vectors** (shared with `tools/test_crc16_golden.py`):

| Input | CRC |
|---|---|
| `"123456789"` | `0x29B1` |
| 64 × `0x00` | `0xD6DA` |
| 4096 × `(i % 256)` | `0x0F69` |

Porters: these three vectors MUST pass on-target before a board is called
protocol-compliant. (Note `pcrc16` rides the BUF-T5a branch `buf/t5a-rx-pcrc16`
commit `88a00cf` on E80; firmware on branches without it emits 24-column PKT lines,
which hosts accept per §3.)

---

## 6. LEN caps — dual enforcement

| Layer | LoRa | FLRC |
|---|---|---|
| Command parse (`START LEN=`) | 6..511 | 6..511 |
| Radio/session (silicon + fw) | **255** | **511** |

The mod-dependent cap is enforced by the firmware at START
(`ERR LEN (MAX 255 LORA / 511 FLRC)`) AND MUST be enforced by host sweep tools
before sending START (belt and braces — a host-side check catches config errors
before they burn airtime).

---

## 7. GAP rule for large packets

**For `LEN > 256`, hosts MUST set `GAP ≥ 40000` µs (40 ms).**

Rationale: at 115200 8N1 the console drains ~87 µs/byte; a worst-case PKT line plus
housekeeping needs headroom so RX line assembly never starves radio IRQ servicing.
40 ms was measured safe in the E80↔E80 511-byte FLRC sweeps (651 pkts, zero drops).
For `LEN ≤ 256` hosts may use the adaptive form `GAP = max(10 ms, 1.2 × airtime + 5 ms)`.

---

## 8. FLRC golden RF config (cross-board sessions)

Any E80↔RP2040 / E80↔ESP32 / RP2040↔ESP32 FLRC session uses EXACTLY:

| Parameter | Value |
|---|---|
| RX sync match | **Match123** (`sync word 1 OR 2 OR 3`) |
| Sync word #1 | **32-bit `0x12AD101B`** |
| Chip CRC | **ON** (2-byte, `FLRC_CRC_2_BYTES`) — never disable cross-board |
| Coding rate | **3/4** (fw `cr` code 1) |
| Preamble | **32 bits** |
| Pulse shape | BT 1.0 |
| BR/BW pairing | per LR2021 datasheet enum (bench default 650 kbps / 0.74 MHz) |

Lineage: sync word + alignment proven in balloon-range-tests commit `9b740aa`
("FLRC byte alignment + app-layer CRC-16 + FIFO clear + sync search", field-proven
on RP2040), adopted on E80 via `5ae1d8a`; Match123 via `c8f459c` (FIX-T3).

The E80-internal legacy symmetric config (sync `2D D4 D4 B2`, Match1-only) works
E80↔E80 only and **MUST NOT** be used cross-board — Match1-only + differing sync
words is the #1 cross-board FLRC breakage mode (harmonization plan §5).

---

## 9. Frequency plan — `FREQ_ALLOWED` per board

| Board tag | Sub-GHz | 2.4 GHz |
|---|---|---|
| `E80BENCH` | 863-870 MHz (enforced in fw; `BAND OVERRIDE <pin>` escape hatch) | — |
| `ESP32BENCH` | 868 MHz default (863-870 window) | 2400-2480 MHz |
| `RP2040BENCH` | 868 MHz default (863-870 window) | 2440 MHz |

- Hosts select session frequency from the **intersection** of both boards' sets and
  MUST refuse non-intersecting configurations before touching hardware.
- 2.4 GHz sessions exist only on the ESP32↔RP2040 pair. E80 is sub-GHz only.
- Cross-board default: 868 MHz band center per host tool.

---

## 10. Board tags (registry)

The `ID?` reply's `<BOARD>` token is the machine-readable board identity:

| Tag | Board |
|---|---|
| `E80BENCH` | STM32F103C8 + LR2021 (this repo) |
| `ESP32BENCH` | ESP32-C3 + LR2021 |
| `RP2040BENCH` | RP2040 + LR2021 |

New boards MUST take a unique tag (one word, `[A-Z0-9]+`, ending in `BENCH` is
conventional) and register it here before cross-board use. Hosts key the tag to the
§9 frequency sets and to board-specific quirks.

---

## 11. Porting checklist

1. **Vendor in verbatim** (freestanding C, zero STM32 deps, shared with host tests):
   `bench_cmd.c/h` (parser + exact ERR strings), `bench_pkt.c/h` (PKT + CONFIG_START
   formatter), `prbs.c/h` (PRBS-15), `bench_payload.c/h` (header + fill),
   `crc16_ccitt_false` (§5). Any modification = spec deviation, document it.
2. Adapt the harness only: console I/O, LR2021 bring-up, role state machine,
   IRQ→event mailbox, STAT? accounting, ID? field population.
3. Golden vectors MUST pass on-target: PRBS fill (§4), pcrc16 `0x29B1`/`0xD6DA`/`0x0F69` (§5).
4. Console drain ≥ 115200-equivalent or handle backpressure; line buffer ≥ 104 chars;
   chunk reply emission to the device TX buffer per call (E80: 160 B per `console_put`).
5. Emit PKT on RX_OK **and** RX_CRC (with RSSI/SNR populated on CRC fails);
   CONFIG_START after every OK CONFIG; TX DONE after burst end.
6. Enforce host-side, in every sweep/ctl tool: LEN caps (§6), GAP ≥ 40 ms for LEN > 256 (§7),
   FREQ intersection (§9), 24/25-column PKT tolerance (§3).

---

## 12. Change control

- Normative source commits at time of writing: `6ff1292` (feat/e80-sweep-results:
  bench_cmd/bench_pkt/prbs/bench_payload) and `88a00cf` (buf/t5a-rx-pcrc16: pcrc16).
- PKT columns are append-only; reply strings are frozen; new commands require a spec
  revision + harmonization-plan task.
- Spec revisions bump the version line at the top and add a changelog entry here:
  - v1.0 (2026-08-21) — initial normative spec (HARM-T1).
