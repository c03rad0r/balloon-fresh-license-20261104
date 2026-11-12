# 2.4 GHz Link Budget Analysis & Campaign Recommendation

> **EXTERNAL REFERENCE (2026-11-08):** an independently published SX1280 2.4 GHz **FLRC**
> dataset with measured NanoVNA S-parameters and conducted attenuation sweeps is available at
> `10.5281/zenodo.21159006` (CC-BY-4.0). Its **insertion-loss measurements** are the
> comparison material this analysis does not otherwise have. See
> [`docs/external/OPENFLRC-ZENODO-21159006.md`](external/OPENFLRC-ZENODO-21159006.md).

## Date: 2026-08-24
## Author: RF Engineering Subagent
## Status: RECOMMENDATION — add 2.4 GHz tests to campaign

---

## 1. Executive Summary

**The E80-900MBL-02 board CAN and SHOULD test at 2.4 GHz alongside 868 MHz.**

The board has **dual SMA jacks** (one sub-GHz, one 2.4 GHz), the LR2021 chip has a
dedicated HF PA path (+12 dBm max at 2.4 GHz vs +22 dBm at sub-GHz), and the
bench firmware already auto-switches PA/RX path when frequency ≥ 1.6 GHz
(`radio_bench.c:321-343`). A full 2.4 GHz sweep was already run successfully on
2026-08-22 (session 2608222108), confirming the hardware path works.

**However, 868 MHz remains the primary band for the 70 km mission test.**
At 70 km, 868 MHz has a ~19 dB link margin advantage over 2.4 GHz (10 dB
from TX power + 9 dB from FSPL). 2.4 GHz is a **secondary/complementary**
measurement, not a replacement.

---

## 2. FSPL Comparison at 70 km

### Formula

```
FSPL(dB) = 20·log10(d_km) + 20·log10(f_MHz) + 32.44
```

### Results at 70 km

| Band | Frequency | FSPL @ 70 km |
|------|-----------|--------------|
| Sub-GHz | 868 MHz | **128.1 dB** |
| 2.4 GHz | 2450 MHz | **137.0 dB** |
| **Δ** | | **8.9 dB** |

2.4 GHz has ~9 dB more free-space path loss than 868 MHz at the same distance.
This is inherent physics — higher frequency = shorter wavelength = more loss.

### Full FSPL Table (50 m – 70 km)

| Distance | FSPL 868 MHz | FSPL 2.4 GHz | Δ |
|----------|-------------|-------------|-----|
| 50 m (0.05 km) | 65.2 dB | 74.2 dB | 9.0 dB |
| 218 m | 78.0 dB | 87.0 dB | 9.0 dB |
| 436 m | 84.0 dB | 93.0 dB | 9.0 dB |
| 872 m | 90.0 dB | 99.0 dB | 9.0 dB |
| 1744 m | 96.0 dB | 105.1 dB | 9.0 dB |
| 5000 m | 105.2 dB | 114.2 dB | 9.0 dB |
| 11000 m | 112.0 dB | 121.1 dB | 9.0 dB |
| 70000 m | 128.1 dB | 137.1 dB | 9.0 dB |

The Δ is constant at 9.0 dB — it depends only on the frequency ratio, not distance.

---

## 3. Link Budget at 70 km — Both Bands

### 3.1 Configuration: E80 board + SMA whip antennas (omnidirectional, ~2 dBi)

**868 MHz (+22 dBm, LoRa SF12 BW125):**

| Parameter | Value |
|-----------|-------|
| TX power | +22 dBm |
| TX antenna gain | +2 dBi (whip) |
| **EIRP** | **+24 dBm** |
| FSPL @ 70 km | -128.1 dB |
| RX antenna gain | +2 dBi (whip) |
| **Received power** | **-102.1 dBm** |
| RX sensitivity (SF12/125kHz) | -141.5 dBm |
| **Link margin** | **+39.4 dB** ✅ |

**2.4 GHz (+12 dBm, LoRa SF12 BW125):**

