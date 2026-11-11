# ADR-150 — Merge the inflation control onto the base-station control board (one PCB, two functions)

- **Status:** **Accepted by operator** (2026-11-11), direct choice among four options:
  *"Both on one board, the inflator and the tracking radio share one PCB."*
- **Date:** 2026-11-11
- **Supersedes:** **ADR-147 Decision 1** (REJECT the merge) and its **Decision 2** rationale
  (separate boards, one basket) as they apply to the *inflation controller*.
  **ADR-149 is extended, not superseded** — the control-board resipe stands; this adds a second
  function to the same board.
- **Does NOT supersede:** **ADR-088** (differential-pressure basis) — every safety requirement there
  is inherited in full and is a hard precondition (§4). ADR-147's finding that *the base station has
  no ESP32* remains **true and is the reason for the MCU change** in §3.
- **Related:** ADR-087/088 (pressure rig), `docs/PRESTRETCH-OVERPRESSURE-INTERLOCK.md`,
  `tools/balloon_pressure_test/` (firmware contract + 33 host assertions), ADR-145/146/148 (v11).
- **BOM:** `docs/fab/base_station/BOM-RESCOPE.md` (updated in the same change)

---

## Context

ADR-149 turned the base station into a control board with a purchased SPI radio module. Independently,
the operator asked whether the **balloon inflation** function could share that board, and chose
**both on one PCB** over three alternatives (ground-station only, inflation only, or two designs).

ADR-147 had rejected exactly this merge. Its two reasons were:

1. The base station carries an **RP2040, not an ESP32**, so the premise "the sensors could share the
   ESP32" was unavailable.
2. **Cost** — JLCPCB already supports several designs in one basket, one payment, one shipment, so a
   merged board bought nothing financially.

Reason 2 is still true today. **Reason 1 is now solvable by ADR-149 itself**: with the analogue RF
chain retired, the RP2040 is doing far less work, and the board is being re-laid-out anyway. So the
merge is no longer blocked by the MCU — it is blocked by **safety**, which ADR-147 never had to
consider because the two functions were never on the same copper.

---

## Decision 1 — MERGE is approved, with the partition in §2

The board carries both:

| function | what it does | safety class |
|---|---|---|
| **Tracking / telemetry** | SX1276-class SPI module, packets + RSSI + SNR | non-safety |
| **Inflation control** | two MS5611 ΔP sensors, fill valve, pump relay, latched alarm | **SAFETY-CRITICAL** |

Approved because the operator asked for it and because it is *not* inherently unsafe — but only if
the partition below is honoured. A merged board is a **single failure domain**, which is the entire
reason this ADR exists rather than a BOM edit.

---

## Decision 2 — THE PARTITION — safety function may not depend on the non-safety function

This is the governing rule of the record. On one PCB, a fault in the radio section must not be able
to disable the over-pressure guard, and the guard must not depend on software that also drives SPI.

**D1. Independent MCU for the interlock.** The guard runs on its **own** microcontroller, separate
from the one driving the tracking radio. One `U_MCU` serving both is rejected: a hung radio driver,
a blocked SPI transaction or a firmware fault in the telemetry path would take the valve interlock
with it.

**D2. Interlock MCU carries no radio duties and no shared bus with the radio MCU.** No shared SPI
bus, no shared crystal, no shared reset line. Opto-isolation or at least separated ground returns
are preferred between the two domains; if a shared ground plane is unavoidable, it must be stated as
a known common-mode path, not glossed.

**D3. Valve is NORMALLY-CLOSED and de-energises closed.** Loss of power, loss of the interlock MCU,
or a hung GPIO must leave the fill path **closed**. This is inherited verbatim from
`PRESTRETCH-OVERPRESSURE-INTERLOCK.md`: *the valve stays closed (fail-safe)*.

**D4. The pump shares the fail-safe path.** Per the existing interlock doc: the fill valve is
electrically in series with the pump, or the pump relay is de-energised-off from the same fault line.
The pump must never be able to run while the valve is closed unless the plumbing guarantees no path
to the envelope.

