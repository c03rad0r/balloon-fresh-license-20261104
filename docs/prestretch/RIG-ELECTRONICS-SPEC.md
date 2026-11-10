# PRE-STRETCH RIG ELECTRONICS — what the board must do

**Status:** specification derived from existing repo artefacts, not an invention. This corrects an
earlier claim that *"no design exists"* — no **PCB** exists, but the firmware, the interlock module
and its host test suite all do, and they define the hardware contract precisely.

**Sources (all on master `cf32688`):**

| artefact | what it fixes |
|---|---|
| `tools/balloon_pressure_test/` | ESP-IDF project, `main.c` + `interlock.c/h` — the firmware the board must run |
| `tools/balloon_pressure_test/test/test_interlock.c` | **33 assertions**, proves the interlock logic on host |
| `docs/PRESTRETCH-OVERPRESSURE-INTERLOCK.md` | the safety contract: fail-closed valve, alarm, boot self-test |
| `docs/prestretch/PRE-STRETCHING-PROTOCOL.md` §D | sensor wiring, leak-test procedure, acceptance table |
| `docs/prestretch/PRESSURE-TEST-PLAN.md` | sensor choice (BMP280 vs MS5611), serial output format |

---

## The board is a carrier, not a computer

The rig is:

```
[Pump] → [Balloon] → [sensor] → [ESP32-C3] → USB serial
```

There is **no ESP32 on a bare module to design around** — the firmware targets `XIAO ESP32C3` or
`ESP32-C3_Mini_V1`, i.e. **an off-the-shelf dev board**. The PCB therefore does not carry the MCU; it
carries the things a dev board cannot provide: a **fail-closed valve driver**, a **pump relay path**
that shares the same fault line, a **latched alarm**, and **I²C sensor connectors**.

This is a materially smaller board than a v11 hub, and it is why the pre-stretch rig is the one of
the three requests that can realistically be ordered next.

---

## What must be on the board

### 1. I²C sensor header(s) — 4-pin
`SDA` GPIO8, `SCL` GPIO9, `3V3`, `GND` (protocol §D.2). Firmware **auto-detects** the sensor at boot:
BMP280 at `0x76`/`0x77` (chip ID `0x58`) first, then MS5611 at `0x76` (PROM read).

Provide **two** connectors or one shared bus with two footprints — the plan distinguishes
**BMP280 for ground leak testing (300–1100 mbar)** and **MS5611 for full altitude range
(10–1200 mbar)**. Same pins, same bus, so a shared bus with both footprints fitted-or-not works.

Pull-ups: 4.7 kΩ to 3V3 on SDA/SCL if the breakouts do not carry them. Most BMP280 breakouts do;
MS5611 breakouts vary. **Fit the pull-ups** — a duplicate pull-up in parallel is harmless, a
missing one is a dead bus.

### 2. Fill valve driver — NORMALLY CLOSED, energize-to-open
This is the safety-critical part. From `interlock.h`:

> The FILL valve is NORMALLY CLOSED (energize-to-open). The physical output is
> `il_valve_energized()`; it returns true **only** while the interlock is in the ARMED state.

**Any fault, power loss, MCU reset or hung task must de-energise the valve.** So:

- **Low-side switch to a NC solenoid valve**, gate pulled down by a resistor so a floating MCU pin
  (reset, before GPIO init) cannot open the valve.
- **The gate pull-down is not optional.** At reset the ESP32-C3's GPIOs are high-impedance; without
  a pull-down the FET state is undefined and could energise the valve during a brownout.
- Flyback diode across the coil, cathode to the supply rail.
- Gate resistor + the pull-down as a divider, so the values are chosen together.

**Valve voltage is NOT specified anywhere in the repo.** That is the one blocking input: a 5 V
solenoid and a 12 V solenoid need different FETs, different flyback diodes, and different supply
provision. It must be measured off the actual valve the operator buys.

### 3. Pump path — same fail-safe line
> The pump must share the same fail-safe path: either the fill valve is electrically in series with
> the pump, or the pump relay is de-energised-off from the same fault line.

Simplest correct implementation: **one relay/contactor driven from the same enable line as the valve**,
so one fault drops both. Do not give the pump its own independent enable that firmware could leave on.

### 4. Latched alarm output
> Alarm is a separate latched output and must be asserted *on* for a fault.

A latch (the `SN74LVC1G373` already used on the hub cut driver is the same pattern) driving a
buzzer + LED. It must latch because the fault that caused it may also hang the MCU — a firmware-driven
alarm that dies with the firmware is not an alarm.

### 5. Boot self-test access
> Hence the boot self-test (§6).

