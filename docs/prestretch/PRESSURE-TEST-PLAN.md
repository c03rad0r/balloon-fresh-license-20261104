# Pressure Test Plan

> **Safety correction — 2026-11-10, [ADR-088](../adr/088-prestretch-differential-pressure-qualification.md).**
> The numerical pressure/pump instructions below are historical, NOT executable.
> Withdraw “1.05 bar” (do not reinterpret as gauge) and the ≥100 kPa pump recommendation.
> Use ΔP = P_internal − P_ambient in Pa/kPa, two MS5611 with same-pressure offset
> calibration and independent manometer validation. Target/ramp/dwell/max remain
> UNKNOWN for each envelope. Independent relief AND pump-off shutdown verification
> are mandatory: leakage and a GPIO pull-down alone are not safety protection.
> Pump actuation is disabled; measurement-only work with pump power disconnected is allowed.
> Historical BMP280, valve, threshold and automatic calibration-transfer claims do not
> override ADR-088. No bench session alone automatically qualifies an envelope.

**Legacy test/firmware reference, NOT current fill authority.** `DIFFERENTIAL-PRESSURE-BASIS.md` supersedes single-sensor measurement, the ambiguous pressure target and automatic flight-readiness claims below. Current rig: ESP32-S3 plus two MS5611 sensors. The firmware output described below is not evidence that paired sampling/control is implemented. Use the new document’s raw/corrected paired-pressure log schema and qualification gates before balloon testing.

---

## 1. Objective

Quantify the gas leak rate of prepared balloons (DecoGlee 18" foil and Yokohama 32" Crystal Clear) by continuously logging internal pressure and temperature, then computing a temperature-compensated leak rate in mbar/h. The output determines whether a balloon is flight-ready (see §6).

---

## 2. Hardware Setup

### 2.1 Components

- ESP32-C3 (XIAO ESP32C3 or ESP32-C3_Mini_V1)
- **BMP280** breakout (ground leak testing) OR **MS5611** breakout (flight sensor, full altitude range)
- Pump + sealed balloon connection

Note: firmware auto-detects sensor at boot. MS5611 covers 10-1200 mbar (full balloon altitude to ~30km), BMP280 covers 300-1100 mbar (ground testing only).

### 2.2 Signal Path

```
[Pump] → [Balloon] → [BMP280] → [ESP32-C3] → USB serial → host PC (CSV capture)
```

### 2.3 Sensor ↔ ESP32-C3 Wiring (BMP280 or MS5611)

| Sensor pin | ESP32-C3 pin | Notes |
|------------|--------------|-------|
| SDA | GPIO8 | I2C data, internal pull-up |
| SCL | GPIO9 | I2C clock, internal pull-up |
| VCC | 3.3 V | do NOT use 5 V |
| GND | GND | |

I2C address auto-detected. Firmware probes for BMP280 (0x76/0x77, chip ID 0x58) first, then MS5611 (0x76, PROM read).

---

## 3. Firmware Description

The firmware already exists at **`tools/balloon_pressure_test/`** — an ESP-IDF project that logs BMP280 or MS5611 readings over USB serial (auto-detects at boot).

- **Build/flash:**
  ```bash
  source ~/esp/esp-idf/export.sh
  cd tools/balloon_pressure_test/
  idf.py build
  idf.py -p /dev/ttyACM0 flash monitor
  ```
- **Configure interval:** `idf.py menuconfig` → Balloon Pressure Test → Measurement interval (default 30 s).
- **Output format (serial):** `[HH:MM:SS] pressure_mbar temperature_C`
  ```
  [00:00:00] 1050.2 22.3
  [00:00:30] 1050.1 22.3
  [00:01:00] 1049.9 22.2
  ```
- **Analysis script:** `python3 tools/balloon_pressure_test/plot_pressure.py pressure_log.txt --output plot.png` — prints data count, duration, raw + temperature-compensated leak rate, and a verdict; renders a pressure/temperature plot.

---

## 4. Test Procedures

### 4.1 Short Leak Test (per balloon, pre-flight gate)

- **Duration:** 2–4 h
- **Log interval:** every **30 s** (firmware default)
- **Balloon:** prepared balloon at launch pressure
- **Pass:** leak rate **< 0.5 mbar/h** (very good); 0.5–2.0 OK
- **Action:** gate to flight — a balloon must pass this before launch.

### 4.2 Long-Term Leak Test (Yokohama pre-flight, strongly recommended)

- **Duration:** 24–72 h
- **Log interval:** every **5 min** (set via menuconfig: `300`)
- **Balloon:** Yokohama 32" at launch pressure, He 4.6
- **Pass:** leak rate **< 0.5 mbar/h** over the full window
- **Action:** confirms long-duration viability; catch slow seam leaks invisible to the short test.

