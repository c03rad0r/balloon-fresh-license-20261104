# v11 `/SCAP_ADC` + solar-input dividers — values, protection, and what is not proven

**Status:** SCHEMATIC, design-intent. **NOT FAB READY.** No v11 PCB exists; v11 is unrouted and
`D_BP1..D_BP4` top-face placement (ADR-146) is unresolved. No copper, no purchase, no actuation.

Implemented in `tracker/hardware/connectivity/v11_pinmap.reg`, generated into
`tracker/hardware/schematics/flight_board/v11_flight.kicad_sch` by
`build_v11_sch.py`, and asserted by `tracker/hardware/test_v11_scap_adc.py`.
Machine-readable channel map: `tracker/hardware/v11_analog_channels.json`.

This closes v11 scope **item 2** only. Items 1, 3 and 4 remain open and are listed at the end.

---

## 1. What was actually wrong on v10, measured

| finding | measurement |
|---|---|
| `/SCAP_ADC` had no MCU end | net contained exactly 2 pads: `R_DIV1.2`, `R_DIV2.1` |
| no solar divider existed | `/W1_SOLAR_P` touched only `D1`, `D_BP1`, `J_W1` |
| **the I2C bus had no pull-ups at all** | pads on `/I2C_SCL`,`/I2C_SDA` were only `U1.38/39` and `U6.7/8` |

The third one is new and was not in ADR-148. ADR-145 justified the MCP23017 on the grounds that
the bus "already exists and is already routed" — routed, yes, but with **no pull-up resistors**,
two more devices cannot drive it. Two 4k7 pull-ups are added; their idle current is zero because
both lines sit high.

---

## 2. Channel assignment

Two `ADS1115IDGS` (`C37593`, VSSOP-10) on the existing bus. Both at **FSR ±4.096 V (PGA code 1),
LSB 125 µV** (SBAS444E Table 7-1).

| device | ADDR strap | address | channel | net | function |
|---|---|---|---|---|---|
| `U_ADC1` | → GND | `0x48` | AIN0–AIN3 | GND | **reserved** cut-sense W1–W4 (item 3), DNP |
| `U_ADC2` | → VDD | `0x49` | AIN0 | `/SCAP_ADC` | `/VSCAP` |
| | | | AIN1 | `/W1_SOLAR_SENSE` | `/W1_SOLAR_P` — 12-cell stack top |
| | | | AIN2 | `/W2_SOLAR_SENSE` | `/W1_SOLAR_N` — 9-cell tap |
| | | | AIN3 | `/W3_SOLAR_SENSE` | `/W2_SOLAR_N` — 6-cell tap |

**Why ±4.096 V and not ±2.048 V or ±6.144 V.** ±2.048 V leaves ~29 LSB between the documented
cold-Voc fault (2.10 V at the pin) and full scale. ±6.144 V cannot deliver full scale at
VDD = 3.3 V (SBAS444E §7.3.3 footnote 1 and its worked example). At ±4.096 V and VDD 3.3 V the
part measures 0–3.3 V single-ended, which is the datasheet's own example.

**Address collision check** (SBAS444E Table 7-2: ADDR → GND/VDD/SDA/SCL = `0x48`–`0x4B`):

| device | address |
|---|---|
| `U_ADC1` | `0x48` |
| `U_ADC2` | `0x49` |
| `U6` MS5611-01BA | `0x76` / `0x77` (SDO strap) |
| MCP23017 (ADR-145, **not fitted**) | `0x20`–`0x27` |

No collision; two ADS1115 addresses remain spare.

**The four wings are in series**, so only three independent nodes exist. Wing voltages 1–3 are
differences of adjacent measured nodes. **Wing 4's own terminal voltage is not directly
measurable** — its positive node is `/W3_SOLAR_N`, and subtracting GND gives the whole string.
ADR-148 spent all eight channels (4 cut + VSCAP + 3 solar). A fifth monitor channel needs a third
ADC, which is a v12 decision, not a v11 omission.

---

## 3. The voltage envelope — and what it rests on

| quantity | value | source |
|---|---|---|
| Array cold Voc, 12 cells @ −60 °C | **9.58 V** | `wing-electrical` §5.1 |
| `/VSCAP` post-BAT54 at that condition | **9.28 V** | 9.58 V − 0.3 V |
| `/VSCAP` rated bank top | **5.4 V** | 2 × 2.7 V (ADR-006) |

