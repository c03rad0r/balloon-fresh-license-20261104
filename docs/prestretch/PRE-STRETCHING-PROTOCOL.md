# Balloon Pre-Stretching and Leak Testing Protocol

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



**Track:** balloon-pre-stretching (physical preparation only)
**Status:** Living document — update as test data arrives

**2026-11-10 precedence:** `DIFFERENTIAL-PRESSURE-BASIS.md` governs pressure measurement and safety. Two MS5611 sensors and an ESP32-S3 are the selected rig; single-BMP280/C3 instructions below are legacy only. No balloon inflation until gates M/S/E pass. Existing circumference targets are process references, not permission to exceed a qualified differential ceiling. Pressure-drop tables alone do not establish flight readiness or true gas loss.
**Sources:** Ruthroff (KC9IKB, 37 flights / 528-day best), KI4MCW (31 flights), K9YO (beginner guide), Yokohama manufacturer, Klofas / SF-HAB, IEEE Spectrum (Schneider)

This protocol covers **physical balloon preparation only**. It does NOT cover firmware, circuit design, antenna, or launch logistics.

---

## Section A — Scope

Two balloon types are in scope. They behave completely differently and require different preparation:

| Property | DecoGlee 18" Foil | Yokohama 32" Crystal Clear |
|----------|-------------------|----------------------------|
| Material | Metalized PET (Mylar / foil) | Nylon / PE laminate |
| Stretches? | **No** — foil is rigid | **Yes** — laminate designed to stretch |
| Pre-stretching required? | No | **Yes — critical** |
| Envelope weight | ~10.5 g | 47 g |
| Net lift (party He) | ~4.8 g/balloon | N/A (use industrial He 4.6) |
| Net lift (He 4.6) | ~5–6 g (est.) | ~20–25 g |
| Gas volume | ~14–15 L | ~70 L |
| Target use | Short shakedown flights (3–5 days est.) | Long-duration (60–500+ days) |
| Proven duration | 25 days indoor leak test | 528 days, 32 circumnavigations (JR29) |

**Key distinction:** DecoGlee balloons are Mylar foil — they do not stretch. "Pre-stretching" does not apply to them; their preparation is inflate → leak test → heat seal → validate lift. Yokohama balloons are a nylon/PE laminate that **must** be pre-stretched with air before filling with lifting gas. Section C (Yokohama) is the main protocol.

---

## Section B — DecoGlee 18" Protocol (Short Shakedown Flights)

DecoGlee 18" round foil balloons are Mylar/PET. They hold their shape rigidly and do **not** stretch. Preparation is a leak-test-and-seal workflow.

### B.1 Physical Properties

- Material: Mylar foil (metalized PET), rigid
- Envelope weight: ~10.5 g
- Net lift with party helium: ~4.8 g/balloon
- Gas volume: ~14–15 L
- Does **not** stretch — pre-stretching does not apply

### B.2 Procedure

1. **Inspect** the balloon for visible defects: seam gaps, pinholes, valve damage. Reject any balloon with visible defects.
2. **HOLD — no numeric inflation pressure is qualified.** Follow `DIFFERENTIAL-PRESSURE-BASIS.md` gates M/S/E; use balloon-specific differential limits, never the withdrawn 1.05 bar instruction. Flight filling is governed separately by the qualified free-lift procedure.
3. **Measure circumference** with measuring tape. Record the value.
4. **Leak test** (electronic — see §D):
   - Short test: hold 2–4 h, log pressure every 30 s.
   - Acceptance: leak rate < 0.5 mbar/h = very good; 0.5–2 mbar/h = OK; > 5 mbar/h = **reject**.
5. **Heat seal the neck.** Do **NOT** rely on the self-sealing valve. Apply **2–3 heat seals** on the nozzle (heat sealer setting **"6"**, ~5 s each), then cover with **Kapton tape**.
   - Do **NOT** use epoxy, superglue, UV epoxy, E6000, model glue, or TPU clamps — **ALL FAILED** in community testing.
6. **Validate free lift** (§E). Target: **4.8 g** net lift per balloon with party helium.

### B.3 Multi-Balloon Cluster Math