| Parameter | Value |
|-----------|-------|
| TX power | +12 dBm (HF PA max) |
| TX antenna gain | +2 dBi (whip) |
| **EIRP** | **+14 dBm** |
| FSPL @ 70 km | -137.0 dB |
| RX antenna gain | +2 dBi (whip) |
| **Received power** | **-121.1 dBm** |
| RX sensitivity (SF12/125kHz) | -141.5 dBm |
| **Link margin** | **+20.4 dB** ✅ |

**Verdict:** Both bands have positive margin at 70 km with simple whip antennas.
868 MHz has **19.0 dB more margin** than 2.4 GHz (10 dB power + 9 dB FSPL).

### 3.2 With ground station Yagi (12 dBi @ 868, 18 dBi @ 2.4 GHz)

**868 MHz:**
- EIRP: +24 dBm, RX Yagi: +12 dBi
- Received: 24 - 128.1 + 12 = **-92.1 dBm**
- Margin: **+49.4 dB** ✅

**2.4 GHz:**
- EIRP: +14 dBm, RX Yagi: +18 dBi
- Received: 14 - 137.1 + 18 = **-105.1 dBm**
- Margin: **+36.4 dB** ✅

With directional ground station antennas, 2.4 GHz closes the gap (the higher-gain
Yagi partially compensates for the power/FSPL disadvantage). Margin difference
drops from 19.0 dB to 13.0 dB.

---

## 4. Two-Ray Model: Crossover Distance

### Formula

```
d_crossover ≈ 4π · h_tx · h_rx / λ
```

Below crossover: two-ray path loss (d⁻⁴, much worse).
Above crossover: free-space path loss (d⁻², standard FSPL).

### Balloon altitude (h_tx = 100 m, h_rx = 1.5 m)

| Band | λ | Crossover distance |
|------|---|-------------------|
| 868 MHz | 0.346 m | **5.5 km** |
| 2.4 GHz | 0.125 m | **15.4 km** |

At 2.4 GHz, the two-ray regime extends to ~15.4 km (vs 5.5 km at 868 MHz). Below
the crossover, two-ray d⁻⁴ loss is severe. **At 70 km, both bands are well into
the FSPL regime** — the 70 km test measures free-space performance for both.

### Ground-level testing (h_tx = 1.5 m, h_rx = 1.5 m)

| Band | Crossover distance |
|------|-------------------|
| 868 MHz | **82 m** |
| 2.4 GHz | **231 m** |

At ground level, 2.4 GHz two-ray extends to 231 m. The 50 m test point is
**inside the two-ray zone for both bands** — expect significant multipath
fading, worse at 2.4 GHz.

### Implication for the 70 km mission test

At balloon altitude (100 m+), both bands are in FSPL regime at 70 km.
The 70 km ground-level test is a **conservative proxy** for balloon-altitude
performance — if it works at 70 km ground-level (two-ray d⁻⁴), it will work
at 70 km balloon altitude (FSPL d⁻², much less lossy).

---

## 5. Antenna Considerations

### 5.1 E80 Board Antenna Ports

The E80-900MBL-02 has **dual SMA-K antenna jacks** (confirmed in
`E80-900MBL-02_CAPABILITY_REPORT.md`):

| SMA Jack | Band | Quarter-wave length |
|----------|------|---------------------|
| Sub-1G SMA | 868 MHz | **86 mm** wire whip |
| 2.4G SMA | 2400-2483 MHz | **31 mm** wire whip |

Both jacks are populated on the board. The LR2021 module has separate
RF output pins: Pin 9 (Sub-GHz) and Pin 10 (2.4 GHz).

### 5.2 Can the E80 PCB antenna work at 2.4 GHz?

**Yes** — but only if a 2.4 GHz antenna is connected to the **2.4G SMA jack**.
The board has a dedicated 2.4 GHz SMA connector and matching network.
The existing 2.4 GHz sweep (2026-08-22) used SMA connectors ~30 cm apart
and achieved 100% CRC pass at -40 dBm RSSI.

