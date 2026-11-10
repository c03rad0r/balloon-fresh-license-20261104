# Pre-Stretch Bench Rig — Over-Pressure / Over-Inflation Interlock

> **Safety correction — 2026-11-10, [ADR-087](adr/087-prestretch-differential-pressure-qualification.md).**
> The numerical pressure/pump instructions below are historical, NOT executable.
> Withdraw “1.05 bar” (do not reinterpret as gauge) and the ≥100 kPa pump recommendation.
> Use ΔP = P_internal − P_ambient in Pa/kPa, two MS5611 with same-pressure offset
> calibration and independent manometer validation. Target/ramp/dwell/max remain
> UNKNOWN for each envelope. Independent relief AND pump-off shutdown verification
> are mandatory: leakage and a GPIO pull-down alone are not safety protection.
> Pump actuation is disabled; measurement-only work with pump power disconnected is allowed.
> Historical BMP280, valve, threshold and automatic calibration-transfer claims do not
> override ADR-087. No bench session alone automatically qualifies an envelope.



**Track:** balloon-pre-stretching · **Status:** DESIGN + STUB — **no hardware test has been run**
**Firmware contract:** `tools/balloon_pressure_test/main/interlock.h` (+ `interlock.c`)
**Host proof:** `tools/balloon_pressure_test/test/test_interlock.c` (33 assertions, `make -C tools/balloon_pressure_test/test check`)
**Related:** `docs/prestretch/PRE-STRETCHING-PROTOCOL.md` §C.2–C.3, `docs/prestretch/PRESSURE-TEST-PLAN.md`, `docs/STATUS-balloon-pre-stretching.md`

> **Read this first.** This document designs a safety interlock. It does **not** contain a
> validated pressure limit, because **no such number exists in this repo and no test has
> been run.** Every threshold below is a **PLACEHOLDER**. The one measured action that
> turns them into numbers is bench session **B1** (`docs/prestretch/PRESTRETCH-BENCH-SESSION-B1.md`).

---

## 1. Why this interlock exists

The protocol names the rig's failure mode in its own words:

> **THE CONTROL VARIABLE IS CIRCUMFERENCE, NOT PRESSURE.**
> Ruthroff confused 0.31 mbar with 0.31 PSI and **overpressured** his balloons — this
> caused the **JR01–JR06 failures.** — `docs/prestretch/PRE-STRETCHING-PROTOCOL.md` §C.3

Today the rig (`tools/balloon_pressure_test`) is a **logger**, not a controller: the pump
runs open-loop and nothing in the firmware can stop an over-inflation. The stated failure
mode is therefore *operator attention only* — a person watching a serial console and a tape
measure. This interlock adds a second, independent guard that acts **without** the operator:
a hard cut-off that closes the fill path and alarms when the differential pressure crosses a
ceiling, plus a redundant fill-time backstop against a stuck-open valve.

**Layering (who guards what):**

| # | Guard | Type | Status |
|---|-------|------|--------|
| 1 | **Circumference** held to the protocol's targets by a tape measure | operator, PRIMARY | exists as procedure |
| 2 | **Firmware interlock** — hard cut-off + alarm | automatic, SECONDARY | **this document** (stub written) |
| 3 | **Passive mechanical relief** on the fill line | hardware, TERTIARY | **proposed, not built** |
| 4 | **Hard fill-time ceiling** (stuck-valve backstop) | automatic | this document (stub written) |

The interlock is deliberately the **second** guard, not the first: the protocol is explicit
that circumference — not pressure — is the control variable, and the pressure interlock is a
*gross over-inflation detector*, not a working setpoint.

---

## 2. What the repo actually says about pressure limits — and what it does NOT

