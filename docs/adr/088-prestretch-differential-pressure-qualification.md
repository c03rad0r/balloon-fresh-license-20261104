# ADR-088 — Differential-pressure basis and qualification before pump arm

**Status:** ACCEPTED — explicit operator decision, 2026-11-10.
Originally allocated 087; concurrent PR #536 landed that number first. During the
authorized merge reconciliation, `python3 scripts/adr_next_number.py` returned 88;
this unmerged record and its references move to 088, preserving master’s ADR-087.
This supplements [ADR-087](087-pressure-rig-differential-basis.md) with the
fail-closed host qualification contract; both retain the same accepted design.
Supersedes ADR-147 Decision 5 and its safety consequences, protocol §B.2's
unsourced 1.05 bar instruction, and the rig spec's ≥100 kPa pump recommendation.
Does not supersede the separate-board decision or change any board portfolio scope.

## Decision and rationale

1. The pressure basis is **ΔP = P_internal − P_ambient**, in **Pa** in machine
   interfaces and Pa/kPa in displays (1 kPa = 1000 Pa). Absolute readings remain
   explicitly labelled. Do not reinterpret “1.05 bar” as gauge or as an absolute
   target: that instruction is withdrawn, not converted into a default.
2. Use **two MS5611** sensors, one internal tap and one ambient, with separately
   identified channels. Determine the pair offset with both ports at the same
   pressure, then independently validate the corrected difference against a
   manometer across the intended range and temperature conditions. Record sensor
   identities, offset sign, uncertainty, test conditions and evidence. Same part
   number does NOT automatically transfer calibration to another pair or flight.
3. **Envelope-specific target ΔP, ramp (Pa/s), dwell (s), and maximum ΔP are UNKNOWN.**
   Qualify the exact envelope type/lot and rig; no numerical pressure recipe is
   approved here. Circumference remains an envelope-specific observation/constraint,
   not a substitute for a pressure ceiling. Existing dwell/circumference examples
   are not automatic qualification evidence.
4. Require **independent pressure relief and a pump-off interlock** before any
   actuation. Pump-off stops adding gas; it does not remove trapped pressure.
   Assumed leakage is not relief. A gate pull-down does not necessarily stop a
   hung MCU driving HIGH, nor a shorted MOSFET. Verify the independent shutdown
   path and relief physically, including power loss, hang and stuck-on faults.
5. Missing/unqualified limits, missing calibration or relief/shutdown verification,
   and stale/missing/invalid readings MUST reject pump arm. Software validation
   is a necessary preflight check, **not independent hardware protection** and
   not permission to connect an actuator. Actuation stays disabled until hardware,
   calibration, envelope acceptance and runtime integration are all verified.

## Withdrawals and alternatives

- Withdraw the ≥100 kPa blood-pressure-pump purchase recommendation. Covering both
  interpretations of an unsourced number is not pump sizing. Select a pump only
  after flow, envelope limits and relief capacity are qualified; no purchase here.
- Reject a single absolute sensor as the differential channel: ambient change would
  be conflated with envelope pressure. Two sensors still require error validation.
- Reject natural leakage as protection. No electrically operated vent is mandated
  by this ADR, but independent relief is mandatory and must not depend on software.
- Old protocol/spec/interlock text is preserved as historical claims under explicit
  correction notices. Placeholder firmware thresholds are NOT validated limits.

## Verified research sources — not executable defaults

Both supplied pages were retrieved and read on 2026-11-10:

- [SF-HAB, Preparation of the clear chinese balloons](https://sf-hab.org/2021/10/12/preparation-of-the-clear-chinese-balloons/)
  explicitly describes **0.5 psi differential** for its clear AliExpress balloons,
  held for a couple of days, with a manometer and water-column pressure control.
- [TT7, The Pre-Stretching Rig](https://tt7hab.blogspot.com/2019/07/the-pre-stretching-rig.html)
  describes a differential MPS20N0040D-D/HX711 rig, calibration and temperature/
  pump-flow corrections, and a particular test rising to **7 kPa over 10 hours**.

These are other authors' envelopes and rigs, not qualification of our DecoGlee or
Yokohama stock, not justification for 1.05 bar, and not our MS5611 calibration.
**Neither example may populate an executable default or an accepted limit.**

## Delivery and acceptance boundaries

The current roadmap is `docs/prestretch/ROADMAP.md`; the host-contract status
addendum in `docs/prestretch/PRESTRETCH-WORK-SPLIT-AND-SCHEDULE.md` distinguishes
this completed decision from outstanding
hardware and qualification. The portfolio remains **flight hub, solar/wing
interconnect, pressure rig, and base station**; a shared basket does not remove a board.
Measurement-only logging, same-pressure sensor characterization and host tests may
proceed with pump power disconnected. No inflation trial is authorized by this ADR.
No physical actuation or purchases are part of this change.

Revisit numerical limits only on traceable envelope-specific evidence plus operator
acceptance; changing the envelope, sensor pair, plumbing or relief invalidates the
associated qualification until reviewed. Default-branch delivery is complete only
when the parent merges this PR to master, not when this branch is pushed.
