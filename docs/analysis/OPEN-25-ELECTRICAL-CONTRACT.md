# OPEN-25 electrical prerequisite correction / full report

Status: REVIEW REQUIRED, NOT a layout or fabrication release. 2026-11-10.
Base: 2449ad8acfd9d5a55dc6c8155075b06bb100db32 (live origin/master).

## Inspection and authority

Live PR inspection found no open cut-sense worker PR. PR #524 is already MERGED
(head c0f300ed9997db7c4332d4c0b58b68a49ed2ba51): ADR-148 selects TWO ADS1115,
not MCP23017 sense inputs. This correction preserves that architecture rather
than opening a competing digital-sense design. Read-only inspection also found
untracked OPEN-25-RESOLVED-digital-cut-sense.md and V11-BUILD-PLAN.md in
/home/c08r4d0r/worktrees/flight-ready. Neither is a landed decision; both contain
stale/conflicting claims. Do not copy their sense circuit into a schematic.

Sources inspected: ADR-051 section 2.6, ADR-129 D5, ADR-148,
V11-CUT-CHANNEL-RESISTORS.md and those two untracked files.

## DECISIONS / corrected circuit contract

1. OPEN-25 pin allocation is decided by ADR-148; electrical closure is NOT proven.
   Preserve top-side bypass diodes, storage AND solar telemetry, four real
   cutter channels, and ADR-145 U_C GPIO economy. Do not remove scope to pass a gate.
2. Reject raw RF_FEED -> 10k -> MCP23017 with 100nF to ground. A capacitor is
   open at DC and a series resistor is not a divider. Binary semantics do not
   alter voltage limits. With no defined pull or verified wing return this
   circuit also has no defined open-state reading. Do not rely on IC clamp
   injection, including while its supply is off. No MCP23017 pin connects to
   raw VSCAP or a 25mV shunt in this contract.
3. Keep ADS1115 shunt sensing, but require a complete current-loop schematic
   BEFORE placement. A 10mOhm low-side shunt only measures current that actually
   returns THROUGH it. The loop must be:
   VSCAP -> independently inhibited high-side drive -> wing conductor -> heater
   -> dedicated return -> per-channel shunt -> hub ground.
   This is a functional requirement, NOT a selected high-side driver part.
   A grounded wing return bypassing the shunt invalidates it. An AO3400A alone
   driven by 3.3V cannot be assumed to be a high-side switch at 5.4V.
   Alternative low-side switching needs an explicit supply conductor to the
   wing and changes the pad-voltage interpretation; approve/document the
   interface before selecting it. Do not silently tie solar negative to GND:
   stacked solar interfaces may float. ADR-051 explicitly requires a wing change.
4. Each ADC shunt input is Kelvin-referenced to the shunt ground, with a series
   resistor and RC filter selected against leakage, acquisition error and
   transient limits. The shunt itself defines the DC pull-down in normal operation;
   an open shunt/return must not leave an exposed ADC node floating or at VSCAP.
   Require a separate defined bias and rated isolation/clamp network for that
   fault. Values and parts remain BLOCKED pending loop and fault-voltage proof.
   Firmware pull-ups are not a substitute for external safe bias.
5. Powered ADC normal input range is GND..VDD, regardless of PGA full-scale.
   TI ADS111x SBAS444E sections 5.1/5.3 specify absolute input limits
   GND-0.3V..VDD+0.3V and maximum input current +/-10mA. These are damage
   limits, NOT operating targets. At VDD=0, a 2.7V divider is not safe.
   Require isolation that defaults OFF with ADC power absent and a discharge
   path to ground, or another datasheet-supported no-backfeed solution.
   Show all power sequences and component tolerances; do not use absolute
   clamp-current rating as permission for continuous injection.
6. Rail/solar dividers remain mandatory. Derive each from its own worst-case
   cold open-circuit voltage and reference, NOT a blanket 5.4V assumption.
   Bound divider output below minimum ADC VDD with margin, including resistor
   tolerance, ground shift and transients; enforce the same unpowered isolation.
   ADC2 already uses all FOUR inputs: no spare channel exists in ADR-148's table.