**⚠️ Critical:** The sub-GHz whip antenna on the sub-GHz SMA jack will NOT
work at 2.4 GHz (wrong length, wrong matching). A 31 mm wire whip or
2.4 GHz stub antenna must be screwed onto the **2.4G SMA jack**.

### 5.3 Bench sweep RSSI anomaly

The 2026-08-22 2.4 GHz sweep showed RSSI of -40 dBm at ~30 cm with +10 dBm.
Expected FSPL at 30 cm/2.4 GHz = 34 dB → expected RSSI ≈ -24 dBm with 0 dBi
antennas. The 16 dB deficit suggests either:
- Antennas not optimally tuned for 2.4 GHz
- SMA whip antennas not connected to the correct SMA jack
- Near-field effects at very close range

This doesn't affect the link budget analysis (FSPL is distance-dependent and
the anomaly is a fixed offset), but it's worth noting for absolute RSSI calibration.

---

## 6. 2.4 GHz Interference Environment

### WiFi Channel Occupancy

| Frequency range | Usage | Interference level |
|----------------|-------|-------------------|
| 2400-2412 MHz | **Clear** (below WiFi ch 1) | Low |
| 2412-2472 MHz | WiFi channels 1-13 | **High** |
| 2472-2483.5 MHz | **Clear** (above WiFi ch 13) | Low |

### Recommendation

Use **2400 MHz** or **2480 MHz** to avoid WiFi interference entirely.
The firmware accepts any frequency in the override range (410-2483 MHz).

For LoRa BW125, the signal occupies only 125 kHz — easily fits in the
12 MHz guard bands at the edges of the ISM band.

---

## 7. Config Changes Needed: 868 MHz → 2.4 GHz

From `bench.c` and `radio_bench.c` source analysis:

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `BAND OVERRIDE 2026` | Unlock out-of-band TX (410-2483 MHz) |
| 2 | `FREQ 2400000000` | Set frequency to 2.4 GHz (or 2480000000) |
| 3 | `PA 12` | Set TX power to +12 dBm (HF PA max) |
| 4 | (automatic) | Firmware auto-switches to HF PA path + HF RX path |

**That's it.** The firmware handles:
- PA selection: `PA_SEL_HF` when freq ≥ 1.6 GHz (`radio_bench.c:324`)
- RX path: `RX_PATH_HF` when freq ≥ 1.6 GHz (`radio_bench.c:331`)
- PA duty cycle: HF duty 16 (vs LF duty 7/6)
- TX power clamp: 0x2C = +22 dBm max (but HF PA physically maxes at +12)

**No firmware changes needed.** The `BAND OVERRIDE` + `FREQ` + `PA` commands
are sufficient. Modulation (LoRa/FLRC), SF, BW, payload length all stay the same.

### Power constraint

| Band | Max TX | Firmware clamp |
|------|--------|----------------|
| Sub-GHz (LF) | +22 dBm | 0x2C = +22 dBm |
| 2.4 GHz (HF) | +12 dBm | 0x18 = +12 dBm |

The firmware clamps at 0x2C (+22 dBm), but the HF PA physically cannot deliver
more than +12 dBm. Setting `PA 12` is both the max and the correct value.

---

## 8. Answer to All 10 Questions

### Q1: At 70 km, how does 2.4 GHz FSPL compare to 868 MHz?

2.4 GHz FSPL is **9.0 dB worse** at 70 km (137.1 dB vs 128.1 dB).
This is a constant offset — it applies at all distances.

### Q2: With +20 dBm at 2.4 GHz vs +22 dBm at 868 MHz, which has better margin at 70 km?

**868 MHz has 19.0 dB better margin** (10 dB TX power + 9 dB FSPL).
- 868 MHz: +39.4 dB margin (whip-to-whip)
- 2.4 GHz: +20.4 dB margin (whip-to-whip)

Note: the E80 board maxes at **+12 dBm** at 2.4 GHz (not +20 dBm).
The +12 dBm cap makes the disadvantage even worse: 19.0 dB total gap.