**D5. Alarm is a separate LATCHED output, asserted ON for a fault.** A de-energised alarm must not be
mistaken for "healthy" — hence a boot self-test, which the existing firmware contract already
specifies.

**D6. The board cannot by itself make inflation safe.** ADR-088 stands: ΔP = P_internal − P_ambient
with **two MS5611** and pair-specific offset calibration validated against an independent manometer;
target/ramp/dwell/max ΔP remain **UNKNOWN per envelope**; independent pressure relief and pump-off
verification are **mandatory**. Nothing in this ADR qualifies an envelope.

---

## Decision 3 — MCU choice: ESP32-S3 for the interlock domain, RP2040 keeps the radio

ADR-147's objection was factual: *the base station's MCU is an RP2040, not an ESP32.* That finding is
honoured rather than overturned — the merge does not assume the RP2040 can do pressure work.

- **Interlock / pressure domain → ESP32-S3.** It matches the existing `tools/balloon_pressure_test`
  firmware (ESP-IDF), reuses the written interlock state machine and its 33 host assertions, and has
  the I²C + ADC + GPIO the job needs.
- **Tracking domain → RP2040** (already on the board), driving the SPI radio module.

Two MCUs on one PCB is deliberate and is **the safety mechanism**, not an accident of convenience.
Cost: one extra MCU + its decoupling; accepted as the price of an independent guard.

**Open item, must be settled in schematic, not assumed:** the RFM96W breakout is **3.3 V logic only**
(also open in ADR-149). Feeding 5 V destroys it. Both MCUs are 3.3 V logic; the board's 5 V rail and
the module `VIN` tolerance must be reconciled explicitly.

---

## Decision 4 — Board dimensions and partition on copper

ADR-149 noted the board could shrink once the RF chain was released. **The pneumatic half consumes
that saving and more.** The former 60 × 45 mm figure no longer applies; the merged board must be
re-sized from the actual part list, and — per the standing rule — the outline is a **measured**
result, not a guess:

- two MS5611 (one internal tap, one ambient) with separate pressure ports
- valve driver + flyback + series element
- pump relay/switch on the same fault line
- latched alarm + its boot self-test access
- two MCUs with **separated** decoupling and, ideally, separated ground pours
- screw terminals or barbs for the fill line and the pressure taps (physical access matters as much
  as copper)

**The valve/pump copper does not go under or near the RF module.** Switching transients beside a
−137 dBm receiver are an own-goal; the partition in D2 applies to layout, not just to schematics.

---

## Consequences

### Positive
- One board, one order, one assembly — the operator's stated preference.
- The pressure rig stops being a **logger** and becomes a controller with an independent guard.
- ADR-149's RF simplification is reused rather than duplicated.

### Negative / accepted costs
- **Single failure domain.** Mitigated by D1–D5, never eliminated. Stated plainly because a merged
  board cannot be as separable as two boards.
- **More parts, more area** than ADR-149's 26-part control board. That board is no longer the target.
- **Two MCUs** means two firmware images, two SWD headers, and a version-skew risk between them.
- **Mixed safety classes on one PCB** invites a future maintainer to treat the whole board as
  non-safety. The silkscreen and the schematic must both mark the interlock domain.

### Neutral
- ADR-147's cost finding stands: merging saves no money at JLCPCB. This ADR is justified on
  **function and operator preference**, not on price.
- The 2.45 GHz TX port remains untouched.

---

## What this ADR does NOT do

- It does **not** authorise a fabrication order.
- It does **not** qualify any envelope, pressure setpoint, ramp or dwell (ADR-088 remains the
  authority, and those values are UNKNOWN).
- It does **not** claim the hardware fail-safe direction is verified. Per the existing interlock
  record, that *"needs the operator's hands"*: the chosen valve must be proven normally-closed and
  de-energising closed, and the pump must be proven to share the path.
- It does **not** select the final valve, pump or sensor part numbers — the BOM carries candidates
  and requirements, not purchases.
