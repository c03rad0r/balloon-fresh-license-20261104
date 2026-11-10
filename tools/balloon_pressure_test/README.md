# Balloon Pressure Test Rig

**MS5611 driver prerequisite:** see [MS5611-MILESTONE.md](MS5611-MILESTONE.md).
Host-verified per-device PROM/CRC and acquisition; paired S3 runtime is not yet
integrated. The legacy single-sensor instructions below are not controller-board
bring-up instructions.

Pressure/temperature logger for balloon leak-rate testing, plus the firmware side
of the over-pressure safety interlock.

## Hardware

- ESP32-C3 (XIAO ESP32C3 or ESP32-C3_Mini_V1)
- **MS5611** breakout — the part the balloon flies (10–1200 mbar, full altitude).
  A **BMP280** (300–1100 mbar) works for a ground leak test but is **ground-only**
  and its calibration does **not** transfer to the flight board. Prefer MS5611 so
  the bench and the flight sensor are the same part.
  The rig auto-detects either part at boot.
- Wiring (both sensors): SDA → GPIO8, SCL → GPIO9, VCC → 3.3 V, GND → GND
- Pump + sealed balloon connection (a pressure tap that seals to the balloon neck)

`docs/PRESTRETCH-OVERPRESSURE-INTERLOCK.md` designs the safety interlock and the
differential-pressure input it still needs. `main/interlock.c` is its firmware
stub: the state machine is real and unit-tested; the sensor/valve hardware is not
wired yet, so the fill valve stays **closed (fail-safe)**.

## Build & Flash

```bash
source ~/esp/esp-idf/export.sh
cd tools/balloon_pressure_test/
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

## Host tests (no hardware)

The interlock logic and the leak-rate analysis are both verifiable on the host:

```bash
make -C tools/balloon_pressure_test/test check
#   -> test_interlock (gcc)      : over-pressure cut-off, fail-closed sensor fault,
#                                  latch/reset, global fail-safe invariant
#   -> test_plot_pressure.py     : fit-based leak rate, sign- and noise-aware verdict
```

## Configure

```bash
idf.py menuconfig
# → Balloon Pressure Test → Measurement interval (default: 30s)
# → Balloon Pressure Test → Over-pressure interlock → cut-off / reset / fill-time
#   (these thresholds are PLACEHOLDERS until bench session B1 derives them)
```

## Output Format

```
[00:00:00] 1050.2 22.3
[00:00:30] 1050.1 22.3
[00:01:00] 1049.9 22.2
```

Columns: `[uptime HH:MM:SS] pressure_mbar temperature_C`

## Log Capture

```bash
idf.py -p /dev/ttyACM0 monitor > pressure_log.txt 2>&1
# Or use screen/pyserial
python3 -m serial.tools.miniterm /dev/ttyACM0 115200 > pressure_log.txt
```

## Analysis

```bash
# --sensor records which part produced the log (bmp280 / ms5611 / auto)
python3 tools/balloon_pressure_test/plot_pressure.py pressure_log.txt \
    --sensor ms5611 --output plot.png
```

Output:
- Data points, duration, start/end values
- **Leak rate from a least-squares fit over every sample (primary number)** — not
  the two endpoints, so one bad sample cannot decide the verdict
- Endpoint rate kept for comparison; fit residual σ and the **noise floor** (the
  smallest rate the log can resolve)
- **Sign- and noise-aware verdict**: a pressure *rise* is reported as a rise, and a
  rate inside the noise band is `INDETERMINATE`, not a pass/fail
- PNG plot (pressure + temperature vs time with the fit line)

## Leak Rate Criteria

| Rate (mbar/h) | Verdict | Flight Ready? |
|----------------|--------|---------------|
| < 0.5 | Very good | Yes |
| 0.5 - 2.0 | OK | Yes (with reserve) |
| 2.0 - 5.0 | Marginal | Restricted |
| > 5.0 | Poor | No — reject |

## Known limits (do not over-read the number)

- The rig measures **internal pressure and temperature only**. It does **not**
  measure circumference/volume (the protocol's *declared* control variable),
  strain, seam stress, creep, burst, gas purity, or lift.
- The temperature term uses the **constant-volume** relation (`ΔP = P·ΔT/T`),
  which does not hold for a stretch envelope. It is reported as an approximation,
  not trusted as a correction.
- The cold soak available is ≈ −18 °C (domestic freezer); the qualification coupon
  asks for ≈ −55 °C.
- A "pressure test passed" is **not** envelope flight-readiness on its own.
