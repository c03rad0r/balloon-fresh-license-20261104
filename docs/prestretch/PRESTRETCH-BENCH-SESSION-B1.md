# Bench Session B1 — Minimal Rig Check and Threshold Derivation

> **Safety correction — 2026-11-10, [ADR-087](../adr/087-prestretch-differential-pressure-qualification.md).**
> The numerical pressure/pump instructions below are historical, NOT executable.
> Withdraw “1.05 bar” (do not reinterpret as gauge) and the ≥100 kPa pump recommendation.
> Use ΔP = P_internal − P_ambient in Pa/kPa, two MS5611 with same-pressure offset
> calibration and independent manometer validation. Target/ramp/dwell/max remain
> UNKNOWN for each envelope. Independent relief AND pump-off shutdown verification
> are mandatory: leakage and a GPIO pull-down alone are not safety protection.
> Pump actuation is disabled; measurement-only work with pump power disconnected is allowed.
> Historical BMP280, valve, threshold and automatic calibration-transfer claims do not
> override ADR-087. No bench session alone automatically qualifies an envelope.



**Status:** SPEC — **not yet run. No hardware test has been performed.**
**Purpose:** the single bench session that (a) proves the interlock's fail-safe direction on
real hardware, (b) derives the `dp_cutoff_mbar` / `dp_reset_mbar` / `max_fill_s` placeholders,
and (c) captures the first real `ΔP`-vs-circumference trace to replace the design doc's guesses.
**Related:** `docs/PRESTRETCH-OVERPRESSURE-INTERLOCK.md`, `docs/prestretch/PRE-STRETCHING-PROTOCOL.md` §C–D

> **This is ONE session.** Roughly 3–4 h of bench time, **no lifting gas**, **no flight**.
> Do not split it: the electrical checks and the ΔP trace must come out of the same rig build.

---

## 1. What to connect

| # | Part | Role | Why this part |
|---|------|------|---------------|
| 1 | **ESP32-C3** running `tools/balloon_pressure_test` | controller + logger | existing rig firmware (MS5611 path present) |
| 2 | **MS5611 #1** on the **internal** pressure tap | measures `P_internal` | **same part the balloon flies** → calibration transfers |
| 3 | **MS5611 #2** on an **ambient** port | measures `P_ambient` | gives a true differential; a BMP280 is **not** acceptable here (300–1100 mbar, ground-only) |
| 4 | **Normally-closed fill valve** (energize-to-open) | the fail-safe actuator | power-off must equal *closed* |
| 5 | **Pump** (hand bulb or electric), ahead of the valve | supply | not required for the electrical checks |
| 6 | **Alarm** (LED/buzzer) | fault indication | separate, latched, asserted-on |
| 7 | **Spare balloon** (a DecoGlee 18″ is fine) or a sealed test bag | the pressure load | a *discardable* envelope, not a flight balloon |
| 8 | **Tape measure** | circumference | the protocol's real control variable (§C.3) |
| 9 | **Multimeter** | continuity across the valve coil | independent confirmation of open/closed |

Wiring: I²C SDA → GPIO8, SCL → GPIO9 (both sensors; two addresses, or two buses), valve drive
→ one GPIO, alarm → one GPIO. **Valve energized only while the interlock reports `IL_ARMED`.**

---

## 2. Procedure and what to record

Log everything to one file — `idf.py -p /dev/ttyACM0 monitor | tee b1_log.txt` — and record
wall-clock time so the ΔP trace and the tape measurements line up.

### Part A — electrical fail-safe checks (do these FIRST, on the bench, no balloon)

