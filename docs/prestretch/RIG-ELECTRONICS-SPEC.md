# PRE-STRETCH RIG ELECTRONICS — ESP32-S3, not C3

**Status:** specification. **Supersedes the C3 version of this document** (PR #518, merged `81f80f3`).
The C3 assumption was inherited from the bench firmware's target and was the assistant's, not the
operator's decision. The operator's instruction is to design around the **S3**.

**Sources (all on master):**

| artefact | what it fixes |
|---|---|
| `tools/balloon_pressure_test/` | ESP-IDF project, `main.c` + `interlock.c/h` — firmware to RE-TARGET to S3 |
| `tools/balloon_pressure_test/test/test_interlock.c` | **33 assertions**, target-independent pure C, host-tested |
| `docs/PRESTRETCH-OVERPRESSURE-INTERLOCK.md` | safety contract: fail-closed valve, latched alarm, boot self-test |
| `docs/prestretch/PRE-STRETCHING-PROTOCOL.md` §D | sensor wiring, leak-test procedure, acceptance table |
| `docs/prestretch/PRESSURE-TEST-PLAN.md` | sensor choice (BMP280 vs MS5611), serial output format |

---

## First: the v10 order was never affected

Asked directly — *is the placed JLCPCB order built around the C3?* **No.** Measured from the delivered
bundle `docs/fab/v10-order-double-sided/bom-jlc.csv`:

```
U1,U1,ESP32-S3-WROOM-1U,1,C2980300
```

**Zero** ESP32-C3 references in the ordered BOM. The C3 appears **only** in the pre-stretch bench
firmware, which was never part of the hub — it targets a dev board (XIAO ESP32C3 / ESP32-C3_Mini_V1)
and was always a separate bench tool. Nothing was mis-ordered.

---

## The consequence of moving to a bare S3 module

The C3 plan was a **carrier**: an off-the-shelf dev board on headers, with the PCB supplying only the
driver, alarm and sensor connectors. **A bare ESP32-S3 module changes that** — the board must now
provide everything a dev board used to:

| function | on the C3 carrier | on a bare S3 board |
|---|---|---|
| MCU | not on board | **ESP32-S3-WROOM-1-N8R8** |
| 3.3 V regulation | dev board provided it | **must be on the board**, ≥ 500 mA |
| USB flashing | dev board's USB | **USB-C + native USB**, no bridge chip needed |
| Reset / boot buttons | dev board | **must be on the board** |
| 3.3 V bulk decoupling | dev board | **must be on the board** |

This is a real board now, not a carrier. That is the cost of consistency with the hub, and it buys the
same toolchain, the same flashing path and the same module across the project.

### S3 module choice — measured, not assumed

| variant | LCSC | antenna | tier | $ |
|---|---|---|---|---|
| **`ESP32-S3-WROOM-1-N8R8`** | **`C2913201`** | **on-board PCB** | Standard only | **3.4788** |
| `ESP32-S3-WROOM-1U` (hub) | `C2980300` | external, needs U.FL | Standard only | 5.03 |

**Use `C2913201`.** The hub's `-1U` was chosen for a remote antenna on a 72 × 80 mm board. A bench rig
does not need one — the PCB antenna removes the U.FL, the antenna, the matching consideration and
**$1.55 per board**. Stock 6,641. Same `ESP32-S3R8` die, same 8 MB PSRAM (N8R8), same 25.5 × 18 mm land
pattern.

### Native USB — no USB-UART bridge

The S3 has **USB-Serial-JTAG in ROM**, and the hub already relies on it for a first flash. So this board
needs **no CH340, no CP2102, no ESP32-PROG**: USB-C → two series resistors → `GPIO19`/`GPIO20`.

Plus `EN` and `BOOT` buttons and the standard two-transistor auto-reset network, so `esptool` and
`idf.py flash` work without the operator holding a button.

### 3.3 V rail — sized for TX bursts

Module range **3.0–3.6 V**; datasheet peak is **330 mA in TX** (97 mA RX). So: regulator ≥ **500 mA**,
bulk capacitance at the module sized for a burst rather than the average, and **the regulator and its
capacitors kept away from the I²C sensor header**.

That last point is not cosmetic. The instrument is a pressure sensor resolving **0.5 mbar/h** sitting on
the same board as a 330 mA RF transmitter. A BMP280 measuring a leak while its rail dips on every TX
burst is measuring the wrong thing. **On this board the layout is part of the measurement.**

---

## What must be on the board

### 1. I²C sensor headers — 4-pin
SDA `GPIO8`, SCL `GPIO9`, `3V3`, `GND`. Firmware **auto-detects** at boot: BMP280 at `0x76`/`0x77`
(chip ID `0x58`) first, then MS5611 at `0x76` (PROM read).

Provide for **both** — `PRESSURE-TEST-PLAN.md` distinguishes **BMP280 for ground leak testing
(300–1100 mbar)** from **MS5611 for full altitude range (10–1200 mbar)**. Same pins, so two footprints
on a shared bus.

**Fit 4.7 kΩ pull-ups to 3V3** on SDA/SCL. Most BMP280 breakouts carry them; MS5611 breakouts vary. A
duplicate pull-up in parallel is harmless; a missing one is a dead bus.

Bus speed **100 kHz** (measured, `I2C_FREQ_HZ 100000` at `main.c:60`) — no length concern at that rate,
but keep the trace clear of the regulator's switching node.

### 2. Pump driver — one actuator, fail-closed (NO valve, NO release valve)

**Revised 2026-11-10 per operator decision, recorded in ADR-147.** The original design had a
normally-closed fill valve plus a pump, with a shared fault line. The operator's reasoning removes the
valve entirely:

> its safe to assume that the pressure will leak out so we can just run the pump to maintain the
> pressure without needing a release valve

A rig that can only **add** gas needs **one** actuator, and the fail-safe direction becomes trivial:
**pump OFF is safe.** This is strictly simpler than the valve design:

- no NC solenoid to source, so **the valve voltage / coil current question — previously the one
  blocking input — disappears**;
- no flyback diode, no solenoid supply rail;
- a **low-side MOSFET on the pump** with a **gate pull-down** is the whole interlock.

**The gate pull-down is still not optional.** At reset, brownout or a hung task the S3's GPIOs go
high-impedance; the pull-down makes the FET fall to OFF, so no gas is added. That is the fail-safe,
and it costs one resistor.

**Retained from the interlock doc:** the pump enable must fail **closed**, and the alarm must be
**latched** and prove itself at boot — both guard faults the MCU cannot report on itself.

**Still a guard, never a setpoint.** Protocol §C.3: a mbar/PSI unit confusion destroyed balloons
JR01–JR06. A pump that maintains pressure must remain gated by a **hard ceiling**, not a control loop
that trusts the sensor.

### 3. Latched alarm + boot self-test feedback
> Alarm is a separate latched output and must be asserted *on* for a fault.

Latch + buzzer + LED, in the `SN74LVC1G373` pattern already used on the hub's cut driver (`C128413`). It
must latch because the fault that caused it may also hang the MCU — a firmware-driven alarm that dies
with the firmware is not an alarm.

**Plus a sense path** to an input, so the boot self-test can *prove* the alarm hardware is alive.
Without it, "de-energised alarm = no alarm" is an assumption.

### 4. Load supply, separate from logic
The pump load must **not** come from the USB 5 V rail. A pump drawing amps will brown out the regulator
and reset the S3 mid-fill — and a reset is exactly the event the fail-safe exists for, so the board
should not manufacture it. Provide a **separate load supply input** with its own bulk capacitance and a
**common ground**.

---

## What is deliberately NOT on the board

- **No mains switching.** A 12 V DC pump switched by a low-side FET is fine; putting mains on a 2-layer
  hobby board is the wrong risk. The pump itself stays a hand-wired chassis part.
- **No release valve and no fill valve.** Deliberate — see §2 and ADR-147.
- **No load cells / heater.** Nothing in the protocol or the firmware references them. The control
  variable is **circumference**, measured with a tape — see the safety note below.
- **No per-wing multiplexing.** This is a single-balloon bench rig.

---

## GPIO assignment — proposed, because the firmware names none

Measured: `main.c` includes `interlock.h` and instantiates `g_interlock`, but the header comment says
`DESIGN + STUB`, and there is **no `gpio_set_level`** and **no valve/alarm/relay constant** anywhere in
it. `il_valve_energized()` is a **logical predicate that nothing physical consumes**.

So the assignment is still free. Proposed, avoiding the S3's strapping pins (`GPIO0`, `GPIO3`,
`GPIO45`, `GPIO46`), the USB pair (`GPIO19`/`GPIO20`) and the UART0 pair (`GPIO43`/`GPIO44`):

