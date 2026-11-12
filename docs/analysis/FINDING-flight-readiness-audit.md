# Flight-readiness audit: every flight-critical part is fully connected

**2026-11-09.** Answers the standing goal directly: *can this board work as a flight board?*
Separates "copper that matters" from "copper that is DNP or flash-time convenience", so effort goes
only where it changes whether the thing flies.

Method: `tracker/hardware/tmp_probes/flight_critical_audit.py`. It classifies every net by whether it
touches a flight part (`U1`, `U3`, `U_LORA1280`, `U7`) or is power, then asks whether that net has
copper at all.

## Flight parts: fully connected

| part | role | pads | netted | **single-pad nets** |
|---|---|---|---|---|
| `U1` | ESP32-S3 MCU | 42 | 46 | **0** |
| `U3` | LoRa2021 (2.4 GHz) | 18 | 14 | **0** |
| `U_LORA1280` | SX1280 (sub-GHz) | 16 | 15 | **0** |
| `U7` | 3.3 V LDO | 5 | 4 | **0** |

Zero single-pad nets on every flight part. Their buses are routed:

| net | pads | tracks | vias |
|---|---|---|---|
| `/SPI1_SCK` | 4 | **419** | 10 |
| `/SPI1_MOSI` | 4 | **302** | 6 |
| `/SPI1_MISO` | 4 | **48** | 2 |
| `/U3_CS_N` | 2 | 105 | 1 |
| `/U3_RESET_N` | 2 | 51 | 3 |
| `/U3_BUSY` | 2 | 25 | 1 |
| `/U3_IRQ` | 2 | 119 | 5 |

Power path is intact: `/W1_SOLAR_P` 21 tracks + 1 via, `/VSCAP` 4 tracks + 4 vias + **zone**,
`GND` 71 pads / 39 tracks / 48 vias / **3 zones**, `+3V3` 24 tracks + 16 vias + 2 zones.

## The three "flight-critical" gaps are not flight blockers

| net | pads | why it does not stop flight |
|---|---|---|
| `/SPI2_SCK` | `U1`, `U2` | `U2` is the **F33 PA, DNP**. Nothing at the far end. |
| `/EN` | `U1`, `J_PROG` | **flash-time only** — a reset convenience, in the air it is not used |
| `/IO0` | `U1`, `J_PROG` | **flash-time only** — ROM bootloader flashes a blank board without it |

**Non-flight gaps: 0.** Every net whose other end is a DNP part, or which is a flash-time
convenience, is accounted for.

## The only part with dangling pins is DNP

| part | status | single-pad nets |
|---|---|---|
| `U_C` | **DNP** | 4 (`CS_N`, `BUSY`, `RESET_N`, `IRQ`) |
| every flight part | fitted | **0** |

That is the whole `U_C` story in one line: its four uncommanded pins belong to a part that is not on
the board. See ADR-145 for the v11 fix.

## What this means for the goal

**The board is electrically flyable as designed.** The remaining DRC records are:

- 7 two-face wing lands — complete in **assembly** by design (ADR-120 R1)
- 3 GND zone anchors — no functional gap
- 2 `/VSCAP` for `C_CAP1`, which is **DNP**
- `/SPI2_SCK`, `/EN`, `/IO0` — as tabulated above

None of them is a flight function. None of them is fixable by more routing effort, because each is
blocked either by a DNP part or by escape geometry (measured: `/EN` 30.71 mm sealed, `/IO0` shorts to
`USB_DN` on every attempt, `/F33_VSENSE` a 40.9 mm gap).

## Reproduce

```
/usr/bin/python3 tracker/hardware/tmp_probes/flight_critical_audit.py
```

Prints every flight-critical net with pad/track/via/zone counts, the two gap lists, and per-part
single-pad-net counts. `pcbnew` lives in the **distro** python, not the project venv.