⚠️ **The 9.58 V is an ESTIMATE, not a measurement.** It comes from `V_OC,cell(25 °C) = 0.62 V` and
`−2.1 mV/(°C·cell)`, **both marked `TODO(unverified)`** in `wing-electrical` §5.1. The cell's
datasheet is not in this repository. `array-power-architecture` §9 item 5 and
`mppt-charge-path-specification` §2 carry the same caveat.

There is **no clamp in the accepted design** (ADR-047 §7.3, `wing-electrical` §5.2), so 9.28 V is
a *reachable node voltage*, not a hypothetical. The ADC is therefore sized to survive the estimate
being wrong — see §4.

**Nothing here invents a solar open-circuit voltage.** The number used is the repo's own
documented estimate, cited, and its `TODO(unverified)` status is carried forward onto the sheet as
a `TODO(unverified)` note rather than silently promoted to fact.

---

## 4. Divider values and input protection

One ratio for all four channels: **0.2198582**.

| divider | source | R top | R bottom | R prot | C | ratio | pin at worst case |
|---|---|---|---|---|---|---|---|
| `D_VSCAP` | `/VSCAP` | 2.2 M (`R_DIV1`) | 620 k (`R_DIV2`) | 10 k (`R_PROT1`) | 10 nF (`C_DIV1`) | 0.2198582 | 9.28 V → **2.040 V** |
| `D_W1` | `/W1_SOLAR_P` | 220 k (`R_SOL1`) | 62 k (`R_SOL2`) | 10 k (`R_PROT2`) | 10 nF (`C_SOL1`) | 0.2198582 | 9.58 V → **2.106 V** |
| `D_W2` | `/W1_SOLAR_N` | 220 k (`R_SOL3`) | 62 k (`R_SOL4`) | 10 k (`R_PROT3`) | 10 nF (`C_SOL2`) | 0.2198582 | 9.58 V → **2.106 V** |
| `D_W3` | `/W2_SOLAR_N` | 220 k (`R_SOL5`) | 62 k (`R_SOL6`) | 10 k (`R_PROT4`) | 10 nF (`C_SOL3`) | 0.2198582 | 9.58 V → **2.106 V** |

**Why the /VSCAP divider had to change.** v10's `R_DIV1`/`R_DIV2` were 1 M / 1 M, ratio 0.5. At
the documented 9.28 V fault that puts **4.64 V** on the ADC pin. SBAS444E §5.1 absolute maximum is
`VDD + 0.3` = **3.6 V**. The inherited divider would have destroyed the ADC in exactly the fault
the board exists to observe. This is not a refinement; it is the difference between a working
instrument and a dead one.

**Night budget is not made worse.** Total 2.82 M gives 1.915 µA / **10.34 µW** at 5.4 V, against
the 2.70 µA / 14.58 µW that ADR-047 §6 recorded for the 1 M / 1 M pair.

**Solar dividers draw nothing at night** — the string sits at 0 V. Daytime cost is 34 µA each
against an array that delivers 0.4–1.2 A.

### The protection is proven by CURRENT and DISSIPATION, not by ratio

SBAS444E §5.1: **±10 mA continuous on any non-supply pin**. §9.1.3 recommends "current-limiting
resistors on the input lines" and states the inputs "can withstand continuous currents as large as
10mA".

Two independent ceilings apply, and a protection claim is only as good as the tighter one:

| dividers | dissipation ceiling | pin-current ceiling | binding | margin |
|---|---|---|---|---|
| `D_W1..D_W3` (220 k / 62 k, 0402) | **150.3 V** (`R_SOLx` top at 62.5 mW) | 471.2 V | **150.3 V** | **15.7×** |
| `D_VSCAP` (2.2 M / 620 k, 0402) | 475.3 V | 471.2 V | **471.2 V** | 49.2× |

The solar family is **dissipation-limited, not current-limited**: at the 471 V it would take to
reach 10 mA, the 220 k 0402 `R_SOLx` is dissipating 614 mW and has failed long before the ADC pin
is stressed. So the honest number for the solar channels is **150.3 V = 15.7× the documented
9.58 V cold Voc**, and the residue past that is a resistor-body limit, not an ADC limit.

Below **16.38 V** source the tap is under the 3.6 V absolute maximum and the ESD diode is not
conducting at all — 1.71× the cold Voc, so the clamp is idle across the entire design envelope.

**Ratio alone could not do this.** Holding 3.6 V at 1.5× cold Voc needs ratio ≤ 0.2505; at 2.0× it
needs ≤ 0.1879; and either would throw away resolution at the low end where the interesting
behaviour is. So the design covers 1.5× by ratio and everything beyond that by the resistor. Both
bounds are asserted, and `G8d` fails if the resistor ever becomes unnecessary — i.e. the test
tells you if the protection stops being load-bearing.

