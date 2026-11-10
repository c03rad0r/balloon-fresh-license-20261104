# Pre-Stretching — What Is Blocked on Your Hands, What I Can Do, and the Schedule

## Current roadmap correction — 2026-11-10 (takes precedence over historical schedule)

Portfolio unchanged: **flight hub, solar/wing interconnect, pressure rig, base station**.
This roadmap owns pressure work only; no other board is cancelled or merged.

| Milestone | Status | Artifact / dependency |
|---|---|---|
| Operator design decision | COMPLETE (accepted; master publication pending merge) | [ADR-087](../adr/087-prestretch-differential-pressure-qualification.md), ADR index; replaces H6 ambiguity with explicit ΔP, not a guessed number |
| Pressure contract + host pump-arm qualification validator | COMPLETE, host-tested only | `tools/balloon_pressure_test/pressure-contract.json`, `pressure_contract.py`, `test/test_pressure_contract.py`; unknown limits refuse; runtime integration still OPEN |
| Dual MS5611 measurement chain | OPEN | S3 rig spec; pair identity, same-pressure offset record, independent manometer uncertainty/range/temperature validation; no automatic flight calibration transfer |
| Independent relief and shutdown | OPEN, blocks actuation | physical relief-capacity and pump-off evidence for power loss, hang, stuck-on faults; no reliance on leakage or gate pull-down alone |
| Envelope qualification | OPEN, blocks actuation | exact type/lot; accepted target Pa, ramp Pa/s, dwell s, maximum Pa and evidence; all currently UNKNOWN |
| Runtime enforcement + fault injection | OPEN, blocks actuation | qualified contract + fresh dual inputs + hardware proofs; integration must reject/stop, not merely log a validator result |
| Pump selection | BLOCKED | withdraw ≥100 kPa recommendation; depends on envelope/flow and relief capacity; no purchase authorized |

Measurement-only logging/offset work with pump power disconnected and host tests can
proceed now. Historical B1 inflation steps, placeholder limits, “1.05 bar” question,
C3/valve assumptions and schedule estimates below are NOT current authorization.
Independent manometer validation and envelope acceptance are separate gates; do not
pressurize an unknown envelope to discover its limit under the old B1 instructions.



**Answer to:** *"Pre-stretching — protocol + firmware exist, board does not. What do you need
me to do here? Is there anything you can do to make progress here? If so, please schedule it."*
**Branch:** `analysis/prestretch-progress` · **No hardware test has been run.**

---

## 0. The one-line answer

**Most of what is "blocked" is not blocked on the board — it is blocked on a *number* and a
*safety check* that only a bench session can produce.** I have done every agent-side item that
needs no hands; what remains is (i) **one 3–4 h bench session (B1)** that derives the interlock
thresholds and proves the valve fails closed, and (ii) **the destructive `S_crack` coupon test**,
which additionally needs a cold soak the domestic freezer (−18 °C) cannot reach (−55 °C).

---

## 1. HUMAN / BENCH-BLOCKED (only you can do these)

| # | Item | Why only you | Blocking? |
|---|------|--------------|-----------|
| H1 | **Build/wire the bench rig**: ESP32-C3 + **two MS5611** (internal tap + ambient) + normally-closed fill valve + alarm | physical assembly; the valve must be *confirmed* normally-closed | blocks everything |
| H2 | **Run bench session B1** (`docs/prestretch/PRESTRETCH-BENCH-SESSION-B1.md`) | needs hands, a discardable balloon, a pump, a tape measure | blocks the threshold numbers |
| H3 | **Confirm the valve fails closed** on power-pull (A6) | a physical measurement | blocks the safety case |
| H4 | **Confirm ambient-vs-internal zero** (±2 mbar, B1) | physical | blocks trusting ΔP |
| H5 | **Decide `dp_cutoff_mbar`** from the Part-C trace | a safety number; your call | blocks arming |
| H6 | **Clarify Protocol §B.2 "1.05 bar"** — absolute or gauge? | only you know the intent | blocks anchoring any ceiling to it |
| H7 | **Source the lifting gas** (industrial He 4.6 for Yokohama; party He only for shakedown) | purchasing; and party He gave 0/9 circumnavigations | blocks any real flight |
| H8 | **`S_crack` coupon test** — one real 0.21 mm cell, end-only over growing span, load to 1 g/2 g, load to crack | destructive, specimen-prep, cannot be simulated | blocks rib-pitch freeze |
| H9 | **Provide a −55 °C cold soak** (or accept a documented −18 °C limitation) for the coupon | the freezer only reaches −18 °C | blocks the *cold* `S_crack` |
| H10 | **Free-lift measurement** with non-magnetic calibrated weights (the MS300 cannot weigh neodymium magnets) | physical; needs the weights sourced | blocks launch go/no-go |