| function | GPIO | note |
|---|---|---|
| I²C SDA | **8** | matches existing firmware `main.c:58` |
| I²C SCL | **9** | matches existing firmware `main.c:59` |
| pump enable (low-side FET, gate pull-down) | **4** | plain GPIO |
| alarm drive (latched) | **5** | plain GPIO |
| alarm sense / boot self-test | **6** | input |
| USB D− / D+ | **19** / **20** | fixed by silicon |

GPIO4–6 are contiguous, all plain I/O on the S3, and route as one short run to the driver block.

Only **one** output now drives gas flow. The firmware's `il_valve_energized()` predicate maps directly
to this single pump enable — the stub wiring is one `gpio_set_level`, not two.

---

## Firmware work this implies

The interlock logic is **target-independent pure C** and already proven on the host:

```
make -C tools/balloon_pressure_test/test check
  test_interlock: 33 passed, 0 failed
  test_plot_pressure: 12 passed, 0 failed
```

What changes for S3:

1. `idf.py set-target esp32s3` in `tools/balloon_pressure_test/`. The I²C driver API and these pin
   numbers are target-agnostic, but **re-run the host test** after.
2. **Wire the stub.** Add the four `gpio_set_level` calls behind `il_valve_energized()` and `il_alarm()`,
   plus the boot self-test read. This is the substantive firmware change.
