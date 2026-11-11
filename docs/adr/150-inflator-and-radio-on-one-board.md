# ADR-150 — the inflator and the tracking radio share one board

- **Status:** **Accepted by operator** (2026-11-11) — the operator chose option 3 of a four-way
  question: *"Both on one board, the inflator and the tracking radio share one PCB."*
- **Date:** 2026-11-11
- **Supersedes:** **ADR-147** (`147-no-merge-pressure-rig-into-base-station.md`), whose *Decision 2*
  ("the cost goal is met WITHOUT merging") is now overridden. Everything ADR-147 measured remains
  valid as measurement; its conclusion does not.
- **Depends on:** ADR-149 (base station becomes a control board, RF becomes SMA modules).
- **Related:** ADR-073/072 (radio system), ADR-051/131 (cut topology, wing interface),
  `docs/fab/base_station/BOM-RESCOPE.md`.

---

## Context — why ADR-147's objection no longer holds

ADR-147 rejected the merge on one specific ground, and it was a good ground at the time:

> Merging a **330 mA WiFi transmitter** and a **0.5 mbar/h pressure instrument** onto the same board
> as a **low-noise RF receiver** is the worst combination available in this project […] Merging them
> would put a WiFi radio next to an LNA.

**The LNA is gone.** ADR-149 retired the entire discrete receive chain — `FLT_433_A/B`, `Q_LNA_SW`,
`TEE1/2`, `U_DET`, `U_VGA`, `J_LNA_FEED` — and replaced it with a purchased SX1276-class SPI module.
There is no longer a low-noise 433 MHz front end sitting on this copper to protect. The specific
conflict ADR-147 identified was between **on-board sensitive RF** and **on-board 2.4 GHz aggressor**;
the sensitive RF has left the board.

That does not make the merge free. It changes which risks matter, and they are different risks —
enumerated below rather than dismissed.

---

## Decision

**D1 — One PCB carries both functions.** The tracking radio (control board, post-ADR-149) and the
pressure/inflation controller share a single board.

**D2 — Two MCUs, not one.** The board keeps the **RP2040** for the radio/host side and the
**ESP32-S3** for the pressure/inflation side. They do **not** merge into a single MCU.

This is the significant call, so the reasoning is stated explicitly:

| option | firmware cost | risk |
|---|---|---|
| **two MCUs** (chosen) | **zero** — both existing firmware trees apply unchanged | two parts, two debug interfaces, one inter-MCU link |
| one MCU (ESP32-S3 only) | port the RP2040 USB/host stack | re-does work that is already tested |
| one MCU (RP2040 only) | port the dual-MS5611 acquisition; **lose WiFi** | the inflation side is the safety-critical one; rewriting it to save a part is the wrong trade |

The ESP32-S3 side is the one that can **inflate and cut**. The dual-MS5611 acquisition layer,
calibration separation (ADR-087) and fail-safe interlock were implemented and tested recently;
rewriting that layer purely to remove an MCU would put untested code underneath an actuator. The
RP2040 side owns USB and the host interface and is already working.

**D3 — The interlock stays entirely inside the ESP32-S3.** No path exists by which the RP2040, the
radio, or the USB host can command actuation. The inter-MCU link carries **telemetry only**
(pressure, state, faults). This preserves the pressure rig's existing safety property: actuation is
disabled by construction, not by agreement between processors.

**D4 — Power is shared, and that is the main new risk.** One input rail feeds both sides. Two
constraints become hard requirements rather than preferences:

1. **Pump inrush must not brown out the radio or the MCU rails.** The pump is the largest transient
   load on the board and the radio must keep receiving through it.
2. **Radio TX bursts must not corrupt pressure measurement.** This is the residual of ADR-147's
   concern: it survives, but in the *analog* sense (supply ripple and ground bounce into a device
   resolving sub-mbar), not the RF-coupling sense (no LNA to desensitise).

Both are layout and decoupling problems, and both must be **measured**, not assumed.

**D5 — The 2.4 GHz antenna keep-out is a layout constraint on the pressure side.** The ESP32-S3
module's antenna keep-out now shares a board with the pressure sensing and pneumatic connectors.
Nothing sensitive may occupy it.