- Each balloon provides **4.8 g net lift** (net lift already accounts for envelope weight).
- A **dead** balloon contributes **0 g lift** but still adds **10.5 g dead weight** (its envelope mass).
- For an N-balloon cluster: total net lift = **N × 4.8 g**.
- A **cut-down mechanism is essential** for cluster survival — if one balloon dies the cluster loses lift *and* gains dead weight.

### B.4 Acceptance

| Leak rate | Verdict | Flight ready? |
|-----------|---------|---------------|
| < 0.5 mbar/h | Very good | Yes |
| 0.5 – 2.0 mbar/h | OK | Yes (with reserve) |
| 2.0 – 5.0 mbar/h | Marginal | Restricted |
| > 5.0 mbar/h | Poor | **No — reject** |

### B.5 Party Helium Limitation

Party helium (Amazon, ~80–97% purity) gives only 4.8 g net lift. Ruthroff's data: **0% circumnavigation rate with party He** (0/9 flights). DecoGlee + party He is for **short shakedown flights only** (3–5 days expected). For any flight targeting > 7 days, use Yokohama + He 4.6 (§C).

---

## Section C — Yokohama 32" Protocol (Long-Duration Flights) — MAIN PROTOCOL

Yokohama 32" Crystal Clear Sphere balloons are the community-proven choice for long-duration pico balloon flights (528 days, 32 circumnavigations — Ruthroff JR29). They are a nylon/PE laminate designed to stretch. Pre-stretching is **critical**: an unstretched balloon will be underinflated at launch and may not reach sufficient altitude, or may burst during stretch at altitude.

### C.1 Physical Properties

- Material: nylon/PE laminate (designed to stretch)
- Envelope weight: **47 g**
- Net lift with He 4.6: **~20–25 g**
- Gas volume: **~70 L** (~0.07 m³)
- **Must** be pre-stretched

### C.2 Pre-Stretching Procedure (9 Steps)

**Step 1 — Humidify workspace (24–48 h before).**
Raise workspace humidity to **50–70% RH** for **24–48 hours** before stretching. This is the manufacturer recommendation. (Ruthroff skipped this step on later flights.)