| Step | Action | Record | Pass criterion |
|------|--------|--------|----------------|
| A1 | Power up. Read the boot line. | the `INTERLOCK selftest: PASS/FAIL` line | **PASS** (0 failures) |
| A2 | Measure valve coil with the multimeter while idle | continuity = **open** | **CLOSED (de-energised)** |
| A3 | Command `il_arm()` | valve state | **energised = OPEN** |
| A4 | Force `sensor_ok=false` (pull/unplug one sensor) | valve state + alarm | **valve CLOSED, alarm ON, within one tick** |
| A5 | Simulate `ΔP ≥ ceiling` (feed the trip path with an over-threshold value) | valve state + alarm | **valve CLOSED, alarm ON, same tick** |
| A6 | Power-pull mid-`ARMED`, then re-power | valve state | **CLOSED both during and after** |
| A7 | Attempt `il_reset()` while still over-threshold | reset result | **REFUSED** (stays latched) |

**A4–A7 are the fail-safe acceptance. If any fails, stop — the rig is not safe to fill with.**

### Part B — zero / differential sanity (balloon connected but at ambient)

| Step | Action | Record | Pass criterion *(PROPOSED — confirm vs datasheet)* |
|------|--------|--------|------------------------------------------------|
| B1 | Both sensors at ambient, tap open to room | `ΔP` after 2 min | **within ±2 mbar of zero** (datasheet absolute-accuracy scale) |
| B2 | Seal the tap; leave 10 min | `ΔP` drift | drift **≤ 0.5 mbar/h** (the protocol's "very good" leak band, §D.7) |
| B3 | Warm the tap side ~5 °C by hand | sign of `ΔP` | **rises** (ΔP responds to temperature as expected — documents the ΔT coupling) |

### Part C — ΔP vs circumference trace (the number that matters)

Inflate the **discardable** balloon in steps, without lifting gas, and record `ΔP` **at each**
protocol circumference target. Do **not** exceed the protocol's own stretch target.

| Step | Circumference target (protocol §C.2) | Record |
|------|--------------------------------------|--------|
| C1 | low stage ≈ 85 % (~88″) | ΔP, time, T |
| C2 | hold 15 min at C1 | ΔP at start/end |
| C3 | raise toward 100″ | ΔP |
| C4 | raise to Ruthroff's **105″** (protocol target) | ΔP |
| C5 | **stop here** — do not go to 116″ in B1 | — |

**Deliverable of Part C:** a two-column trace `circumference ↔ ΔP`. From it, pick
`dp_cutoff_mbar` = *a value safely above the ΔP at the intended stretch target but far below
anywhere the envelope shows distress* — the operator sets this, because it is a weight-bearing
safety number.

### Part D — derive the thresholds

1. Set `dp_cutoff_mbar` from Part C (a margin above the target-circumference ΔP).
2. Set `dp_reset_mbar` ≤ `dp_cutoff_mbar` (start at ⅓ of it).
3. Set `max_fill_s` above the protocol's 2–4 h low-stage fill.
4. Patch `Kconfig.projbuild` (`BALLOON_IL_*`) with the three numbers and commit.

---

## 3. Acceptance summary (how you know B1 succeeded)

- **A1–A7 all pass** — the valve fails closed on every fault and on power loss; trips latch.
- **B1 within ±2 mbar, B2 ≤ 0.5 mbar/h** — the differential chain is real, not noise.
- **C1–C4 produce a monotonic circumference→ΔP trace** — this is the first real data the
  prestretch programme will have produced.
- **Three Kconfig numbers committed** replacing the placeholders.

## 4. What B1 does NOT do

- It does **not** measure burst pressure (the balloon is not taken near failure).
- It does **not** give `S_crack` (that is the separate, destructive coupon test — it needs
  real 0.21 mm cells and a cold soak the domestic freezer cannot reach, see
  `docs/wing/WING-RIB-PITCH-JUSTIFICATION.md` §5).
- It does **not** qualify the balloon for flight; a leak/ΔP pass is not flight-readiness.

## 5. Explicit statement

**No part of this session has been run.** The ESP-IDF component is not flashed here (an
`idf.py` build needs `source ~/esp/esp-idf/export.sh`, and no valve/sensor hardware is wired).
Everything in §2 is a plan.