| Claim | Source | Status |
|-------|--------|--------|
| Control variable is **circumference**, not pressure | Protocol §C.3 | **Verified (documented)** |
| Over-pressure (wrong units) caused JR01–JR06 failures | Protocol §C.3 | **Verified (documented)** |
| Ruthroff's error magnitude: 0.31 mbar mis-read as 0.31 psi (≈ 21.4 mbar) | Protocol §C.3 (implied) | Documented; magnitudes are the doc's own |
| DecoGlee inflate target **"1.05 bar"** | Protocol §B.2 | **AMBIGUOUS — absolute or gauge is not stated.** Do not use until clarified (see §6). |
| Free lift **5–7 g** target; **> 8 g = burst risk** | Protocol §C.2 Step 8, §F | Documented (lift, not pressure) |
| Temperature cycling limited to **−18 °C** freezer | Protocol §D.5 | Documented (a rig limit, below the −55 °C coupon ask) |
| **A burst / stretch-limit pressure for Yokohama 32″** | — | **NOT STATED ANYWHERE IN THE REPO → UNKNOWN** |
| **An allowable wall differential pressure** | — | **NOT STATED → UNKNOWN** |

**Conclusion the interlock is built on:** a pico balloon is **not a pressure vessel**, and the
repo publishes **no** ceiling differential at which the Yokohama laminate fails. Standard
practice for a *toy-sized* latex/laminate envelope is single-digit-mbar gauge pressures at
full excursion, and the "burst risk" the protocol names is driven by **free lift and
circumference**, not by a measured burst pressure.

Therefore the firmware ceiling is set to trip **well below any plausible burst** — it is a
*detector of "this is going wrong"*, not a *design limit*. **The number must come from B1.**

> **Unit discipline is part of the safety case.** The JR01–JR06 failures were a *unit* error.
> The interlock works in **mbar of differential pressure, labelled as such, everywhere** — no
> bar/psi ambiguity is permitted at an interface. `il_cfg_t` fields carry the `_mbar` suffix.

---

## 3. The sensor the interlock needs

The interlock needs the **differential pressure across the envelope wall**,
`ΔP = P_internal − P_ambient`, in mbar, fresh every control tick.

### 3.1 The BMP280/MS5611 mismatch — the reason the bench cannot use the current part

The bench rig's stated sensor is a **BMP280** (Protocol §D.1–D.2). BMP280 is a **300–1100 mbar
absolute** sensor: it is **ground-only**. The flight board flies an **MS5611** (10–1200 mbar,
full-altitude). Two consequences:

1. **Calibration does not transfer.** A leak rate/ΔP characterised on a BMP280 tells you
   nothing, numerically, about what the MS5611 on the flight board will read — different
   part, different accuracy class, different range.
2. **The BMP280 cannot see flight altitude at all**, so it can never be the flight sensor.

**Decision (design):** the bench rig's ΔP measurement must use **the part the balloon flies
— MS5611** — so that bench numbers and flight numbers are the same measurement. The existing
ESP-IDF firmware **already has an MS5611 path** (`tools/balloon_pressure_test/main/main.c`)
alongside the BMP280 path; `plot_pressure.py` now takes `--sensor {auto,bmp280,ms5611}` and
labels the range accordingly. BMP280 remains *optional* for a pure ground leak test only.

### 3.2 Options for the differential input

| Option | Parts | Calibration transfers to flight? | Notes |
|--------|-------|----------------------------------|-------|
| **A (recommended)** | **two MS5611** — one internal tap, one ambient | **YES** (same part as flight) | Two absolute readings differenced in firmware. ΔP resolution set by the two parts' noise; MS5611 is a high-resolution barometric part (datasheet ~0.012 mbar class — **verify against the datasheet; not repo-sourced**). |
| B | one MS5611 internal + ambient from a ground reference | partially | Cheaper; loses the independent ambient reading, so a slow ambient drift is not separable from a real ΔP. |
| C | a true differential sensor (e.g. SDP810 / MPXV7002 class) | **NO** | Fast and low-noise, but it is a part that **does not fly** → no calibration transfer, and it is a different measurement chain. |
| D | BMP280 internal + BMP280 ambient | only for ground tests | Ground-only; still cannot be the flight sensor. Superseded by A for anything that must transfer. |