### 4.3 Multi-Balloon Comparison (batch QC for DecoGlee)

- **Setup:** run the short leak test (§4.1) on each balloon in a batch in sequence (or simultaneously on multiple rigs if available).
- **Goal:** rank balloons by leak rate; reject outliers (> 5 mbar/h) before launch.
- **Output:** a table of balloon-ID → leak rate → verdict.

### 4.4 Temperature Cycling Test (seal / seam stress)

- **Setup:** inflate balloon to launch pressure, run the rig.
- **Step 1:** baseline log at ambient for ~1 h.
- **Step 2:** place balloon in freezer at **−18 °C for 4–8 h**, keep logging.
- **Step 3:** return to ambient, log another ~2 h.
- **Pass:** no seam rupture; leak rate within acceptance after temperature compensation (§5).
- **Action:** stress-tests heat seals and laminate seams with thermal contraction.

---

## 5. Data Analysis

### 5.1 Temperature Compensation

Pressure changes with temperature even with no gas loss. Compensate before computing the leak rate:

```
ΔP_temp = P × (T_end − T_start) / T_start
```

where **T is in Kelvin** (K = °C + 273.15). Subtract `ΔP_temp` from the raw measured pressure drop to isolate the true gas loss.

### 5.2 Leak Rate Calculation

```
leak_rate (mbar/h) = (ΔP_measured − ΔP_temp) / Δt_hours
```

The analysis script `tools/balloon_pressure_test/plot_pressure.py` computes both the raw and the temperature-compensated leak rate automatically.

---

## 6. Pass / Fail Criteria

| Leak rate (compensated) | Verdict | Flight ready? |
|--------------------------|---------|---------------|
| < 0.5 mbar/h | Very good | Yes |
| 0.5 – 2.0 mbar/h | OK | Yes (with reserve) |
| 2.0 – 5.0 mbar/h | Marginal | Restricted |
| > 5.0 mbar/h | Poor | **No — reject** |

Additional rejection triggers (from `PRE-STRETCHING-PROTOCOL.md` §F): visible tears/pinholes, seam separation, failed heat seal, free lift out of 5–7 g band (Yokohama).

---

## 7. Data Logging Format

Capture serial output to a CSV for analysis. Recommended columns:

```csv
timestamp,pressure_mbar,temp_c,leak_rate_mbar_h
```

- `timestamp` — wall-clock or uptime (HH:MM:SS or ISO-8601)
- `pressure_mbar` — BMP280 reading
- `temp_c` — BMP280 reading
- `leak_rate_mbar_h` — running compensated leak rate (compute in post, or live if firmware supports)

**Capture command:**
```bash
idf.py -p /dev/ttyACM0 monitor > pressure_log.txt 2>&1
# or
python3 -m serial.tools.miniterm /dev/ttyACM0 115200 > pressure_log.txt
```

The rig's serial format (`[HH:MM:SS] pressure_mbar temp_C`) is space-delimited; convert to CSV for the analysis script if needed.

---

## 8. Pre-Flight Checklist

Run through this before every launch. A balloon must pass all items.

**Rig:**
- [ ] BMP280 wired to ESP32-C3 (SDA=GPIO8, SCL=GPIO9, 3.3 V, GND)
- [ ] Firmware flashed, serial output confirmed
- [ ] Log interval set (30 s short / 300 s long)
- [ ] Capture command running to file

**Balloon (DecoGlee):**
- [ ] Inspected — no defects
- [ ] Gates M/S/E in `DIFFERENTIAL-PRESSURE-BASIS.md` passed; balloon-specific differential limit and approved fill procedure recorded (no universal pressure target)
- [ ] Circumference recorded
- [ ] Short leak test passed (< 0.5 mbar/h, or ≤ 2.0 with reserve)
- [ ] Neck heat-sealed (setting "6", ~5 s, 2–3 seals + Kapton) — NO glue
- [ ] Free lift validated (4.8 g/balloon, party He)

**Balloon (Yokohama):**
- [ ] Pre-stretched (single cycle, circumference-controlled — NOT pressure)
- [ ] Post-stretch inspection passed (no tears/pinholes/seam separation)
- [ ] Refilled with He 4.6 (~70 L; underinflated look is NORMAL)
- [ ] Nozzle heat-sealed (setting "6", ~5 s, 2–3 seals + Kapton) — NO glue / NO self-sealing valve
- [ ] Free lift measured (5–7 g; < 5 obstacles risk, > 8 burst risk)
- [ ] Leak test passed (2–4 h min, 24 h strongly recommended)

**Records:**
- [ ] CSV log saved (timestamp, pressure_mbar, temp_c, leak_rate_mbar_h)
- [ ] Verdict recorded per balloon ID