7. Safe reset means drive OFF by hardware, ADC invalid until configured, and
   no firing on I2C loss/brownout. A transparent SN74LVC1G373 latch plus 100k
   gate pull-down is NOT by itself a timed, reset-safe one-shot: a driven-high
   output overrides that pull-down. Prove inhibit, bounded pulse termination,
   startup state, serialization and retry lockout separately. Gate threshold
   is not evidence of fully enhanced MOSFET RDS(on).

## Timing and interpretation

- Boot: hardware inhibit asserted; configure ADC/mux/PGA; discard stale samples.
- Idle: low-side current is zero for BOTH intact and broken heater. Never report
  continuity from idle zero. A non-heating continuity probe would require a
  separately current/energy-limited excitation and thresholds; none is approved
  by this report.
- Drive: select only the active channel, allow RC settling and a fresh conversion
  after mux/PGA change. ADS1115 is multiplexed, not four simultaneous converters.
  At 860 SPS nominal conversion time is 1.163ms, before bus/oscillator allowances.
  Derive an actual timeout from worst-case conversion and filter tolerance.
- During drive, first establish valid current and valid supply; current collapse
  with supply/enable valid is electrical-open evidence only. Supply collapse,
  broken return, failed switch, ADC saturation or stale data are FAULT/UNKNOWN,
  not successful release. Use consecutive fresh samples, calibrated thresholds
  and an independent pulse timeout; missing ADC data must never extend a pulse.
- After drive OFF, zero current is expected and cannot establish a sever.
  Cutting a retaining nylon cord need not break the nichrome heater itself.
  Mechanical release requires independent observation; never infer it solely
  from heater continuity/current.

## Numerical corrections (not bench qualification)

At 5.4V, 2.17Ohm heater and 10mOhm shunt: I=2.477064A,
Vshunt=24.7706mV, Pshunt=61.358mW. At +/-0.256V range,
LSB=7.8125uV, current LSB=0.78125mA: 2.48A is about 3174 counts,
NOT 248 counts. A 10mA threshold is only 12.8 counts and needs an offset,
noise, ground-bounce and leakage budget. It is not yet qualified.
100k||100k with 100nF gives 5ms, not 10us.
10k||10k with 100nF gives 0.5ms / 318Hz, not 1.6kHz.
27uA at 5.4V is 146uW, not 0.15W. 100Ohm*630pF is 63ns, not 13ns.

## Required verification before layout

- Pin-by-pin hub AND wing netlist proving both current conductors, no parallel
  shunt return, connector current ratings and solar isolation/reference.
- Corner calculations or simulation for ADC powered/unpowered, VSCAP present,
  connector unplug/replug, open shunt, shorted heater, short to each solar rail,
  reset and brownout. Supply injection must be bounded without back-powering.
- Dummy-load tests only initially: resistor load and open/short fault fixtures,
  current-limited supply, scope capture at drive/gate/shunt/ADC/supply; quantify
  filter settling, thresholds, pulse timeout and restart lockout. No actual
  cutter actuation or pressure operation was performed or authorized here.
- Schematic ERC/parity and independent electrical review before copper; later
  DRC is necessary but cannot prove the electrical contract.

## Reproduction and evidence limits

`gh pr view 524 --repo felixfelix-bot/balloon-fresh --json state,headRefOid`
`git show 2449ad8a:docs/adr/148-ads1115-analog-sense-and-rail-telemetry.md`
`python3 docs/analysis/open25_arithmetic_check.py`

Primary source: https://www.ti.com/lit/ds/symlink/ads1115.pdf
(SBAS444E, December 2024), downloaded and converted with pdftotext in this audit.
Microchip DS20001952C fetch was blocked; no MCP-specific absolute maximum is
asserted as verified here. Direct raw-node wiring remains rejected without it.
No circuit, board copper, order tag or v10 artifact changed. No purchases.
This is a correction and gating contract, not a complete component-qualified
schematic; independent review and the listed electrical evidence remain blockers.