**Design choice: Option A** for the runs whose numbers must transfer to the flight board;
Option D is acceptable for a *ground-only* smoke test where transfer is explicitly not claimed.

### 3.3 Freshness / fault detection

`il_tick()` takes a `sensor_ok` flag. The caller (the rig task) must assert it *false* on:
stale reading (no new sample within N ticks), out-of-range reading, I²C error, or a NaN.
`sensor_ok == false` **fails closed** — see §5.

---

## 4. Firmware logic

Implemented as a pure-C state machine, contract in `main/interlock.h`:

```
                 il_arm()
   IL_IDLE ─────────────────► IL_ARMED ◄──────── il_reset() (only if ΔP < dp_reset
      ▲                          │   │                   AND sensor_ok)
      │                          │   │
      │  il_reset()              │   │  any of:
      │  (condition-aware)       │   ├─ ΔP ≥ dp_cutoff_mbar ........► IL_TRIP_OVERPRESSURE
      └──────────────────────────┘   ├─ sensor_ok == false .........► IL_TRIP_SENSOR_FAULT
                                     ├─ elapsed ≥ max_fill_s .......► IL_TRIP_TIMEOUT
                                     └─ il_abort() ................► IL_TRIP_MANUAL
```

**Rules (each is unit-tested on the host):**

1. **Hard cut-off.** In `IL_ARMED`, when `ΔP ≥ dp_cutoff_mbar` on a *healthy* reading, the
   state latches to `IL_TRIP_OVERPRESSURE` and the valve de-energises **in the same tick**.
2. **Alarm.** `il_alarm()` is true in **every** `IL_TRIP_*` state and false otherwise.
3. **Trips latch.** No trip clears implicitly when the condition goes away. Clearing requires
   an explicit `il_reset()` that *succeeds only* when `sensor_ok` **and** `ΔP < dp_reset_mbar`
   — i.e. the operator has seen the fault and the condition is genuinely gone. A reset while
   still over-pressure is refused.
4. **Sensor fault fails closed.** A missing/invalid reading de-energises the valve and alarms.
   There is **no** "carry on with the last value" path.
5. **Fill-time backstop.** `max_fill_s` closes the fill regardless of pressure — the redundant
   guard against a stuck-open valve or a ΔP input that is silently pinned low.
6. **Global invariant (tested).** `il_valve_energized()` is true in **exactly one** state
   (`IL_ARMED`) and in no alarming state. This is asserted directly in `test_interlock.c`.

**Not yet done (agent-doable, no hardware):** wire the state machine into the fill-control
loop in `main.c` (today it runs `il_selftest()` at boot and stays `IL_IDLE`, valve closed),
and add a GPIO/valve-driver output plus an alarm output. See §7.

---

## 5. FAIL-SAFE direction — the valve must fail CLOSED

This is the safety-critical property and the reason the module is shaped the way it is.

- **The fill valve is NORMALLY CLOSED (energize-to-open).** The physical output is
  `il_valve_energized()`; it is true **only** in `IL_ARMED`.
- **Every fault de-energises the valve**, so the fill path closes.
- **Power loss, MCU reset, or a hung task closes the valve too**, at zero firmware cost:
  de-energised **is the default**, and no code has to run for it to hold. A fail-*open*
  design would instead need firmware to keep it closed — the wrong direction for a gas fill.
- **The pump must share the same fail-safe path**: either the fill valve is electrically in
  series with the pump, or the pump relay is de-energised-off from the same fault line. Do not
  let the pump run on while the valve is closed unless the plumbing guarantees no path to the
  envelope.
- **Alarm is a separate latched output** and must be *asserted on* for a fault (audible/visible),
  so that a de-energised alarm means "no alarm" only if the alarm hardware is proven healthy —
  hence the boot self-test (§6).