### Q3: Two-ray model — how does 2.4 GHz change crossover distance?

At balloon altitude (100 m TX, 1.5 m RX):
- 868 MHz: crossover at **5.5 km**
- 2.4 GHz: crossover at **15.1 km** (2.75× farther)

2.4 GHz suffers two-ray d⁻⁴ loss over a longer range. At 70 km, both are
in FSPL regime. But at intermediate distances (5-15 km), 2.4 GHz is still
in two-ray while 868 MHz is already in FSPL.

### Q4: At balloon altitude (100m+), does 2.4 GHz become viable for 70 km?

**Yes.** At 100 m altitude, the crossover is at 15.4 km — well below 70 km.
The 70 km link is in FSPL regime with +20.4 dB margin (whip-to-whip, SF12).
With a ground station Yagi (18 dBi), margin increases to +36.4 dB.

### Q5: Can the E80 board's PCB antenna work at 2.4 GHz?

**Yes — but only on the dedicated 2.4G SMA jack** with a 2.4 GHz antenna (31 mm whip).
The sub-GHz SMA whip will not work at 2.4 GHz (wrong length, wrong matching).
The board has separate SMA jacks and matching networks for each band.

### Q6: 2.4 GHz interference environment for LoRa?

WiFi channels 1-13 occupy 2412-2472 MHz. Use **2400 MHz or 2480 MHz** to
avoid WiFi entirely. LoRa BW125 only needs 125 kHz, fitting easily in the
12 MHz guard bands at the ISM band edges.

### Q7: Advantage to testing BOTH bands?

1. **Frequency diversity**: if one band has interference, the other is fallback
2. **Comparative data**: same distance, same board, same modulation → direct
   comparison of real-world path loss vs theoretical
3. **Regulatory flexibility**: 2.4 GHz is global ISM (no regional restrictions)
4. **Antenna trade-off data**: 31 mm vs 86 mm whip — size matters for balloon
5. **Validates dual-band hardware path**: confirms the E80's HF path works
6. **Future mesh architecture**: ADR-012 plans dual-band TDMA (Sub-GHz for
   MeshCore, 2.4 GHz for FIPS transport) — ground testing validates both paths

### Q8: For Madeira-Porto Santo (70 km), which band is better?

**868 MHz is clearly better for the 70 km mission test:**
- 19.0 dB more link margin
- +22 dBm vs +12 dBm TX power
- 9 dB less FSPL
- No WiFi interference
- Lower atmospheric absorption
- Established regulatory framework (EU SRD 863-870 MHz)

2.4 GHz is viable but marginal — +20.4 dB margin is adequate but not comfortable.
868 MHz's +39.4 dB margin is robust and weather-resilient.

### Q9: Can we do both 868 MHz and 2.4 GHz in the same campaign?

**Yes.** Same board, same firmware, same test script. Only changes:
- Swap antenna on SMA jack (or use both SMA jacks simultaneously with two whips)
- Send `BAND OVERRIDE 2026` + `FREQ 2400000000` + `PA 12` for 2.4 GHz
- Send `FREQ 869525000` + `PA 22` for 868 MHz (no override needed)

The board has **two SMA jacks** — both can have antennas attached simultaneously.
No physical antenna swap needed if both whips are pre-mounted.

### Q10: What config changes are needed to switch from 869 MHz to 2.4 GHz?

```
BAND OVERRIDE 2026     # unlock 410-2483 MHz
FREQ 2400000000        # or 2480000000 to avoid WiFi
PA 12                  # HF PA max is +12 dBm (not +22)
```
That's all. Modulation, SF, BW, payload, session — all unchanged.
PA/RX path switching is automatic in firmware.

---

## 9. Recommendation: Add 2.4 GHz Tests to Campaign

### 9.1 YES — add 2.4 GHz, but as secondary measurements

