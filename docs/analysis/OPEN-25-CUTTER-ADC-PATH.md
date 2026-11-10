# OPEN-25 cutter ADC input: bounded component proposal

Status: proposed input circuit, not electrical closure. No copper or actuation.
Scope: ADR148 ADS1115, one ground-referenced 10 mOhm shunt per cutter.
Repeat the input cell for the allocated cutter channels; do not allocate a spare ADC input.

## Selected candidate

Use **TMUX1511PWR**, not directly on the raw shunt:

```
Kelvin shunt high -- R1 1.00k -- node S -- TMUX1511 S1(2)/D1(3) -- ADC AIN
                                |                              |
                            R2 1.00k                       R3 10.0k
                                |                              |
Kelvin shunt low = ADC GND ------+------------------------------+
```

TSSOP pin 14 VDD = same switched 3.3 V rail as ADS1115, pin 7 GND;
100 nF decoupling. SEL1 pin 1 active high, external 10k pulldown in
addition to internal **typical** 6 Mohm. Other channel pin assignments per
source [1] section 4; unused selects grounded. Never use the 12-pin package
pinout for this TSSOP. R1/R2/R3: precision thin-film 0603, 0.1% initial,
<=25 ppm/K, >=0.1 W, >=25 V working rating procurement requirements.
Exact resistor order codes remain a BOM verification item; no invented MPN.
Use a conservative +/-0.5% total resistance envelope (initial + temperature
+ aging allocation), not 0.1% over the entire flight environment.

Enable only with the ADC rail verified >=3.0 V and stable. Disable before
rail removal. **Hardware enforcement of that rule is still required**;
MCU firmware alone does not prove a safe collapsing-rail sequence.

## Primary limits, not absolute-maximum operating targets

[1] TI TMUX1511 Rev B: https://www.ti.com/lit/ds/symlink/tmux1511.pdf
sections 5.3, 5.5, 5.7 and pin table. Supply operating 1.5..5.5 V;
powered signal 0..min(2*VDD,5.5 V); below 1.5 V signal range 0..3.6 V.
Powered-off leakage maximum +/-2 uA over -40..125 C at VDD=0,
VS<=3.6 V, VD=0. Do NOT substitute the 10 nA room-temperature,
VS<=3 V number. ON leakage +/-50 nA under the specified table test
conditions; OFF leakage +/-100 nA. RON maximum 4.5 ohm, not the
2 ohm typical. SEL low <=0.45 V, high >=1.2 V, legal 0..5.5 V;
logic leakage +/-2 uA gives only 20 mV across external 10k pulldown.
Power-removal turnoff maximum 4 us is specified for a 1 us supply fall,
200 ohm/15 pF test load: not an arbitrary rail-ramp guarantee.

[2] TI ADS1115: https://www.ti.com/lit/ds/symlink/ads1115.pdf
sections Recommended Operating Conditions, Electrical Characteristics,
and Analog Inputs. Operating supply 2..5.5 V, input GND..VDD.
Absolute input GND-0.3..VDD+0.3 V and +/-10 mA pin current are stress
limits, not a back-power budget. At +/-0.256 V PGA, LSB=7.8125 uV;
differential impedance 710 kohm and common-mode impedance 100 Mohm
are **typical**, not guaranteed minimum input impedances.

## Arithmetic and accuracy

Run `python3 docs/analysis/check_cutter_adc_path.py`.
With switch open, the worst divider output at 5.4 V is 2.7135 V,
comfortably below the switch's 3.6 V powered-off ceiling. Powered/on,
R3 loads the divider: nominal gain with RON=0 is 10/21=0.4761905;
25 mV becomes 11.9048 mV, about 1524 codes. Use this gain, not 0.5.
The script enumerates resistor and RON corners. RON is in series with
the ADC-side bleed load and therefore affects DC gain even without ADC
input current. Across these corners gain stays 0.473..0.479; resistor
error is about 0.53%, RON contribution about 0.043%.

50 nA switch leakage times <=503 ohm gives <=25.2 uV ADC error,
about 0.212% of a 25 mV shunt signal; this is a table-condition estimate,
not proof that leakage at near-ground 12 mV is guaranteed by those tests.
The typical 710 kohm ADC load contributes about 0.067% additional gain
loss. ADC offset/gain/noise and shunt tolerance/tempco remain separate;
there is no guaranteed total metrology error without bounding ADC input
loading and near-ground switch leakage. One-code input-referred step is
16.4 uV (1.64 mA at 10 mOhm). Calibrate zero and gain; calibration does
not validate fault protection.

At VDD=0, +/-2 uA into R3 gives +/-20.1 mV by the leakage model.
This is inside the ADC stress envelope, NOT a promise of zero injection
or proof of unpowered ADC operation. The switch leakage specification
uses VD=0, whereas this passive bleed permits a small nonzero VD:
validate that condition and measure ADC rail backfeed before acceptance.
No ADC-pin capacitor is selected: stored charge would add a separate
power-collapse hazard. R1 dissipation under steady 5.4 V is <9 mW.

## Fault-protected alternative: not selected

[3] TI TMUX7462F Rev B: https://www.ti.com/lit/ds/symlink/tmux7462f.pdf
sections 6.4/6.5 and device description. Source fault/powered-off protection
is +/-60 V, normal source/drain range VFN..VFP. It requires supply span
8..44 V and VDD>=5 V; single supply therefore >=8 V, NOT this 3.3 V rail
or the bounded 5.4 V source. VFP minimum 3 V. This is an always-on
protector, not a selectable switch with default-low EN; DR chooses drain
fault behavior, not channel enable. Adding an 8+ V rail merely for this
cell is rejected here. Its 8.3 ohm typical RON is not an accuracy bound
at 3.3 V (an illegal supply). It cannot be credited with leakage or
resistance performance on that rail. A fault protector also needs proof
that its threshold/delay never exposes ADS1115 beyond its rail: a
'60 V protected' source does not mean the drain is ADC-safe during ramps.

## Failure boundary and remaining gates

- Proven arithmetic assumes raw node 0..5.4 V and intact common ground,
  resistors, and switch. Negative transients, inductive overshoot, ESD,
  higher supply, or loss of Kelvin ground are outside this claim.
- Shunt open with ADC powered: input <=2.714 V at rail >=3.0 V; conversion
  saturates at +/-0.256 V PGA but input remains inside its operating rail.
- ADC off, switch supply off: divider remains bounded; bleed handles the
  specified leakage model, subject to off-state validation above.
- Rail falling through 2.7 V while switch remains ON can violate ADC
  operating range; at lower rails it can violate stress limits. Default
  SEL pulldown does not defeat a stuck-high GPIO. This is the exact
  unresolved protection bottleneck: select and verify hardware power-good
  gating plus fall-time/turnoff coordination, or a separately qualified
  low-voltage fault protector. Do not label this circuit ramp-safe yet.
- R2 open or R1 short exposes TMUX1511 to raw 5.4 V when off: NOT protected.
  R3 open invalidates the off leakage voltage bound; switch stuck closed
  invalidates isolation. This is not single-component-fault tolerant.
- Before schematic acceptance: exact resistor datasheets/derating, actual
  rail tolerances, hardware enable circuit, switching transients, leakage
  over temperature, ADC loading/calibration and dummy-source ramp tests.
  No heater firing is authorized. The viable steady-state candidate and
  explicit sequencing blocker advance the input cell, not the driver.
