# ADR-152 — the valve is chosen by envelope class, not by availability

- **Status:** **Accepted by operator** (2026-11-11) — the operator reviewed the flow model and the
  oversizing argument and directed that the decision be recorded.
- **Date:** 2026-11-11
- **Depends on:** ADR-149 (control board), ADR-150 (inflator + radio on one board, **S1**),
  ADR-151 (pump rail).
- **Supersedes:** the earlier BOM leaning toward the SMC `VQZ1121` as a default choice. That part was
  never bought; this ADR withdraws the *recommendation*, not a purchase.
- **Evidence:** `docs/analysis/valve_fill_flow_model.py` (run output quoted below).

---

## Context — the envelope decides the valve, not the other way round

The natural order — pick a valve, then size everything around it — produces a wrong answer here,
because the flow requirement varies by **two orders of magnitude** across the envelope classes this
project actually names.

Run of `docs/analysis/valve_fill_flow_model.py` (2026-11-11):

```
envelope volumes:  15.0 L .. 1853.3 L   ratio 123.6x

REQUIRED AVERAGE FLOW vs FILL TIME
  envelope                    30 s          120 s         10 min
  18" DecoGlee Mylar      30.00 L/min     7.50 L/min     1.50 L/min
  36" latex              800.64 L/min   200.16 L/min    40.03 L/min
  60" Cymylar           3706.67 L/min   926.67 L/min   185.33 L/min
```

The same candidate valve (`SMC VQZ1121`, Cv 0.19, ≈380 L/min air at 2 bar abs) is:

- **~51× oversized** for an 18" DecoGlee at a 120 s fill,
- **adequate** for a 36" latex,
- **unable to pass it** for a 60" Cymylar, which needs 927 L/min at 120 s.

**One part cannot be correct across that range.** So the decision order is inverted: fix the envelope
class, then size the valve.

---

## Decision

**D1 — No valve is selected until the envelope class is fixed.** This is the primary decision. The
remaining clauses describe the valve that *will* be chosen once it is.

**D2 — The valve is a small, direct-acting, 12 V DC, normally-closed part, in the low single-digit
L/min band.** Sized to the smallest envelope class the project flies, not to the largest.

**D3 — Oversizing is a safety defect, not conservatism.** This ADR corrects an earlier assumption in
this project's BOM work that "bigger is safer". It is backwards here:

- ADR-088 governs pre-stretch, and `DIFFERENTIAL-PRESSURE-BASIS.md` keeps **circumference as the
  Yokohama process endpoint** while differential pressure is the measurement and safety-ceiling basis.
  Both are operator-observed — neither closes the loop in hardware.
- A valve that dumps 15 L in seconds removes the operator's ability to stop in time. That is precisely
  the JR01–JR06 over-pressure failure the interlock exists to prevent.
- A valve that is grossly oversized also makes controlled **ramp rate** harder, which the pressure
  basis requires. Ramp control is a firmware duty-cycle problem, and it is far easier from a valve
  that is only modestly larger than the requirement.

**D4 — Direct-acting is required for S1 to be provable, independent of flow.**

ADR-150 **S1** states the valve is normally-closed and **de-energises closed**. On a **direct-acting**
valve, de-energising removes the only opening force, so S1 is a **structural property** of the part.
On a **pilot-operated** spool valve, de-energising *usually* closes it, but the state depends on pilot
pressure and internal dynamics.

> "Usually" is not a safety claim, and S1 demands proof. Therefore **pilot-operated** valves are
> excluded regardless of their flow rating.

**Scope correction, so this does not overreach.** D4 excludes *pilot-operated* actuation — it does not
ban spool bodies as such. A **direct-acting solenoid spool** valve has the same provable property as a
direct-acting poppet valve: de-energising removes the only opening force. So a direct-acting spool is
**permitted** by D4, subject to S1 being demonstrated on the bench for the exact part.

This matters because `docs/analysis/fill-valve-selection.md` §5 records the flip condition: if the
programme commits to 60" Cymylar envelopes, required flow rises to ~185 L/min even on a 10-minute fill,
a small direct-acting valve cannot pass it, and a `VQZ1121`-class spool valve becomes correct **on flow**
— at which point, in that document's words, "the proof obligation moves to its fail-safe direction
rather than its flow." That is consistent with this ADR: the envelope class decides the size (D1), and
S1 must still be proven (D4), whichever body wins.

**D5 — The pump sets the achievable fill rate; the valve only has to not restrict it.** The model's
flow figures are *averages*, and its own output says so. A valve rated above the pump's free-flow
capability is sufficient — there is no benefit to exceeding it, and a cost to grossly exceeding it (D3).

**D6 — Helium tolerance is a selection criterion, not an afterthought.** The model notes helium leaks
through small clearances faster than air and that its flow figures are for air. Seat and seal
materials must be checked for helium service at the chosen leak rate.

---

## What this ADR does NOT do

- It does **not** name a specific part. D1 forbids that until the envelope class is fixed.
- It does **not** fix the envelope class. That is an operator input.
- It does **not** change ADR-088's circumference endpoint or authorise a pressure-only stretch recipe.
- It does **not** authorise pumping, actuation, fabrication or purchase.
- It does **not** claim any fill time is achievable — the pump is unspecified (ADR-151 sized the rail,
  not the pump).

---

## What the model cannot answer (quoted from its own output)

1. **DP targets remain unknown** per ADR-088 §3 — no setpoint is assumed.
2. **36"/60" volumes are sphere upper bounds**; real foil balloons hold less. The 123.6× spread is
   therefore a *ceiling* on the required flow, and the true spread is smaller but still large.
3. **Gas flow above is air**; helium behaves differently (D6).
4. **Pump capability is not in the repo**, so achievable fill time is unproven.

---

## What would change this decision

| if | then |
|---|---|
| the envelope class is fixed at 18" / pico | D2 holds as written; a low single-digit L/min direct-acting valve is correct |
| the project commits to 36"+ envelopes | D2's flow band must rise; re-run the model at the chosen fill time and re-size |
| a helium-tight seat is unavailable in a small direct-acting body | this becomes a genuine trade-off and needs its own record — do not silently accept a leaky seat |
| a pilot-operated valve is proposed for flow reasons | reject on D4 unless S1 can be demonstrated on the bench, and record the demonstration |

---

## Reproduce

```bash
/usr/bin/python3 docs/analysis/valve_fill_flow_model.py
```

The script prints envelope volumes, required flow at 30 s / 120 s / 10 min, the oversizing factor for
the candidate valve, and its own limitations. Every number in this ADR is copied from that run.
