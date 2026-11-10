# v11 CUT CHANNEL — the resistor values are already in the repo

**Status:** design note. Closes the specific gap I claimed last turn: I asked the operator for nichrome
gauge, length and cut current on the grounds that *"the gate resistor and sense resistor values are not
specified anywhere"*. **That was wrong.** `docs/analysis/wing-jettison.md` §3.1–§3.3 specifies the wire
and the current completely, and `docs/analysis/wing_release_electrical.py` already carries the
energy figure as a named constant (`NICHROME_CUT_J = 2.59`).

This note takes the specified values, checks them against the part that is actually fitted, and states
what the resistors must be.

---

## 1. What the repo already fixes — verified by re-running the arithmetic

`docs/analysis/wing-jettison.md` §3.1:

| quantity | value | source |
|---|---|---|
| wire | nichrome NiCr 80/20, **0.127 mm (36 AWG)** | doc; alloy marked `TODO(unverified)` |
| length per cut | **25 mm** | doc, marked assumption |
| resistivity ρ_E | **1.10e-6 Ω·m** | typical NiCr, `TODO(unverified)` |

Recomputed here, independent of the doc:

```
A  = pi/4 x (0.127e-3)^2        = 1.2668e-8 m2
R  = 1.10e-6 x 0.025 / 1.2668e-8 = 2.17 ohm        (doc says 2.17)
m  = 8400 x 1.2668e-8 x 0.025    = 2.66 mg          (doc says 2.66)
```

§3.3, at the rail that actually exists (`VSCAP`, post-BAT54, pre-LDO, ~5.4 V):

```
I = 5.4 / 2.17 = 2.49 A
P = 5.4 x 2.49 = 13.4 W
t = 2.59 J / 13.4 W = 193 ms
```

**All four figures reproduce exactly.** So the design targets are: **2.49 A, 13.4 W, 193 ms, per wing.**

---

## 2. The part already fitted is the right class — measured

`U_CUT1..4` are placeholders, but the FET named throughout ADR-051/ADR-129 is the `IRLML2502` class, and
the `AO3400A` (`C20917`, JLCPCB **Basic**, $0.0891) is the part this project has already qualified.

| spec | AO3400A (AOS Rev3) | required | verdict |
|---|---|---|---|
| VDS | 30 V | 5.4 V | 5.5x margin |
| ID cont. @25 °C | 5.7 A | 2.49 A | 2.3x |
| ID cont. @70 °C | 4.7 A | 2.49 A | 1.9x |
| RDS(on) @ VGS 4.5 V | < 32 mΩ | — | **0.20 W at 2.49 A** |
| VGS(th) max | 1.45 V | 3.3 V gate | fine |
| package | SOT-23 | — | — |

**One channel at a time is comfortably inside the part.** But ADR-129 D5 already records the trap:
*"4 simultaneous fires = 9.9 A = 2.4x the IRLML2502 class rating"*. Recomputed against the AO3400A:
**10.0 A = 212 % of the 70 °C rating.** So serialisation is not a nicety — **firmware must fire one
channel at a time, and the hardware should help it.**

---

## 3. The resistor values

### Gate resistor — 100 Ω, and it is chosen by the *latch*, not by the FET

The gate is driven by a `SN74LVC1G373` latch output (`C128413`) whose source impedance is a few ohms
through a small CMOS output stage. The gate resistor is therefore **not** a current limiter for the
latch; it is there to damp the gate loop and set switching speed.

```
Rg = 100 ohm
Qg(AO3400A) = 7 nC max at VGS 4.5 V
```
A 3.3 V CMOS output through 100 Ω into 630 pF (Ciss) gives a **~13 ns** time constant. The pulse is
**193 ms**. Switching loss is irrelevant; the resistor's only job is damping.

**100 Ω is the value.** Not a calculated optimum — a standard value that is safely above the ringing
regime for a 630 pF gate at these edge rates, and low enough that the gate reaches threshold in
nanoseconds, not milliseconds.

### Gate pull-down — 100 kΩ to GND, and this one is the safety

ADR-051 §2.5.1 and ADR-129 D5 both mandate a **latched one-shot**, and give the reason:

> Cutting is irreversible and a level-sensitive driver can re-fire on reset, brown-out, retry or a
> floating gate — each fire costing ~2.59 J of the bank's 16.63 J, at the exact moment the bank matters.

At reset the S3's GPIOs float, and the latch's output state is undefined until it is driven. **100 kΩ
from gate to GND** holds the FET off through that window. With the 100 Ω series resistor this also forms
a divider, but the pull-down's ratio is ~1000:1, so it does not attenuate the drive at all.

**Two fires = 5.2 J = 31 % of the 16.63 J bank.** The pull-down is what prevents that.

### Sense divider — the cut-sense path, and why it is a divider at all

`U_CUT<n>` pin 3 is `/CUT_SENSE_W<n>` = `J_W<n>` pad 3 (`RF_FEED`), and it carries **both** the drive
and the continuity sense on one conductor (ADR-129 D5). The sense input therefore sits on a node that
is driven to **5.4 V** during a fire, and the ADC it feeds must not see that.

