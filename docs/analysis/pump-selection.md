# Pump selection — what the inflation controller actually needs from it

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** Not an ADR, no authorisation to buy or
> actuate anything. ADR-088 keeps pump actuation **disabled** and leaves ΔP targets **UNKNOWN**.
> ADR-150 governs the merged board; this narrows the pump blocker beside the valve one.

**Date:** 2026-11-11 · **Branch:** `feat/pump-sizing` · **Base:** `origin/master` `192173f4`
**Model:** [`pump_sizing_model.py`](pump_sizing_model.py) — every number below is its own printed
output. Reproduce: `python3 docs/analysis/pump_sizing_model.py`
**Lens:** flow, direction, duty. **Not re-derived:** valve sizing (`fill-valve-selection.md`),
helium thermodynamics, ΔP setpoints.

---

## 0. Answer first — three findings that change the spec

**1. The pump is an AIR pump. It never touches helium.**
The protocol's own pipeline is `[Pump] → [Balloon] → [BMP280] → [ESP32-C3]`, and its Yokohama steps
are explicit: inflate **with air** to ~85 % circumference, hold 12–48 h, deflate **on suction** for
~2 h, **then** refill with He 4.6 (~70 L). Helium arrives from a cylinder through a regulator.

**So helium compatibility and helium flow are not pump requirements at all.** They are *regulator*
requirements. That deletes the largest unknown from the pump spec, and it means the valve study's
"the envelope decides the valve" applies to the **helium** side while the pump is sized by the
**air/pre-stretch** side. They are two different devices with two different sizing logics.

**2. Flow does not decide the pump — direction does.**
Every candidate fills a 32" balloon faster than an operator can watch (26–375 min), and deflate needs
only **2.34 L/min**. But step 2 pushes air in and step 4 pulls it out **with the pump on suction**.
A positive-pressure-only pump **cannot perform step 4 at all**. Measured on the candidates:

| pump | pressure | vacuum | both? |
|---|---:|---:|---|
| BD-03A-3L | 2.00 bar | **0 kPa** | **NO** |
| BD-03V-5L | **0 bar** | 70 kPa | **NO** |
| JSG OD-05TVB-S.1 | 1.25 bar | 70 kPa | **YES** |
| BD-04AB-11L | 2.50 bar | 75 kPa | **YES** |
| Boxer 5KS | 0.30 bar | 50 kPa | **YES** |

**3. During the 12–48 h hold the pump is OFF and the VALVE is under load.**
The pump does nothing for two days; the valve must hold, and the MS5611 must resolve it. An
*acceptable* leak of 2.0 mbar/h loses 6.7 L over 12 h and 26.6 L over 48 h on a 281 L envelope
(2.4 % / 9.5 %) — so the valve is the component that matters across the hold, not the pump.

**Recommendation:** a **dual-direction (pressure + vacuum) 12 V diaphragm pump, ~5 L/min class,
brushless, PWM-driven**. `JSG OD-05TVB-S.1` (5.5 L/min, −70 kPa, 1.0–1.5 bar, 4 W, brushless) fits
every constraint; the `Boxer 5KS` is the low-noise premium option at €74.64 but only 0.30 bar.

---

## 1. What is being moved, and by which device