**Step 2 — Two-stage air inflation.**
- Inflate with air to **~85% target circumference (~88")**, hold **2–4 h**.
- Then inflate the remaining distance to **100–116"**. Ruthroff prefers **105"**.

**Step 3 — Hold at stretch circumference.**
Hold at the stretch circumference for **12–48 h**. **Minimum 24 h for first flights.**

**Step 4 — Deflate completely.**
Fully deflate, **~2 h with the pump on suction**.

**Step 5 — Inspect for damage.**
Reject if any tears, pinholes, or seam separation are found.

**Step 6 — Refill with He 4.6.**
Refill with He 4.6 (~0.07 m³ = **70 L**). **The balloon will look underinflated — this is NORMAL.** (The pre-stretch stores slack in the laminate so the balloon can expand at altitude without bursting.)

**Step 7 — Heat seal the nozzle.**
Heat sealer setting **"6"**, ~5 s per seal, **2–3 seals + Kapton tape**.
Do **NOT** use the self-sealing valve, epoxy, superglue, UV epoxy, E6000, model glue, or TPU clamps — **ALL FAILED.**

**Step 8 — Measure free lift.**
Target **5–7 g** free lift. Reference points:
- Ruthroff JR29 = **528 days @ 7 g**
- Ruthroff JR14 = **507 days @ 5 g**
- KI4MCW best = **15 days @ 5.7 g**

Below **5 g** = obstacles risk. Above **8 g** = burst risk.

**Step 9 — Leak test.**
Leak test at launch pressure: **2–4 h minimum, 24 h strongly recommended.**

### C.3 Critical Control-Variable Rule

> **THE CONTROL VARIABLE IS CIRCUMFERENCE, NOT PRESSURE.**

Ruthroff confused 0.31 mbar with 0.31 PSI and **overpressured** his balloons — this caused the **JR01–JR06 failures**. Control the **circumference** during pre-stretching, not the pressure. The BMP280 leak test (§D) measures pressure only to *detect leaks*, never to control inflation.

### C.4 One Stretch Cycle Only

Only **ONE stretch cycle** is needed: inflate → hold → deflate → refill. There is no evidence of any multi-cycle benefit.

---

## Section D — Leak Test Methodology

### D.1 Electronic Setup

```
[Pump] → [Balloon] → [BMP280] → [ESP32-C3] → USB serial
```

The BMP280 measures pressure inside the sealed balloon volume (or a chamber connected to it). The ESP32-C3 reads it over I2C and logs to USB serial.

### D.2 BMP280 Wiring (ESP32-C3)

| BMP280 pin | ESP32-C3 pin |
|------------|--------------|
| SDA | GPIO8 |
| SCL | GPIO9 |
| VCC | 3.3 V |
| GND | GND |

### D.3 Short Test

- Duration: **2–4 h**
- Log interval: every **30 s**
- Acceptance: **< 0.5 mbar/h = good**

### D.4 Long Test

- Duration: **24–72 h**
- Log interval: every **5 min**

### D.5 Temperature Cycling

- Place balloon in freezer at **−18 °C for 4–8 h**.
- Check for seam rupture after return to ambient.
- This stresses heat seals and laminate seams with thermal contraction.

### D.6 Temperature Compensation Formula

Pressure changes with temperature even with no leak. Compensate before computing leak rate:

```
ΔP_temp = P × (T_end − T_start) / T_start
```

where **T is in Kelvin**. Subtract `ΔP_temp` from the measured pressure drop to isolate the true gas loss.

### D.7 Acceptance Table

| Leak rate | Verdict | Flight ready? |
|-----------|---------|---------------|
| < 0.5 mbar/h | Very good | Yes |
| 0.5 – 2.0 mbar/h | OK | Yes (with reserve) |
| 2.0 – 5.0 mbar/h | Marginal | Restricted |
| > 5.0 mbar/h | Poor | **No — reject** |

---

## Section E — Free Lift Measurement

### E.1 Method

1. Put **calibrated weights in a small bag** (non-magnetic — see §E.2).
2. Tape the bag to the balloon neck.
3. **Add gas until neutral buoyancy** (balloon just floats).
4. **Remove the bag.** The weight of the removed bag = the balloon's free lift.

### E.2 Weight Budget (Yokohama)

- Balloon envelope: **47 g**
- Payload: **9–14 g**
- Free lift: **5–7 g**
- **Total: 61–68 g**

### E.3 ⚠ MS300 Scale Warning

The **MS300 jewelry scale CANNOT weigh neodymium magnets** — magnetic interference corrupts the reading. Use **non-magnetic calibrated weights** for all lift measurements.

---

## Section F — Rejection Criteria (Both Types)

Reject a balloon if **any** of the following:

**Physical (both types):**
- Visible tears, pinholes, or holes
- Seam separation
- Valve damage (DecoGlee)
- Any damage found on post-stretch inspection (Yokohama, §C.2 Step 5)

**Leak (both types):**
- Leak rate **> 5.0 mbar/h** after temperature compensation

**Lift:**
- Free lift **below 5 g** (Yokohama — obstacles risk)
- Free lift **above 8 g** (Yokohama — burst risk)
- Free lift below target per-ballon value (DecoGlee — recheck fill)

**Seal:**
- Heat seal fails to hold pressure — re-seal, do not patch with glue (all glues failed, §B.2 / §C.2 Step 7)

---

## Section G — Equipment Checklist

### What Felix HAS

- [x] Yokohama 32" balloons (Crystal Clear)
- [x] Heat sealer
- [x] Kapton tape
- [x] 30× DecoGlee 18" foil balloons
- [x] Pressure sensor + pump
- [x] MS300 jewelry scale (⚠ cannot weigh neodymium magnets — §E.3)
- [x] Digital calipers
- [x] GPS module
- [x] Supercaps

### What Felix NEEDS

- [ ] **Helium source** — party He for DecoGlee shakedown, industrial **He 4.6** for Yokohama long-duration
- [ ] **BMP280 breakout** wired to ESP32-C3 (for electronic leak testing, §D)
- [ ] Non-magnetic calibrated weights (for free lift measurement, §E)
- [ ] Measuring tape (circumference — the control variable, §C.3)
- [ ] Humidifier (workspace 50–70% RH, §C.2 Step 1)
- [ ] Freezer access (temperature cycling, −18 °C, §D.5)