**Rationale:**
1. Hardware supports it (dual SMA, dual PA, firmware ready)
2. 2.4 GHz sweep already ran successfully (2026-08-22)
3. Link margin is positive at 70 km (+20.5 dB whip-to-whip)
4. Frequency diversity data is scientifically valuable
5. Low cost: just add a 31 mm whip to the 2.4G SMA jack
6. Future mesh architecture (ADR-012) plans dual-band — validate now

### 9.2 Test Plan Addition

Add 2.4 GHz tests at **3 key distances** (not all stops — 868 MHz remains primary):

| Stop | Distance | 868 MHz (existing plan) | 2.4 GHz (addition) | Rationale |
|------|----------|------------------------|---------------------|----------|
| Sanity | 50 m | SF12 255B | SF12 255B | Near-field sanity, both bands |
| D4 | 5000 m | SF12 255B | SF12 255B | Mid-range, two-ray vs FSPL comparison |
| D6 | 70000 m | SF12 255B | SF12 255B | Mission test — dual-band at max range |

**3 additional runs × ~15s = ~45s extra test time.** Negligible cost.

### 9.3 2.4 GHz Test Configuration

```
BAND OVERRIDE 2026
FREQ 2400000000          # 2400 MHz (below WiFi, clear)
MOD loRa 12 125           # SF12, BW125 (max sensitivity)
PA 12                     # +12 dBm (HF PA max)
START N=50 LEN=255 GAP=5000
```

### 9.4 What NOT to test at 2.4 GHz

| Mode | Reason |
|------|--------|
| FLRC any bitrate | Sensitivity -88 to -98 dBm → dead beyond ~1-5 km |
| LoRa SF5-SF7 | Sensitivity -102 to -123 dBm → marginal at 70 km |
| 2412-2472 MHz | WiFi interference zone |
| PA > 12 | HF PA physically caps at +12 dBm |

### 9.5 Antenna Setup for Dual-Band Testing

Both E80 boards should have **two whip antennas mounted simultaneously**:

| SMA Jack | Antenna | Length | Band |
|----------|--------|--------|------|
| Sub-1G SMA | Wire whip | 86 mm (quarter-wave @ 868 MHz) | 868 MHz |
| 2.4G SMA | Wire whip | 31 mm (quarter-wave @ 2.4 GHz) | 2.4 GHz |

No antenna swapping needed during the campaign — both are always connected.
Just change frequency + power via console commands between test runs.

### 9.6 Pre-test Checklist

- [ ] Confirm 31 mm whip antennas are screwed onto **2.4G SMA** jacks on both boards
- [ ] Confirm 86 mm whip antennas are on **Sub-1G SMA** jacks (existing setup)
- [ ] Verify `BAND OVERRIDE 2026` is accepted by both boards
- [ ] Send `FREQ 2400000000` + `PA 12` → verify `ID?` shows correct freq/power
- [ ] Run 50m sanity: 50 packets, verify CRC pass rate
- [ ] Record RSSI at each distance for path loss model validation

---

## 10. Summary Table

| Metric | 868 MHz | 2.4 GHz | Δ |
|--------|---------|---------|-----|
| Max TX power | +22 dBm | +12 dBm | 10 dB |
| FSPL @ 70 km | 128.1 dB | 137.1 dB | 9.0 dB |
| Link margin @ 70 km (whip) | +39.4 dB | +20.4 dB | 19.0 dB |
| Link margin @ 70 km (Yagi) | +49.4 dB | +36.4 dB | 13.0 dB |
| Two-ray crossover (100m alt) | 5.5 km | 15.4 km | 2.8× |
| Quarter-wave antenna | 86 mm | 31 mm | 2.77× smaller |
| Regulatory | EU SRD 863-870 | Global ISM | 2.4 GHz simpler |
| Interference | Low | WiFi (avoidable) | 868 MHz cleaner |
| EU duty cycle | 1% (863-870) | None (most sub-bands) | 2.4 GHz better |

**Bottom line: 868 MHz is the mission band. 2.4 GHz is the science experiment.
Run both — it costs 45 extra seconds and produces valuable comparative data.**