`R_PROT` also forms the first-order RC with `C_DIV`/`C_SOL`: τ = 100 µs, corner 1.59 kHz — inside
SBAS444E §9.1.5's "output data rate or 10× higher" guidance for the 128 SPS–860 SPS range — and
the cap doubles as the sample-and-hold reservoir the switched-capacitor input needs.

**Source impedance is dominated by the divider, not `R_PROT`, and it is not negligible.** The ADC
draws a small average current into its switched-cap input, so the divider's Thevenin resistance
divides against the input impedance and shows up as a gain error:

| channel | R_thevenin | + `R_PROT` | Z_source | loading error vs 15 MΩ (TYP) |
|---|---|---|---|---|
| `D_W1..D_W3` | 48.4 kΩ | 10 kΩ | 58.4 kΩ | **0.388 %** |
| `D_VSCAP` | 483.7 kΩ | 10 kΩ | 493.7 kΩ | **3.186 %** |

The 2.2 M / 620 k pair was chosen for the night-power budget, and it costs **3.19 % gain error** —
8× worse than the solar channels. That is a *systematic, calculable* error, so it is correctable
in firmware calibration, but it must not be silently ignored, and any absolute `/VSCAP` accuracy
claim carries it. If a better number is wanted later, the fix is buffering the `/VSCAP` tap or
dropping the divider to 220 k/62 k (at 34 µA of standing draw) — a v12 trade, not a v11 change.

**Resolution:** input-referred LSB = 125 µV / 0.2198582 = **568.5 µV**. The 5.4 V rail reads
**9 498 counts**; the 9.28 V fault reads **16 322 counts**. Both are far above the noise floor, so
this is a real measurement, not a threshold.

---

## 5. What is proven vs. still unqualified

### Proven (asserted by `test_v11_scap_adc.py`, which runs)

- Registry ↔ schematic parity, both directions, at node granularity.
- The channel map in the JSON matches the actual netlist pins — the JSON is checked, not trusted.
- Four distinct I2C addresses, two of which match their ADDR strap per SBAS444E Table 7-2.
- Every divider keeps its pin inside the FSR **and** inside VDD at the documented worst case.
- All four dividers share one ratio **by resistor value**, to <1e-12.
- **Negative control:** the v10 1 M/1 M ratio fails the same check (4.64 V > 3.6 V). A gate that
  cannot fail is not a gate; `--self-test` additionally proves two poisoned fixtures are rejected.
- Pin current inside the 10 mA continuous limit at the documented fault, and the *binding* limit
  (resistor dissipation) identified per divider rather than quoted as one number.
