# Part recommendations for the assembly BOM — with the reasoning, and three real problems

**2026-11-08, board `0602c7c8`.** Every number below was fetched from its LCSC product page and its
schema.org spec block read. Nothing here is inferred from a part number's shape.

## First: the "13 empty numbers" no longer exist

They were filled in `bc2ef54c`. All 14 JLC lines now carry a number. **But verifying that a number
*exists* is not the same as verifying the part is *right*, and that is what this document does.** Two
of the chosen parts are fine; three parts expose circuit problems that no part number can fix; one
needs a deliberate decision.

## The BOM as it stands, with the specs that matter

### Diodes

| ref | part | key specs | verdict |
|---|---|---|---|
| `D_BP1..4`, `D_HUB1..2` | **SS24** (C50645) | SMA, **Vr 40 V**, **If 2 A**, Vf 550 mV @ 2 A, surge 50 A, −55…+125 °C | **Keep.** 40 V against a ~9.6 V cold-Voc string is 4× margin; 2 A against the array's current is generous. Vf 550 mV is the right trade for a blocking diode on a solar path |
| `D1` | **BAT54W** (C699107) | SOD-123, **Vr 30 V**, If 200 mA, Vf 1 V @ 100 mA, Ir 2 µA @ 25 V | **Keep.** It is the reverse-current block between `/VSCAP` and `/W1_SOLAR_P`; 200 mA is ample for a single wing string. Schottky, so the low Vf and the 2 µA reverse leakage both matter here |

### Capacitors — one real derating concern

| ref | part | specs | verdict |
|---|---|---|---|
| `C10`, `C4` | **CL05A106MQ5NUNC** 10 µF 0402 (C15525) | **X5R**, **6.3 V**, ±20 % | **OK at 3.3 V** |
| `C_BULK` | **CL31A107MQHNNNE** 100 µF 1206 (C15008) | **X5R**, **6.3 V**, ±20 % | ⚠ **See below** |
| `C_HF` | **CL05B104KO5NNNC** 100 nF 0402 (C1525) | **X7R**, **16 V**, ±10 % | **Good.** X7R is the correct class for decoupling, 16 V gives 3× on a 5.4 V rail |
| `C_MON` | **CL05B103KB5NNNC** 10 nF 0402 (C15195) | **X7R**, **50 V**, ±10 % | **Good.** The low-leakage class matters here: it sits on `/F33_VSENSE`, a high-impedance sense node, so a leaky dielectric would corrupt the reading. X7R at 50 V is right |

**⚠ The 10 µF and 100 µF are both X5R at 6.3 V.** Rails:

```
C10   on +3V3                              -> 3.3 V,  6.3 V is fine
C4    on /GNSS_VCC (via R_F1 from +3V3)    -> ~3.3 V,  6.3 V is fine
C_BULK on /F33_VCC                         -> up to 5.4 V (J_VCC pin 1 = VSCAP)
```

`C_BULK` at **5.4 V on a 6.3 V X5R 1206** is an 86 % voltage utilisation. X5R loses capacitance with
DC bias, and a 6.3 V-rated part run at 5.4 V typically gives back **only about half its nominal
capacitance**. The 100 µF bulk is there to hold up the F33's PA during TX bursts; delivering ~50 µF
instead is a real functional difference.

**Recommendation:** for `C_BULK`, **move to a 16 V X5R or X7R 1206 100 µF** (e.g. the 16 V part in the
same CL31 family). It costs a few cents. `C10`/`C4` at 3.3 V are fine as they are — 6.3 V is a
sensible 2× derating at that voltage.

**This is a change to a line that currently has a valid number**, so I have written it down rather
than changed the BOM without asking.

### Resistors — the values are right, the impedances are not

| ref | part | specs | verdict |
|---|---|---|---|
| `R_BAL1/2` | **0402WGF1002TCE** 10 kΩ (C25744) | ±1 %, 62.5 mW, ±100 ppm/°C | **Good.** For balancing two series supercaps the value only needs to dominate leakage; ±1 % means the pair balances to 1 % |
| `R_DIV1/2` | **0402WGF1004TCE** 1 MΩ (C26083) | ±1 %, 62.5 mW | **Value OK, impedance problem** — see below |
| `R_F1` | **0402WGF1000TCE** 100 Ω (C25076) | ±1 %, 62.5 mW | **Good.** Series dropper into `/GNSS_VCC`; at the GPS's few mA the drop is millivolts |
| `R_MON1/2` | **RTT02475JTH** 4.7 MΩ (C11906) | **±5 %**, 62.5 mW | **±5 % is the weakest link, and the impedance is worse** — see below |