The S3's ADC range is 0–3.3 V (attenuation 0 dB gives ~1.1 V, 11 dB gives ~3.3 V). A 5.4 V node needs
**at least a 2:1 divider** to stay under 3.3 V, plus series protection because the same pad is the
drive return.

**Proposed: 100 kΩ / 100 kΩ with 100 nF to GND, plus a series 1 kΩ into the ADC pin.**

- 5.4 V through 2:1 → **2.70 V** at the ADC, inside 3.3 V with margin
- 100 kΩ source impedance is low enough for the S3 ADC and high enough not to load the drive node
  appreciably during a 193 ms pulse (200 kΩ across 5.4 V = 27 µA = 0.15 W, negligible against 13.4 W)
- 1 kΩ series + the ADC's protection diodes handles the edge case where the divider is lifted
- 100 nF forms a ~10 µs filter — fast enough to see a cut completing, slow enough to ignore the
  switching transient

**`OPEN-25` (the cut-sense GPIO/divider choice) has been open since ADR-068.** This closes the *values*;
the *pin* assignment is still ADR-108's problem, because the F33 pin plan consumed the budget and
ADR-108 §251 records that four dedicated GPIOs are no longer available. **Do not pretend the pin is
solved**: four sense channels need four inputs, and the honest options are the ADR-145 expander or a
shared multiplexed sense node with wing selection. That is a v11 schematic decision, not a resistor.

---

## 4. What this means for the v11 build

**The cut channel is no longer blocked on a measurement.** Every number it needs now exists:

| item | value | status |
|---|---|---|
| nichrome | 0.127 mm (36 AWG), 25 mm/cut | in repo |
| resistance | 2.17 Ω | in repo, reproduced |
| cut current | 2.49 A at 5.4 V | in repo, reproduced |
| pulse | 193 ms, 2.59 J | in repo, reproduced |
| FET | AO3400A `C20917` | qualified on this project |
| latch | SN74LVC1G373 `C128413` | selected |
| Rg | **100 Ω** | this note |
| pull-down | **100 kΩ** | this note; the mandated fail-safe |
| sense divider | **100k/100k, 1 kΩ series, 100 nF** | this note; values only |
| sense **pin** | **still open** (`OPEN-25`, ADR-108) | v11 schematic decision |

**So the operator's alternative is not needed.** I offered to ship v11 with the cut channel DNP so that
missing wire specs would not block the board. That offer rested on my own false claim. The channel can
be built.

**What genuinely remains undecided is the sense pin**, and that is a consequence of ADR-108 having spent
the GPIO budget — solvable with the ADR-145 expander already on the v11 roadmap.

---

## 5. But read this before building the channel at all

`docs/analysis/wing-jettison.md` opens with a recommendation that has not been withdrawn:

> **Recommendation: do not build it.** A nylon-string wing attachment with a nichrome release has **no
> mission in this flight** and it is **mass-negative** on a vehicle where mass is the binding constraint.

Its three findings, each with a number:

1. **No trigger gains anything.** Solar power *is* the science. The only defensible trigger is descent,
   and there the jettison buys **11 % of a descent rate already ~0.45 m/s** and removes **5.4 % of the
   descent drag area**.
2. **The hardware costs more than it sheds.** ~0.5 g per channel × 4 = **2.0 g carried all flight** to
   shed **3.2 g** on descent, plus **22 % of ADR-036's 100 µW night budget** in leakage alone.
3. **The string makes the structure worse.** A load-driven cord is **0.02–0.10 mm** — unbuildable — and
   any knot-able cord is ~100× stronger than the load and cannot hold the wing rigid in its vertical
   plane, which is the arm's actual job.

**The operator overrode this on 2026-10-22** — ADR-129 D5: *"Yes please include the nichrome cutoff."*
That is recorded and the channel is in the design. **This note does not reopen it.** But two things are
worth stating plainly, because they cost nothing to say now and would cost a board to discover later:

- **The 2.59 J figure scales with thermophysical constants that the study itself marks
  `TODO(unverified)`** — `cp`, `H_f`, the wire setpoint and the ×4 loss factor are order-of-magnitude.
  The *resistor values above are safe* because they do not depend on that energy: 100 Ω and 100 kΩ are
  chosen for gate damping and fail-safe, not tuned to 2.59 J.
- **A first fire should be measured, not assumed.** 193 ms into 25 mm of 0.127 mm nichrome is a
  prediction. Bench it on a discarded wing with a current probe before a flight depends on it.

---

## Reproduce

```bash
/usr/bin/python3 - <<'PY'
import math
rho, L, d = 1.10e-6, 0.025, 0.127e-3
A = math.pi/4*d*d
R = rho*L/A
for v in (5.4, 3.3):
    I, P = v/R, v*v/R
    print(f"{v} V: R={R:.2f} ohm  I={I:.2f} A  P={P:.1f} W  t={2.59/P*1000:.0f} ms")
PY
```

Prints `5.4 V: R=2.17 ohm I=2.49 A P=13.4 W t=193 ms`, matching `wing-jettison.md` §3.1-§3.3 exactly.