- Unwired cut-sense inputs are tied to GND per SBAS444E §9.1.4, not floated.
- Native ERC: **9 violations, exactly the v10 baseline** — all inherited (U5/U2
  `power_pin_not_driven`, U_C's single-ended control nets, `IO0` with no MCU end). Zero new.
- Regeneration is byte-identical.

### Still unqualified — stated, not glossed

1. **The cold Voc is an estimate.** Both temperature coefficients are `TODO(unverified)` and the
   cell datasheet is absent. The protection is robust to this; the *reported volts* are not, until
   the cell is measured or its datasheet lands.
2. **ADC pin leakage over temperature is not specified by TI.** SBAS444E gives digital input
   leakage (10 µA max) but no separate analog-pin leakage figure. 10 µA × 10 kΩ would be 100 mV,
   which is a real uncertainty at the low end of the solar range.
3. **Input impedance is typical, not guaranteed.** 15 MΩ differential at ±4.096 V is a `TYP`
   value, and `OPEN-25-CUTTER-ADC-PATH.md` makes the same point. No guaranteed total metrology
   error exists without bounds on it — and the `/VSCAP` channel additionally carries the 3.19 %
   source-loading error quantified in §4.
4. **No clamp.** Nothing in this change adds one. ADR-047 §7.3 requires it and it is a separate
   part; until it exists, the fault path this design survives is still present on the board.
5. **Power sequencing on a collapsing rail is still blocked.** For the *rail-monitor* channels the
   divider is passive and bounded, and `R_PROT` limits current — but this document does not claim
   ramp safety, and neither should anyone else. For the *cut-sense* channels the question is
   openly BLOCKED (see §6).
6. **Below −40 °C.** Nothing here is qualified at −60 °C. SBAS444E is specified −40 to +125 °C.
   The project's cold case is −60 °C ambient.
7. **TI publishes no powered-off input characteristic, and this design does not invent one.**
   SBAS444E §10.1 "Power-Supply Sequencing" contains exactly one requirement — "Wait approximately
   50µs after VDD is stabilized before communicating with the device" — and then goes straight to
   §10.2 decoupling. There is **no statement anywhere in the datasheet** about what the AIN pins
   tolerate when VDD = 0. The absolute-maximum table is written relative to VDD (`VDD + 0.3`), which
   is *undefined* at VDD = 0, and the §9.1.3 protection-diode discussion presumes the rails exist.

   So the widely-repeated "the ESD diode conducts into the VDD rail" model is an *inference*, not a
   datasheet guarantee. In this design it is bounded by 10 kΩ of series resistance and by the
   divider, which caps the current a de-powered pin can be asked to sink — but **bounded current is
   not the same as proven safe**, and no number here should be read as a powered-off rating.

### On the TMUX1511 question

The prior work found TMUX1511 powered-off protection is **only 3.6 V**. That is correct and it is
*not* being credited with anything here: **no analog switch is used in this change.**
`OPEN-25-CUTTER-ADC-SEQUENCE.md` rejects the shared-rail TMUX1511 retrofit because the supervisor's
assertion latency has no guaranteed maximum and the rail collapse rate is unbounded. **This design
does not claim to have solved that.** What it does is bound pin *current* on a divider that is
passive, always-on and needs no sequencing decision — which is a strictly weaker claim.

**What is missing to protect an unpowered ADC from a 5.4 V fault on the cut-sense path:** a
qualified power-good gating scheme with a *guaranteed maximum* assertion delay, plus a bounded rail
collapse rate — or a separately held-up ADC/protection supply domain with sized hold-up
capacitance. Neither exists; TPS3808G33 has 20 µs *typical* and no maximum (§6.6), which is why the
sequence document blocks it rather than deferring it.

---

## 6. Remaining v11 items, in dependency order

| # | item | state |
|---|---|---|
| 1 | `D_BP1..D_BP4` to the top face (ADR-146) | **NOT DONE**, and blocking. Layout-only, zero parts, so the schematic is identical either way — but PR #530 measured both proposed `D_BP2` top sites as illegal under native DRC. Accepted; not re-litigated. Needs a legal site before fab. |
| 2 | `/SCAP_ADC` + solar dividers (ADR-148) | **THIS CHANGE.** Schematic complete; 5 open qualifications in §5. |
| 3 | Real cut-driver parts (latch + AO3400A + Rg + shunt) | **NOT DONE.** `U_CUT1..4` remain placeholders. Their four ADC channels are reserved and grounded. Blocked on the power-sequence question in §5. |
| 4 | GPIO economy / MCP23017 (ADR-145) | **NOT DONE.** No part added. Bus now has the pull-ups it needs, which is a prerequisite. |
| 5 | Full re-route | Not started. Depends on 1–4. |

**v11 is NOT fab ready:** item 1 is unresolved and the board is unrouted.

---

## 7. Reproduce

```bash
cd tracker/hardware/schematics/flight_board
python3 build_v11_sch.py                 # regenerate the sheet from the registry
kicad-cli sch erc v11_flight.kicad_sch   # native ERC -> 9, all inherited
cd - && python3 tracker/hardware/test_v11_scap_adc.py            # the gate
python3 tracker/hardware/test_v11_scap_adc.py --self-test        # prove it can fail
```

## 8. Sources

- **TI ADS1115**, SBAS444E (rev. December 2024) — §5.1 Absolute Maximum Ratings, §5.3 Recommended
  Operating Conditions, §5.5 Electrical Characteristics, §7.3.3 FSR/LSB + Table 7-1, §7.5.1.1 +
  Table 7-2 (ADDR), §9.1.3 Input Protection, §9.1.4 Unused Inputs, §9.1.5 Analog Input Filtering,
  §10.2 Power-Supply Decoupling.
- `docs/adr/148-ads1115-analog-sense-and-rail-telemetry.md`
- `docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md`
- `docs/analysis/OPEN-25-CUTTER-ADC-SEQUENCE.md` (blocked), `OPEN-25-CUTTER-ADC-PATH.md`
- `docs/analysis/wing-electrical.md` §5.1–§5.3
- `docs/adr/047-v9-power-provisioning.md` §6, §7.3
- `docs/fab/V11-DESIGN-SPEC.md` §2