**Divider check, computed rather than assumed:**

```
VSCAP divider  1M/1M    VSCAP 5.4 V -> ADC 2.70 V   (+3.3 V full scale: 0.60 V headroom) OK
F33 divider    4.7M/4.7M F33 5.4 V -> ADC 2.70 V   same headroom                       OK
```

So the **ratios are right and neither divider overranges the ADC.** The problem is source impedance:

```
Thevenin impedance, 1M/1M    = 0.5 MΩ
Thevenin impedance, 4.7M/4.7M = 2.35 MΩ
ESP32-S3 ADC wants            ≲ 10 kΩ for accurate sampling
```

**Both dividers are 50–235× above what the ADC wants.** The sample-and-hold capacitor cannot charge
through 2.35 MΩ in a normal acquisition window, so readings will lag and read low. **No part number
fixes this** — it needs a smaller divider (costing quiescent current), an op-amp buffer, or firmware
with a long acquisition time.

**Recommendation on parts:** keep the values, and **put `R_MON1/2` at ±1 % rather than ±5 %** — the
F33 sense is a measurement, and a 5 % resistor makes it a 5 % measurement for a saving of about a
cent. The impedance issue goes to whoever writes the ADC firmware.

### Modules and connectors

| ref | part | specs | verdict |
|---|---|---|---|
| `U1` | **ESP32-S3-WROOM-1U-N8R8** (C2980300) | Supply 3.0–3.6 V, Tx 355 mA, **operating temp −40…+65 °C** | ⚠ **See below** |
| `U7` | **TPS7A0233DBVR** (C5142805) | 3.3 V, **200 mA**, Iq 25 nA, Vin 6 V max, −40…+125 °C | **Good,** with one caveat |
| `J_HUB_PV` | **PZ254V-11-05P** 1×5 (C492404) | 2.54 mm TH, 3 A, 250 V | **Good** |
| `J_PROG` | **PZ254V-11-06P** 1×6 (C492405) | 2.54 mm TH, 3 A, 250 V | **Good** |

**⚠ `U1` operating temperature −40…+65 °C.** A pico balloon at altitude sees ambient
**−40…−50 °C** — which is *inside* that range at the bottom but with **zero margin**, and any
self-heating is working against it. This is exactly the accepted risk the project says it will
*measure* via the NTC chain (decision D5). Worth knowing that the module's own rated floor is the
same number the risk register is worried about, so the measurement matters.

**`U7` caveat: 200 mA output.** ADR-047 records this as the standing trap — the F33's PA must never
be fed through the LDO, and `+3V3` also feeds the ESP32-S3, which draws **355 mA while transmitting**.
`355 mA > 200 mA`. Check whether the ESP32 ever transmits from this board: if it does, the LDO is
undersized for that path. This is ADR-047's own concern and it is not new, but the datasheet numbers
now make it concrete.

## What I recommend changing, in priority order

1. **`C_BULK` → a 16 V X5R/X7R 100 µF 1206.** It is run at 86 % of its voltage rating on a rail that
   genuinely reaches 5.4 V, and X5R DC-bias derating will halve it. Cheapest, highest-value change.
2. **`R_MON1/2` → ±1 %.** A sense divider should not carry a 5 % tolerance.
3. **Investigate `U7`'s 200 mA against the ESP32's 355 mA TX current.** Not a part swap — a
   question of whether that current path is real.
4. **Leave everything else alone.** SS24, BAT54W, the X7R ceramics, R_BAL, R_F1, U1's memory variant
   and both headers are correctly specified.

## The honest caveat on all of this

I verified **catalogue specs**, not **the design intent behind each value**. Where the two disagree —
the dividers' impedance, the LDO's current headroom, `U1`'s temperature floor — the disagreement is
a *design* question and changing a part number would hide it rather than fix it. Items 1 and 2 above
are safe part swaps; 3 and the divider impedance need a design decision, not a BOM edit.