## 2. AGENT-DOABLE-NOW (no hands, no hardware) — *done in this branch*

| # | Item | File(s) | Done? | Genuinely hardware-free? |
|---|------|---------|-------|--------------------------|
| A1 | **Over-pressure interlock design doc** | `docs/PRESTRETCH-OVERPRESSURE-INTERLOCK.md` | ✅ written | yes — design |
| A2 | **Interlock firmware (fail-safe state machine)** | `tools/balloon_pressure_test/main/interlock.{h,c}` | ✅ written | yes — pure C, no ESP-IDF deps |
| A3 | **Host unit test proving fail-safe direction** | `tools/balloon_pressure_test/test/test_interlock.c` | ✅ **33/33 pass** (gcc) | yes — host `gcc` |
| A4 | **Wire interlock stub into the ESP-IDF rig** (boot self-test; stays closed) | `main/main.c`, `main/CMakeLists.txt`, `Kconfig.projbuild` | ✅ written | build needs `export.sh`; no sensor/valve needed to compile |
| A5 | **Fix the leak-rate analysis** (fit-based, sign-aware, noise-aware; `--sensor` for the BMP280↔MS5611 mismatch) | `tools/balloon_pressure_test/plot_pressure.py` | ✅ rewritten + 3 fixes | yes — pure Python, no numpy needed |
| A6 | **Host test of the analysis** | `tools/balloon_pressure_test/test/test_plot_pressure.py` | ✅ **12/12 pass** | yes — host `python3` |
| A7 | **Document the BMP280-vs-MS5611 mismatch + the fix** | `README.md`, `PRESTRETCH-OVERPRESSURE-INTERLOCK.md` §3 | ✅ written | yes |
| A8 | **Rib-pitch justification doc, `S_crack` marked UNKNOWN** | `docs/wing/WING-RIB-PITCH-JUSTIFICATION.md` | ✅ written (proposed, not invented) | yes |
| A9 | **Minimal bench session spec** | `docs/prestretch/PRESTRETCH-BENCH-SESSION-B1.md` | ✅ written | yes |
| A10 | **This work split + schedule** | `docs/prestretch/PRESTRETCH-WORK-SPLIT-AND-SCHEDULE.md` | ✅ this file | yes |

### Agent-doable items still open (schedule these)

| # | Item | File it touches | Hardware-free? |
|---|------|-----------------|----------------|
| A11 | Drive a **valve GPIO + alarm GPIO** from the control loop (hal layer) | `main/interlock_io.c` (new), `main/main.c` | yes — code + logic; benched by H3 |
| A12 | Add a **hardware-layer unit test** for the valve/alarm polarity (de-energised default) | `test/test_interlock_io.c` | yes — host test with a GPIO mock |
| A13 | **Capacitive/first-order ΔP→circumference** estimator so B1's trace is auto-tabulated | `tools/balloon_pressure_test/b1_reduce.py` (new) | yes — pure Python |
| A14 | Add **MS5611 driver path documentation** for the bench (two-part address/bus wiring) | `README.md`, `main/` | yes — doc + code review (the path already exists) |
| A15 | Fix the **ADR-110 / ADR-001 number collision** flagged in the ADR index | `docs/adr/INDEX.md` | yes — but needs your decision (see open questions) |
| A16 | **Reconcile `first-flight-checklist.md` item 13** (BMP280 "optional") with the flight MS5611 requirement | `docs/flight/first-flight-checklist.md` | yes — needs your confirmation of intent |