3. Verify `sdkconfig` flash/PSRAM settings match the **N8R8** (8 MB flash, 8 MB octal PSRAM), not
   whatever the C3 build assumed.

---

## The safety note that overrides everything

Protocol §C.3:

> Ruthroff confused 0.31 mbar with 0.31 PSI and **overpressured** his balloons — this caused the
> **JR01–JR06 failures**. Control the **circumference** during pre-stretching, not the pressure.

**The pressure sensor is a leak detector and a gross over-inflation guard, never a setpoint.** A pico
balloon is not a pressure vessel and the repo publishes no ceiling at which the laminate fails. The
interlock ceiling trips *well below any plausible burst*.

---

## What is blocked, and on whom

| item | blocked by |
|---|---|
| pump FET and supply provision | **pump voltage and current** — operator must specify |
| regulator choice and bulk sizing | load current, and whether logic and load share a supply |
| `dp_cutoff_mbar` (5 placeholder), `dp_reset_mbar` (2), `max_fill_s` (10800) | **Bench session B1** — measure ΔP vs circumference |

**None is a design question the repo can answer.** They are physical facts about hardware not yet bought.

---

## Recommended sequence

1. **Operator specifies the pump** (voltage and current, at startup and running). Much smaller ask than
   the valve question it replaces — and the pump is already in the protocol's parts list.
2. Schematic: S3 module, 3.3 V regulator ≥ 500 mA, USB-C + native USB, EN/BOOT + auto-reset, I²C headers
   with pull-ups, single pump driver (low-side FET + gate pull-down), latched alarm with self-test sense,
   separate load supply for the pump. **No valve of any kind.**
3. Layout **2-layer**. Keep the regulator's switching node and the TX burst current away from the I²C
   sensor run — on this board the layout *is* the measurement.
4. Order with **Standard PCBA** and let JLCPCB place the S3 module. The ESP32-S3-WROOM series is
   **Standard Only** per JLCPCB's own part data. Hand-fitting was considered and rejected in ADR-147:
   the module's **3.90 x 3.90 mm (15.2 mm2) GND thermal pad** sits under the body with no accessible
   edge and needs hot air, so an iron cannot wet it. A partially-wetted thermal pad on an RF module
   gives intermittent resets under TX load. The pump stays hand-wired — it is a chassis part.
5. **Bench session B1** sets the real thresholds before the rig touches a balloon.