**Verification status:** the *logic* of the above is proven on the host (`test_interlock.c`,
33 assertions, incl. the global invariant). The *hardware* fail-safe direction (that the chosen
valve really is normally-closed and de-energises closed; that the pump shares the path) is
**NOT verified — it needs the operator's hands.**

---

## 6. Thresholds, and how they stop being placeholders

| Symbol | Meaning | Present default | Derivation |
|--------|---------|-----------------|------------|
| `dp_cutoff_mbar` | hard ceiling on `P_in − P_amb` | **5 mbar — PLACEHOLDER** | **B1**: measure ΔP vs circumference to the protocol's stretch targets, then set the ceiling **well below** the first sign of trouble. |
| `dp_reset_mbar` | ΔP required before a reset is allowed | **2 mbar — PLACEHOLDER** | **B1**: must be ≤ `dp_cutoff_mbar`. |
| `max_fill_s` | hard fill-time backstop | **10800 s (3 h) — PLACEHOLDER** | **B1**: set above the protocol's 2–4 h low-stage fill but as a backstop. |

These live in `Kconfig.projbuild` (`BALLOON_IL_*`) and are carried in `il_cfg_t`; both files
state they are unvalidated. **Do not fly, and do not treat a pass as a safety margin, on these
numbers until B1 replaces them.**

Also flagged for the operator: Protocol §B.2's **"inflate to 1.05 bar"** does not say whether
that is absolute or gauge. Until that is clarified, no ceiling can be anchored to it — another
reason B1's own measurement, not a quoted number, sets the limit.

---

## 7. What is DESIGN vs what is VERIFIED

| Item | Status |
|------|--------|
| Fail-safe state machine (states, latching, fail-closed direction) | **VERIFIED on host** — 33 assertions pass, no hardware |
| Global invariant: valve energised in exactly one state, never in an alarming state | **VERIFIED on host** |
| Leak-rate analysis is fit-based, sign-aware, noise-aware (rig-side, adjacent concern) | **VERIFIED on host** — 12 Python assertions pass |
| `il_selftest()` boot hook in the rig firmware | **WRITTEN (stub)** — runs at boot, leaves valve closed; not flashed to hardware here |
| `dp_cutoff_mbar` / `dp_reset_mbar` / `max_fill_s` values | **PLACEHOLDER — not validated** |
| Differential-pressure sensor choice (Option A, two MS5611) | **DESIGN — not purchased, not wired** |
| Actually driving a valve GPIO / alarm GPIO from the loop | **NOT IMPLEMENTED** |
| Valve is physically normally-closed and de-energises closed | **NOT VERIFIED — needs operator's hands** |
| Pump shares the fail-safe path | **NOT VERIFIED — needs operator's hands** |
| Passive mechanical relief (guard #3) | **PROPOSED — not sourced, not built** |
| Any bench run producing real ΔP data | **NONE — no hardware test has been performed** |

---

## 8. References

- `docs/prestretch/PRE-STRETCHING-PROTOCOL.md` §B.2 (1.05 bar, ambiguous), §C.2 (9 steps, circumference targets), §C.3 (circumference-not-pressure rule; JR01–JR06), §D.1–D.2 (BMP280 rig), §D.5 (−18 °C freezer), §F (rejection criteria incl. >8 g burst risk)
- `docs/prestretch/PRESSURE-TEST-PLAN.md`, `docs/STATUS-balloon-pre-stretching.md`
- `docs/flight/FLIGHT-TEST-READINESS-2026-07-29.md`, `docs/flight/first-flight-checklist.md`
- `tools/balloon_pressure_test/main/interlock.h`, `interlock.c`, `test/test_interlock.c`
- `docs/prestretch/PRESTRETCH-BENCH-SESSION-B1.md` — the single bench session that de-placeholders §6
