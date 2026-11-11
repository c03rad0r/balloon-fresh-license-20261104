# Fill valve selection — what flow the inflation controller actually needs

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** This is not an ADR, not an operator
> decision, and it authorises no purchase and no inflation. ADR-088 keeps pump actuation **disabled**
> and leaves every ΔP target **UNKNOWN per envelope**. ADR-150 remains the authority on the merged
> board; this study only narrows the valve blocker it names.

**Date:** 2026-11-11 · **Branch:** `feat/control-board-v1` · **Base:** `origin/master` `74f4312f`
**Model:** [`valve_fill_flow_model.py`](valve_fill_flow_model.py) — every number below is its own
printed output. Reproduce: `python3 docs/analysis/valve_fill_flow_model.py`
**Lens:** flow, coil, fail-safe direction. **Not re-derived:** pump capability (absent from the repo),
helium thermodynamics, ΔP setpoints (withdrawn by ADR-088).

---

## 0. Answer first

**The candidate valve is not flow-limited for the small envelope, and the envelope — not the valve —
is the decision variable. Do not select a valve until the envelope class is fixed.**

1. **An 18" DecoGlee Mylar holds 15 L** [CITED `PRE-STRETCHING-PROTOCOL.md` B.1]. A 2-minute fill
   needs **7.50 L/min**. The SMC VQZ1121's quoted Cv of 0.19 works out to roughly **380 L/min** of air
   — an **~51× oversizing**.
2. **A 60" Cymylar is 123× larger** — 1853 L as a sphere upper bound. A 2-minute fill needs
   **927 L/min**, which the same valve **cannot** pass. At a 10-minute fill it needs 185 L/min and
   just fits.
3. **So the same valve is grossly oversized for one envelope and inadequate for another.** Any valve
   recommendation made before the envelope is chosen is a guess wearing a number.
4. **Oversizing is not free.** A grossly oversized valve makes a controlled ramp harder, because the
   minimum controllable increment is a larger fraction of the target. ADR-088's control variable is
   circumference held by a **taper measure**, so a valve that fills 15 L in seconds removes the
   operator's ability to stop in time — which is the exact failure mode (JR01–JR06 overpressuring)
   the interlock exists to prevent.
5. **Recommendation:** for pico-balloon work, a **small direct-acting 12 V normally-closed valve** in
   the low single-digit L/min class, not the $45 spool valve. The VQZ1121 stays on the table only if
   the programme moves to 60" envelopes.

---

## 1. Envelope volume — what the valve must move

| envelope | volume | basis |
|---|---:|---|
| 18" DecoGlee Mylar | **15.00 L** | [CITED] protocol §B.1, "~14–15 L" |
| 36" latex | **400.32 L** | [COMPUTED] sphere, r = 0.4572 m — **upper bound** |
| 60" Cymylar | **1853.33 L** | [COMPUTED] sphere, r = 0.7620 m — **upper bound** |

**Spread: 15 L to 1853 L, a factor of 123.6.** That spread is why a single valve number is meaningless.

> **The sphere volumes are upper bounds.** Real foil balloons are pillow-shaped and hold materially
> less than a sphere of the same nominal diameter, so treat 400 L and 1853 L as ceilings, not
> capacities. The 18" figure is cited from the protocol because it is the one envelope actually
> measured in this repo.

---

## 2. Required average flow

`Q = V / t`, printed by the model:

| envelope | 30 s fill | 120 s fill | 10 min fill |
|---|---:|---:|---:|
| 18" DecoGlee Mylar | 30.00 L/min | **7.50 L/min** | 1.50 L/min |
| 36" latex | 800.64 L/min | 200.16 L/min | 40.03 L/min |
| 60" Cymylar | 3706.67 L/min | **926.67 L/min** | 185.33 L/min |

This is **average** flow. Two caveats that matter:
- The **pump** sets the achievable rate; the valve only has to not restrict it. Pump capability is
  **not specified anywhere in the repo** (`TODO(unverified)`), so no fill time above is proven
  achievable — they are requirements, not predictions.
- A valve must pass the **peak**, and gas flow depends on the pressure drop, which ADR-088 leaves
  unknown. The numbers above are therefore a *lower bound on the valve's required passing capacity*
  at whatever ΔP the operator eventually qualifies.

---

## 3. Is the candidate oversized?

Converting the SMC VQZ1121's quoted **Cv = 0.19**:

```
water at 1 psi drop   : 0.719 L/min (water)
air, sonic, 2 bar abs : ~380 L/min   (order-of-magnitude estimate)
18" balloon, 120 s    : 7.50 L/min
oversizing factor     : 51x
```

**The gas conversion is an ESTIMATE, not a datasheet figure** — it uses the common choked-flow
approximation `Q ≈ 1000·Cv·P₁(bar abs)` and is good to perhaps a factor of two, not 10 %. Even at
**25× instead of 51×** the conclusion is unchanged: the valve is not the constraint for a pico balloon.

**Against the 60" case it inverts.** 926.67 L/min required vs ~380 L/min estimated passing capacity
means the candidate **cannot** fill a 60" balloon in two minutes. That is not a defect in the valve —
it is the wrong valve for that envelope.

---

## 4. Fail-safe direction — the part that is not about flow

Flow decided whether the valve is *sized* right. It says nothing about whether it is *safe*. ADR-150
**S1** requires the valve to be **normally closed and to de-energise closed**, and requires that to be
**proven, not inferred**.

The SMC VQZ1121 listings found are **2-position single-solenoid** valves, which *usually* means
spring-return-to-off. **That is an inference, not a proof**, and the specific coil voltage in those
listings is **24 VDC** — not 12 V. Both must be closed against the vendor's ordering guide before any
order, on the exact suffix.

**A valve that fails open is a safety defect, not a part substitution.** For a direct-acting valve this
is also easier to prove: with no pilot pressure involved, de-energising removes the only opening force,
and the spring (or the medium's own pressure against a seat) closes it. That is a second, independent
reason to prefer a small direct-acting valve over a pilot-operated spool valve for this job.

---

## 5. Recommendation and the condition that flips it

**Recommend: a small direct-acting 12 V DC normally-closed valve, low single-digit L/min.**

The condition that flips it: **if the programme commits to 60" Cymylar envelopes**, the flow
requirement jumps to ~185 L/min even on a generous 10-minute fill, a small direct-acting valve cannot
pass it, and the VQZ1121-class spool valve becomes correct — at which point the proof obligation moves
to its fail-safe direction rather than its flow.

**Not recommended at any envelope size:** selecting a valve before the envelope class is fixed. That is
the one option this study rejects on numbers, because the required flow spans 123× across the envelopes
the repo actually names.

---

## 6. Open items

| item | status |
|---|---|
| ΔP targets, ramp, dwell, max | **UNKNOWN** — ADR-088 §3 withdraws every numeric pressure instruction |
| Pump capability | **TODO(unverified)** — absent from the repo; no fill time is proven achievable |
| 36"/60" true capacities | **TODO(unverified)** — sphere upper bounds only; needs a measured envelope |
| Helium vs air flow | **TODO(unverified)** — the model's gas figures are air; He leaks faster through clearances |
| Valve fail-safe direction | **PROVEN NOWHERE** — needs the vendor ordering guide *and* the operator's hands (ADR-150 S6) |
| Candidate valve coil voltage | listings are **24 VDC**; a 12 V variant exists in the series but the suffix is unconfirmed |