## 3. Kanban-suitable one-line titles

`[HUMAN]` = needs your hands/hardware · `[AGENT]` = no hands needed

```
[HUMAN] Build prestretch bench rig: ESP32-C3 + 2x MS5611 + normally-closed fill valve + alarm
[HUMAN] Run bench session B1: electrical fail-safe checks A1-A7 (valve must fail closed)
[HUMAN] B1 Part B/C: measure ambient zero (+/-2 mbar) and record DP-vs-circumference trace
[HUMAN] Set dp_cutoff_mbar / dp_reset_mbar / max_fill_s from B1 Part C, patch Kconfig, commit
[HUMAN] Clarify PRE-STRETCHING-PROTOCOL.md B.2 "inflate to 1.05 bar" - absolute or gauge?
[HUMAN] Source industrial He 4.6 (long-duration) and party He (shakedown only)
[HUMAN] Run S_crack coupon: one 0.21mm cell, end-only span to crack, record S_crack
[HUMAN] Provide -55C cold soak for S_crack coupon (or accept documented -18C limitation)
[HUMAN] Measure free lift with non-magnetic calibrated weights (MS300 unusable for magnets)
[AGENT] Implement valve+alarm GPIO hal layer driving the interlock state machine
[AGENT] Add host unit test for valve/alarm polarity (de-energised is the safe default)
[AGENT] Add b1_reduce.py to tabulate DP-vs-circumference and suggest a cutoff
[AGENT] Document MS5611 two-part bench wiring and address/bus configuration in README
[AGENT] Resolve ADR-110/ADR-001 numbering collision in docs/adr/INDEX.md
[AGENT] Reconcile first-flight-checklist item 13 (BMP280 optional) with flight MS5611 rule
```

## 4. Proposed schedule

1. **Now (done in this branch):** A1–A10 — all hardware-free work committed.
2. **You, ~30 min:** confirm H6 ("1.05 bar" ambiguity) and H4's intent; source a
   normally-closed valve and a second MS5611 (H7/H1 parts).
3. **Next agent session:** A11–A14 (GPIO hal, its host test, the B1 reducer, MS5611 wiring doc)
   — all of it compiles and tests without hardware, so it is ready the moment the rig is built.
4. **You, one bench session (B1, 3–4 h):** H1–H5. This *unblocks* the threshold numbers and
   the safety case. Nothing else can substitute.
5. **You, one destructive session:** H8 (and H9 for the cold number). This *unblocks* the
   rib-pitch freeze.
6. **Then:** H10 (free lift), gas, and a real leak test on a flight balloon.

## 5. The minimum bench session that unblocks the `S_crack` coupon

`S_crack` is blocked **purely on your hands** — no agent action produces it. The minimum is:

> **Take one real 0.21 mm × 78.55 × 38.90 mm cell. Support it end-only (no bond) over a gap
> `S`. Load to 1 g, then 2 g. Increase `S` until it cracks. Record `S_crack` and the surface
> strain at first damage.** — `docs/wing/WING-RIB-PITCH-JUSTIFICATION.md` §5, ADR-063 §6

That needs **no board**. It needs: the cells (you have them), a span fixture, a way to apply a
known load, and a way to find the crack. The −55 °C repeat (H9) additionally needs cold soak
the freezer cannot reach. **B1 (the pressure rig) and the `S_crack` coupon are independent** —
B1 is not a prerequisite for the coupon, and vice versa.

## 6. Open questions for you

1. **Protocol §B.2 "inflate to 1.05 bar"** — absolute or gauge? (blocks anchoring any ceiling)
2. **Bench sensor** — confirm the rig moves to **MS5611** (flight part) and drops the "BMP280"
   wording, so calibrations transfer. `first-flight-checklist.md` item 13 still says BMP280 is
   "optional" — reconcile?
3. **Rig cold soak** — accept the **−18 °C** limit as documented, or obtain a −55 °C source?
4. **ADR numbering** — `110-tollgate-over-lr2021.md` collides with `001`; which wins?