The board needs a way for firmware to **prove the alarm hardware is healthy** at boot — a feedback
path from the alarm drive (e.g. a sense pin on the driver output, or an LED the firmware can see
through the buzzer's parallel branch). Without it, "de-energised alarm = no alarm" is an assumption,
not a fact.

### 6. Power
The rig runs from USB (the dev board is USB-powered and logs over USB serial). The valve/pump load
must **not** come from USB 5 V — a solenoid will brown out the dev board mid-fill, which is exactly
the failure mode that re-opens the valve. Provide a **separate load supply input** with its own
bulk capacitance, and a common ground.

---

## What is deliberately NOT on the board

- **No MCU.** Off-the-shelf C3 dev board, socketed or on headers.
- **No pump driver electronics.** A mains/12 V pump is switched by a relay module or the valve line;
  putting mains on a 2-layer hobby board is the wrong risk.
- **No load cells / heater.** Nothing in the protocol or the firmware references them. The control
  variable is **circumference**, measured with a tape — see the safety note below.
- **No per-wing multiplexing.** This is a single-balloon bench rig.

---

## The safety note that overrides everything else

Protocol §C.3, quoted in the interlock doc:

> Ruthroff confused 0.31 mbar with 0.31 PSI and **overpressured** his balloons — this caused the
> **JR01–JR06 failures**. Control the **circumference** during pre-stretching, not the pressure.

So **the pressure sensor is a leak detector and a gross over-inflation guard, not a setpoint.**
The interlock doc says this in its own words: the ceiling is set to trip *well below any plausible
burst*, and it is a detector, not a working control.

**A pico balloon is not a pressure vessel, and the repo publishes no ceiling differential at which
the Yokohama laminate fails.** Any board designed here must not create the impression that pressure
control is how inflation is regulated.

---

## The gap in the firmware that the board must not paper over

`main.c` **includes** `interlock.h` and instantiates `g_interlock`, but the header comment is explicit:

> `/* ---- Over-pressure / over-inflation interlock (DESIGN + STUB) ----`
> `* the interlock's boot self-test and then leaves the (notional) fill valve`

Measured: `main.c` contains **no GPIO call that drives a valve, a pump or an alarm** — no
`gpio_set_level`, no valve/alarm/relay constants. The `il_valve_energized()` output is a **logical**
predicate that nothing physical consumes yet.

**This matters for the board design in one specific way:** the firmware currently names no GPIO for
valve, pump or alarm, so **the pin assignment is still free**. Choose it now, record it, and the
firmware change is a few lines. Build the board against a pinout that does not exist in code and you
will be re-working whichever side moves second.

**Proposed pinout** — avoids the strapping pins (GPIO2/8/9 are the C3's boot-sensitive pins, and 8/9
are already I²C) and the USB-JTAG pair (GPIO18/19):

| function | GPIO | why |
|---|---|---|
| I²C SDA | **8** | fixed by firmware `main.c:58` |
| I²C SCL | **9** | fixed by firmware `main.c:59` |
| valve enable (NC, energize-to-open) | **3** | plain GPIO, no strapping role on C3 |
| pump enable (shared fault line) | **4** | plain GPIO |
| alarm drive (latched) | **5** | plain GPIO |
| alarm sense / boot self-test | **6** | input, proves the alarm path is alive |

**Verify against the chosen dev board before layout** — XIAO ESP32C3 and ESP32-C3_Mini_V1 do not
expose identical pin breakouts, and the whole point of a carrier is that its header matches the board
that plugs into it.

---

## What is blocked, and on whom

| item | blocked by |
|---|---|
| valve FET, flyback, supply provision | **valve voltage and coil current** — operator must specify the valve |
| board outline and connector placement | whether the valve/pump mount to the board or are cabled off |
| `dp_cutoff_mbar` (5 mbar placeholder), `dp_reset_mbar` (2), `max_fill_s` (10800) | **Bench session B1**: measure ΔP vs circumference, then set the ceiling well below the first sign of trouble |

**None of the three is a design question I can settle by measuring the repo.** They are physical
facts about hardware that has not been bought yet.

---

## Recommended order of work, if this is the board to build

1. **Operator specifies the valve** (voltage, coil current, NC confirmed by datasheet) and the pump
   switching method. This unblocks 90% of the schematic.
2. Draw the schematic: I²C headers, NC valve driver with gate pull-down, shared pump enable, latched
   alarm with boot self-test feedback, separate load supply.
3. Layout as **2-layer, no impedance control needed** — this board is DC switching and I²C at
   **100 kHz** (measured: `I2C_FREQ_HZ 100000` in `main.c:60`).
4. Order **bare** PCBs; assemble by hand. Nothing here is fine-pitch, and hand assembly keeps the
   safety-critical valve path inspectable.
5. **Bench session B1** sets the real thresholds before the rig is used on a balloon.

Because the firmware and its 33-assertion host test already exist, the PCB is the last missing piece —
but it is blocked on a part that has not been chosen, not on design effort.
