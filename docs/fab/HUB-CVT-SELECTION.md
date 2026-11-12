# `U_HUB_CVT` — PV input converter: what it must do, and candidates

**2026-11-08. Research only — NO PART CHOSEN.** `U_HUB_CVT` is `part TODO(unverified)` on the
board: footprint fixed at **VQFN-16 3x3 mm P0.5**, device undecided.

This document exists because the previous research effort
(`docs/fab/CUT-DRIVER-SELECTION.md`) covered the **cut drivers** thoroughly and left this one
undone. It is the other half of the assembly blocker.

---

## 1. What the part must do — measured, not assumed

Read from the board's nets and from ADR-129 D3 / ADR-070 / ADR-044:

| requirement | evidence |
|---|---|
| **Input: the hub PV array** | nets `/HUB_PV_P` (net 21), `/HUB_PV_N` (net 20) |
| **Interior node between bypass diodes** | `/HUB_PV_MID1` (net 19) — ADR-129 D3: becomes a real net between connector and `D_HUB1`/`D_HUB2` |
| **Output: the raw supercap rail** | `VSCAP`, described in ADR-129 as *"raw supercap, post-BAT54, pre-LDO"*, **≈5.4 V** |
| **Package** | VQFN-16 3×3 mm, pitch 0.5 mm — **fixed by the footprint already on the board** |
| **Quiescent draw matters a lot** | ADR-044 §3: *"1 µA at 5.4 V = 5.4 µW = 5.4 %"* of ADR-036's **100 µW night anchor**. The converter sits on the **raw VSCAP node**, so its I<sub>Q</sub> drains the bank continuously |
| **Efficiency at low light matters** | The night budget is at the 100 µW scale — this is not a "1 A buck" application |

## 2. The hard constraint that shapes everything: package

The footprint is **already routed**: VQFN-16 3×3 mm, 0.5 mm pitch, EP 1.1 mm. Changing the
device means either finding one in exactly that package, or **changing the footprint and
re-routing** — which is the expensive path this project has repeatedly avoided.

So candidate selection is genuinely constrained to **VQFN-16 3×3 (or a compatible 3×3 QFN-16
with the same pinout class)**, not "any energy-harvesting PMIC".

## 3. The design question underneath it

ADR-044 §3 records the open question this part *embodies*: option (b) is a **switcher**, and
its stated costs are:

- **I<sub>Q</sub> is part-dependent and not yet selected** — and it drains the bank 24/7
- new failure point: *"a switcher can fail open (no charging) or short (array shorted into the
  bank); there is no such failure mode on a wire"*
- unmeasured EMI: verification is ADR-029 §5 tests 1/3/4 (< 3 dB 2.4 GHz rise, < 1 dB GNSS
  C/N0 drop, < 20 mV rail dip)

**That is a design decision, not a sourcing decision**, and it is the reason this part is still
`TODO`.

## 4. Candidate classes to evaluate — NOT yet price-checked

I am listing the classes rather than picking, because the choice depends on the ADR-044
option question, and picking before that would be deciding by shopping list.

| class | examples | why it might fit | why it might not |
|---|---|---|---|
| **Energy-harvesting boost PMIC** | TI BQ25504 / BQ25570, ST SPV1050 | designed exactly for µW-scale harvesting with a storage element; BQ25570 adds a regulated output | **BQ25504 is QFN-16 3.5×3.5, not 3×3** — footprint mismatch; I<sub>Q</sub> ~488 nA typ |
| **Low-I<sub>Q</sub> boost converter** | TPS61099, TPS61299-class | much lower I<sub>Q</sub> than a harvesting PMIC's MPPT front end | no MPPT; may not start at very low Vin |
| **Ideal-diode / ORing + boost** | LTC3105-class | very low start-up voltage | availability and package |
| **Do nothing (option (a) in ADR-044)** | wire the array straight to the bank | zero I<sub>Q</sub>, zero new failure mode, zero EMI | loses MPPT; array operating point uncontrolled |

**The last row is a real option and should not be skipped.** ADR-044's own text contrasts a
switcher against *"a wire"*, and the wire has no I<sub>Q</sub> and no new failure mode. If the
harvesting gain cannot be shown to beat the converter's own draw at the 100 µW anchor, the
wire is the better engineering answer — which would make `U_HUB_CVT` a **DNP site**, not a
part to buy.

## 5. What I have NOT done

- **Not price-checked or stock-checked any candidate.** The v9 method (live JLCPCB API, with a
  known-good control part to prove the query is real) is the right way and I have not run it.
- **Not verified any candidate's package against VQFN-16 3×3.**
- **Not selected a part.** AGENTS.md standing authority covers technical decisions, but this one
  is bounded by ADR-044's unresolved option question, and choosing a device would silently decide
  that question.

## 6. What would settle it, in order

1. **Decide ADR-044 option (a) wire vs (b) switcher.** Everything else follows from this.
2. If (b): shortlist by package **first** (VQFN-16 3×3), then by I<sub>Q</sub> at 5.4 V, then
   price/stock — in that order, because I<sub>Q</sub> is 5.4 % of the night budget per µA.
3. Verify each candidate against ADR-029 §5 tests 1/3/4 before it is trusted.

## 7. Reproduce

```
grep -n "U_HUB_CVT" docs/adr/129-v10-power-restoration-and-bypass-diodes.md
grep -n -A4 "VSCAP" docs/analysis/array-power-architecture.md
sed -n '360,380p' docs/analysis/array-power-architecture.md    # ADR-044 option (b) costs
```