**D6 — Nothing is qualified.** No board has been laid out, fabricated or powered up. No pump has run.
No actuation has occurred.

---

## Measured starting point

Footprints and body area measured on the current files (`pcbnew`, body bounding boxes only — not
`GetBoundingBox()` on the footprint, which includes reference text and inflates small parts by ~6×):

| source | footprints | body area |
|---|---|---|
| base station as-is | 44 | 841 mm² |
| base station **after ADR-149** | **26** | **562 mm²** |
| pressure controller (compact) | 26 | 2407 mm² |
| **combined** | **52** | **2970 mm²** |

At the ~60 % packing that the compact pressure board achieved, 2970 mm² of body needs roughly
**5000 mm² of board** — about **70 × 70 mm**. That is an estimate from body area, not a placement.

The pressure side dominates the area (81 %), because it carries two MS5611 breakouts, USB-C, the buck
and the pneumatic port keep-outs.

---

## Consequences

### Positive

- One design, one order, one enclosure, one power input.
- One board to carry and to mount in the ground station.
- The radio and the inflator can share a single telemetry record with a common timestamp.

### Negative / accepted

- **ADR-147's noise concern is reduced, not eliminated.** Supply and ground coupling between a pump
  and a sub-mbar instrument is real. It must be measured on first article.
- **Two MCUs and two firmware trees** on one board — more parts, more debug access needed
  (`J_SWD` for the RP2040, USB for the ESP32-S3).
- **A shared failure domain.** A fault that takes the board down takes the radio *and* the inflator.
  ADR-147's separation gave independent failure. This is the clearest cost of the merge.
- **Bring-up is harder:** two processors to flash and a link to verify before either is trustworthy.

### Neutral

- `J_2450_TX` remains untouched — separate band, separate function, unaffected by either ADR.

---

## What this ADR does NOT do

- It does not authorise a fabrication order or a purchase.
- It does not delete ADR-147. That record stays as the measurement and reasoning that applied
  *before* ADR-149 removed the LNA.
- It does not settle the 3.3 V question from ADR-149 (the SX1276 module's logic and `VIN` tolerance);
  that remains open and now applies to the combined board.
- It does not claim the combined board is safe for flight.

---

## Open items before layout can start

1. **The 3.3 V / 5 V reconciliation for the RF module** (inherited from ADR-149).
2. **Pump current and inrush** — needed to size the shared rail and its bulk capacitance. Not yet
   specified anywhere in the repo.
3. **Which pneumatic interface** the combined board presents: the pressure board's port keep-outs were
   designed for a sealed tap to a balloon neck (see the MS5611 interface drawing, commit `b28cdb8d`).
4. **Whether the radio and inflator still ship as one enclosure**, which decides connector placement.

---

## Reproduce

```bash
/usr/bin/python3 - <<'PY'
import pcbnew
bs = pcbnew.LoadBoard('tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb')
pr = pcbnew.LoadBoard('tracker/hardware/pressure-controller-core/compact/compact.kicad_pcb')
rf = {'FLT_433_A','FLT_433_B','Q_LNA_SW','TEE1','TEE2','U_DET','U_VGA',
      'C_DET1','C_DET2','C_VGA1','C_VGA2','FB_DET','FB_VGA','R_LNA_ILIM',
      'C_LNA1','C_LNA2','C_TAP','J_LNA_FEED'}
keep = [f for f in bs.GetFootprints() if f.GetReference() not in rf]
def area(fs):
    return sum(f.GetBoundingBox(False, False).GetWidth() *
               f.GetBoundingBox(False, False).GetHeight() / 1e12 for f in fs)
print('after ADR-149: %d fps, %.0f mm2' % (len(keep), area(keep)))
print('pressure:      %d fps, %.0f mm2' % (len(pr.GetFootprints()), area(pr.GetFootprints())))
print('combined:      %d fps' % (len(keep) + len(pr.GetFootprints())))
PY
```

`pcbnew` lives in the distro python (`/usr/bin/python3`), not the project venv.
