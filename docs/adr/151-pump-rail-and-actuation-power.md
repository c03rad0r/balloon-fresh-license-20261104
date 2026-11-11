# ADR-151 — pump/valve power on the combined board: one switchable rail, sized by measurement

- **Status:** **Accepted by operator** (2026-11-11) — under the standing authority recorded in
  `AGENTS.md` ("make the decision, record the reasoning"), and because the operator's chosen option 3
  (ADR-150, one board for inflator + radio) cannot be laid out without a power answer.
- **Date:** 2026-11-11
- **Depends on:** ADR-149 (control board, RF as modules), ADR-150 (inflator + radio on one board).
- **Relates to:** `docs/analysis/PROGRAM-GAP-ANALYSIS.md` **D11** (pump and safety spec — still open),
  `docs/prestretch/PRE-STRETCHING-PROTOCOL.md`.

---

## Context — why an ADR and not a component choice

ADR-150 merged the inflator onto the radio board. That makes one question unavoidable: **where does
pump current come from, and what stops it disturbing the radio?**

Two facts decide the approach, both measured on the current files:

1. **No pump exists in either design.** The pressure controller has **no actuation net at all** — 52
   nets, zero drivers, no pump connector (measured on `compact.kicad_pcb`, see the reproduce block). Its `30 × 24 mm`
   (720 mm²) "motor/protection reservation" is **unqualified**: a labelled space, not a circuit.
2. **No pump is specified anywhere in the repo.** Grep for a pump/valve part, current, inrush or
   datasheet returns nothing usable. D11 in the program gap analysis records the pump and safety spec
   as an **open decision**, with the recommendation "**(a) or (b), never (c)**" — an over-pressure
   event is the documented balloon-killer.

So the rail cannot be sized from a part number. It can still be **sized by decision rule**, which is
what this ADR does — and the rule is chosen so that the unknown does not block the layout.

---

## Decision

**D1 — The pump gets its own switchable rail, fed from `VIN_GS` directly, not from `+5V_PCBA`.**

The existing 5 V buck is rated **1 A** (`TPS62162`, 3–17 V in). The retired RF loads were the only
large consumers on that rail and ADR-149 removed them, but the pump must still not share it:
a pump inrush on the same regulator as the MCU rail turns a mechanical transient into a logic-level
event. The pump rail is switched **upstream of** the 5 V buck so that pump current never passes
through the regulator that feeds the radio.

**D2 — Size the pump rail against an explicit envelope, and make the envelope a checked value.**

| parameter | value | basis |
|---|---|---|
| input range | 9–18 V nominal, protected | existing `VIN_GS` spec |
| pump rail continuous | **2.0 A** design target | envelope, see D3 |
| pump inrush, 10 ms | **5.0 A** without rail collapse | envelope, see D3 |
| bulk capacitance | ≥ 220 µF low-ESR on the pump rail, ≥ 47 µF on `+5V_PCBA` | sized for the inrush, measured on first article |

**D3 — Justification for those numbers, and what would change them.** They are not a guess at a
particular pump; they are the envelope that covers the pump classes this project can plausibly use
(diaphragm and peristaltic, 6–12 V, small balloon pre-stretch): typically 0.3–1.5 A continuous with
2–4× inrush for a few milliseconds. **2.0 A / 5.0 A sits above the top of that range**, so the rail
is not the binding constraint when the pump is finally chosen.

If the chosen pump exceeds **2.0 A continuous or 5.0 A inrush**, this ADR is **superseded and the
rail re-sized** — the numbers are a decision, not a measurement of hardware that does not exist.

**D4 — Actuation stays inside the ESP32-S3 and stays disabled by construction.** ADR-150 D3 already
puts the interlock entirely in the ESP32-S3 with the inter-MCU link carrying telemetry only. This ADR
adds the power-side counterpart:

- The pump switch is **low-side**, with a **gate pull-down** so an undriven or floating gate is OFF.
- There is **no path** from the radio MCU, the USB host or the RP2040 to the pump switch.
- Firmware `ACTUATION_DISABLED` remains a compile-time constant; the rail being capable of 2 A does
  not mean anything drives it.

**D5 — A mechanical relief is required before any automated fill.** D11's recommendation is adopted
verbatim: "an over-pressure event is the documented balloon-killer; any automated fill must have a
mechanical relief plus a firmware ceiling." The relief is **not** a PCB component and must not be
counted as solved by this ADR.

**D6 — The `30 × 24 mm` reservation is now genuinely spoken for** and must be sized from the real
driver circuit (switch, gate resistor, pull-down, bulk cap, connector), not left as unqualified space.

---

## Consequences

### Positive

- The layout is **unblocked**: the rail has a current budget and a topology, so parts can be placed.
- Pump current cannot brown out the radio — the separation is topological, not defensive.
- The envelope covers the plausible pump range, so the eventual pump choice is unlikely to force a
  board respin.

### Negative / accepted

- **2 A / 5 A is an envelope, not a measurement.** It will be wrong in detail; the design must tolerate
  that, which is why the bulk capacitance is sized for inrush rather than for steady state.
- **A second switching stage** costs area and a part count on a board that is already 52 parts.
- **The relief valve remains an open mechanical item**, and it is the safety-critical one.

---

## What this ADR does NOT do

- It does **not** select a pump. D11 remains open.
- It does **not** authorise actuation, flashing, fabrication or purchase.
- It does **not** claim the combined board is safe for flight, or that pre-stretch automation is
  ready. `docs/prestretch/PRESTRETCH-WORK-SPLIT-AND-SCHEDULE.md` governs that.
- It does **not** change the pressure controller's existing firmware or its interlock.

---

## How to check this decision later

1. When a pump is chosen, read its **continuous current** and **inrush** from its datasheet.
2. If continuous ≤ 2.0 A **and** inrush ≤ 5.0 A → this ADR holds; record the part and move on.
3. Otherwise → supersede this ADR with the measured values and re-size the rail, the bulk capacitance
   and the connector rating **before** layout.

---

## Reproduce the "no pump exists" finding

```bash
cd tracker/hardware/pressure-controller-core
/usr/bin/python3 - <<'PY'
import pcbnew
b = pcbnew.LoadBoard('compact/compact.kicad_pcb')
nets = {str(k) for k in b.GetNetsByName().keys()}
print('total nets:', len(nets))
hits = [n for n in nets if any(t in n.upper() for t in
        ('PUMP', 'VALVE', 'SOLENOID', 'MOTOR', 'ACTUAT', 'RELAY'))]
print('actuation nets:', hits or 'NONE -- this board cannot drive a pump')
PY
```

`pcbnew` lives in the distro python (`/usr/bin/python3`), not the project venv.