| target | volume | basis |
|---|---:|---|
| 32" Yokohama (the main protocol) | 281.2 L | sphere, r = 0.4064 m — **upper bound** |
| 36" latex | 400.3 L | sphere — upper bound |
| 60" Cymylar | 1853.3 L | sphere — upper bound |
| 18" DecoGlee Mylar | **15.0 L** | [CITED] protocol §B.1 |
| He refill (32" Yokohama) | **70.0 L** | [CITED] protocol C.4 step 6 |

```
AIR    path : pump     -> valve -> balloon   (pre-stretch + vacuum deflate)
HELIUM path : cylinder -> regulator -> balloon   (NOT the pump)
```

**The sphere volumes are ceilings.** Real foil/laminate balloons hold materially less than a sphere
of the same nominal diameter, so treat 281 L as an upper bound on pre-stretch air.

---

## 2. Inflate — time to fill at rated flow

`t = V / Q` for the 281 L envelope:

| pump | L/min | minutes |
|---|---:|---:|
| BD-01A | 0.8 | 375 |
| BD-02A | 2.2 | 125 |
| BD-03A-3L | 3.0 | 94 |
| BD-03V-5L | 5.0 | 56 |
| **JSG OD-05TVB-S.1** | **5.5** | **51** |
| BD-04AB-11L | 11.0 | 26 |
| Boxer 5KS | 5.1 | 55 |

**These are best cases.** Rated flow is at 0 bar, and the protocol holds the balloon at a raised
pressure, so real flow falls as back-pressure rises. A pump chosen at its rated flow will be slower
in service — which is an argument for the 5 L/min class over the 2–3 L/min class.

**The 0.8–2.2 L/min pumps are genuinely too slow** (2–6 hours to pre-stretch). That is not a
preference; it is the only place where flow *does* eliminate candidates.

---

## 3. Deflate — not a flow constraint, entirely a direction constraint

Required average for a 2 h suction deflate: **2.34 L/min**, which every candidate exceeds.

**But BD-03A-3L has 0 kPa vacuum.** It physically cannot deflate. That single line removes what
would otherwise look like the obvious "3 L/min, 2 bar, cheap" choice.

---

## 4. Hold — the pump is idle and the valve is loaded

| hold | accepted leak | gas lost | share of 281 L |
|---|---:|---:|---:|
| 12 h | 2.0 mbar/h | 6.66 L | 2.37 % |
| 48 h | 2.0 mbar/h | 26.64 L | 9.47 % |

ADR-088 requires **pump-off shutdown to be verifiable** — so the design point is that the pump is
*off* and the system is leak-tested across a day or two. This is why the valve's normally-closed
proof (ADR-150 S1) carries safety weight and the pump's flow does not.

**Sensor side:** a 2 mbar/h acceptance window against an MS5611 with ±2.5 mbar error band over
−20…+85 °C (datasheet) means the *sensor*, not the pump, sets the leak-measurement floor. That is a
calibration problem ADR-088 already names, restated here so it is not mistaken for a pump problem.

---

## 5. What decides the pump — and what does not

| criterion | decides? | evidence |
|---|---|---|
| **direction (pressure AND vacuum)** | **YES** | steps 2 and 4; BD-03A/BD-03V each fail one |
| **flow ≥ ~3 L/min** | **YES, as a floor** | 0.8–2.2 L/min pumps need 2–6 h to pre-stretch |
| **duty / brush life** | **YES** | brushes rated ~1000 h, brushless 3–5×; holds of 12–48 h plus repeat cycles |
| **noise 55–65 dB** | **YES** | hours of running beside a sub-mbar leak measurement |
| **PWM control** | **YES** | a 5 L/min pump at full speed overshoots a fine circumference adjustment |
| **helium compatibility** | **NO** | the pump never sees He — see §1 |
| **helium flow** | **NO** | set by the cylinder regulator |
| **exact flow rating** | **NO** | every viable candidate fills faster than the operator can react |

---

## 6. Recommendation and what flips it

**Recommend: dual-direction 12 V brushless diaphragm, ~5 L/min, PWM-driven.**

- **`JSG OD-05TVB-S.1`** — 5.5 L/min, −70 kPa, 1.0–1.5 bar, 4 W, brushless, 148 g. Fits every
  constraint in §5. **Preferred.**
- **`Boxer 5KS`** — €74.64, 5.1 L/min, 0.30 bar, 50 kPa, 1.5–4 W, 80 g. Premium low-noise option,
  but **0.30 bar** is thin if the envelope ever needs meaningful pressure; note it also loses vacuum
  headroom (50 vs 70 kPa).

**Flips if:** the pre-stretch envelope moves to 60" Cymylar (1853 L upper bound). At 5.5 L/min that
is 5.6 hours of inflation — tolerable but long, and the BD-04AB-11L (11 L/min, 2.5 bar, 75 kPa)
becomes the right class.

**Rejected on numbers:** any single-direction pump, at any flow rating, because step 4 is in the
protocol.

---

## 7. Open items

| item | status |
|---|---|
| ΔP targets, ramp, dwell, max | **UNKNOWN** — ADR-088 §3 |
| Real loaded flow at the protocol's hold pressure | **TODO(unverified)** — ratings above are 0 bar |
| True 32"/60" capacities | **TODO(unverified)** — sphere upper bounds only |
| Pump noise at the operating point | **TODO(unverified)** — vendor figures are 55–65 dB, unmeasured here |
| Whether one dual-direction pump or two single-direction pumps + 3-way valve | **UNDECIDED** — both satisfy §5; two pumps cost more space and a valve |
| Sensor resolution vs the 0.5 mbar/h window | **TODO(unverified)** — MS5611 ±2.5 mbar band vs a 2 mbar/h test is a calibration problem, not a pump one |
