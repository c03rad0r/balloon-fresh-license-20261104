# Base 5 V logical supply correction — NOT a qualified power tree

Follow-up: [MCU supply block](mcu-supply.md) supersedes the historical
unspecified/floating U_LDO and missing MCU decoupling findings below.
Other blockers, especially 18 V input, remain unchanged.

Base: PR #532 `82071ddc126001275bbbb20e848f02c527428d58`. Isolated branch
`pr/base-5v-supply`; worktree `~/worktrees/pr-base-5v-supply`. Worktree inventory
and live PR #532 head inspected before editing; no competing branch/worktree
with this ownership existed. Decision: [ADR-086](../../adr/086-base-station-fixed-5v-correction.md).

## Exact sources and reasoning

- [TI TPS6216x SLVSAM2E](https://www.ti.com/lit/ds/symlink/tps62160.pdf),
  §§5–7, 8.3–8.4, 9.2.2 and package addendum: TPS62162 = 3.3 V;
  **TPS62163DSGR = fixed 5.0 V**, WSON/DSG, active ordering code. Both use
  1 PGND, 2 VIN, 3 EN, 4 AGND, 5 FB, 6 VOS, 7 SW, 8 PG, EP AGND (pad 9).
  Same 2×2 mm body, 0.5 mm pitch, 0.9×1.6 mm EP. FB grounded for fixed output;
  VOS senses output after L1. Existing stock DSG footprint retained.
- [ADL5240 Rev A](https://www.analog.com/media/en/technical-documentation/data-sheets/adl5240.pdf),
  power supplies table: **4.75–5.25 V**, amplifier 93 mA typical / 120 mA maximum,
  DSA 0.5 mA. A 3.3 V rail cannot meet this. The 5 V requirement is real.
- [AD8318 Rev E](https://analog.com/media/en/technical-documentation/data-sheets/AD8318.pdf),
  power interface: 4.5–5.5 V, 68 mA typical, 82 mA maximum at 25°C,
  temperature slope 150 µA/°C. **Frozen 15 mA allowance is wrong.**
- [ZX60-P103LN+ Rev D](https://minicircuits.com/pdfs/ZX60-P103LN%2B.pdf), p2:
  specified at 5 V; 95 mA typical / 120 mA max at 25°C; p3 absolute maximum
  5.5 V is not a recommended operating range. External masthead load retained.

TI and Mini-Circuits PDFs downloaded and text-read directly. ADI direct downloads
repeatedly timed out / extraction was blocked; manufacturer-PDF indexed tables
were read via search. Thus ADI full-document/local-hash verification remains open,
not falsely reported as a successful download.

## Startup, passives and local decoupling

EN connects directly to VIN_GS_PROT as in TI's typical application. This removes
output-dependent startup and does not involve MCU I/O. TI EN absolute maximum is
VIN+0.3 V; this does not raise VIN's recommended 17 V limit. Internal soft start:
about 50 µs delay and 25 mV/µs ramp (typical), not guaranteed system sequencing.

PG is open drain: **RC0603FR-07100KL**, 100 kΩ ±1%, 0603, 0.1 W to **+3V3_MCU**.
TI reference uses 100 kΩ; 33 µA sink at 3.3 V is below its 2 mA logic-low rating.
[Exact resistor](https://digikey.com/en/products/detail/yageo/RC0603FR-07100KL/726889).
Never pull this MCU-connected net to 5 V. PG can assert at 92% nominal and is
high-impedance in shutdown: it is telemetry, **not a fail-safe RF rail-valid gate**.

TI §9.2.2 recommends 2.2 µH / 22 µF output and 10 µF input, X5R/X7R ceramics.
Selected real parts, not generic placeholder values:

| Ref | Part | Evidence |
|---|---|---|
| L1 | Bourns SRN4018-2R2M, 2.2 µH ±20%, 44 mΩ max, 2.9 A Irms / 3.0 A Isat at 25°C | [Manufacturer table](https://bourns.com/docs/Product-Datasheets/SRN4018.pdf); existing `L_Bourns-SRN4018` source footprint retained |
| C_IN | Murata GRM31CR61E106KA12L, 10 µF ±10%, 25 V X5R 1206 | [Part specification](https://www.murata-capacitor.com/pdf-6b/grm31cr61e106ka12l.pdf), [catalogue](https://www.datasheets.com/murata/grm31cr61e106ka12l) |
| C_OUT | Murata GRM31CR71A226KE15L, 22 µF ±10%, 10 V X7R 1206 | [Exact part](https://digikey.com/en/products/detail/murata-electronics/GRM31CR71A226KE15L/2039036) |

C_IN is VIN-to-ground local input bypass; C_OUT is output-to-ground local bypass;
VOS must Kelvin-sense C_OUT after L1 in the eventual schematic/layout. Nominal
filter values are TI-recommended, **effective capacitance is not yet qualified**:
TI Table 2 assumes about ±20% combined variation, and these specific parts require
DC-bias curves at 17 V/5 V plus temperature/tolerance/aging before release. No
claim that 10 V rating alone proves adequate effective output capacitance.
The existing VGA/LNA local capacitors are retained; adding arbitrary capacitors
to the incorrectly mapped RF ICs would not fix their pinout and is deferred.

Inductor nominal static ripple at 17→5 V, 2.25 MHz is
`5*(1-5/17)/(2.2e-6*2.25e6) = 0.713 A p-p`. At 0.5 A load,
peak is 0.857 A (1 A load: 1.357 A), below the selected 3 A saturation rating.
At −20% L these become 0.946/1.446 A. This is a nominal-frequency sizing check,
not worst-case switching-frequency, fault-current or temperature qualification.
No need to invent a new TDK footprint merely to use the TI example inductor.

## Corrected load envelope, not a fabricated worst-case guarantee

`120 + 0.5 + 82 + 120 + 50 = 372.5 mA`; adding 25% yields **465.625 mA**.
Adding the detector's 25→85°C slope (9 mA) yields **476.875 mA** with margin.
This fits the intended 0.5 A envelope and is below the converter's 1 A rating,
but MCU 50 mA remains an allowance, DSA 0.5 mA is not a proven max, and LNA
hot current, flash, LDO quiescent current, inrush and switch faults remain unbounded.
The historical 316 mA is preserved only as a transcription of the frozen error,
not an acceptable current signoff. The logical spec tests do not prove power adequacy.

## Unsupported corners / release blockers

- **18 V input unsupported.** 3–17 V is the converter recommended input range;
  20 V absolute maximum is not permission to operate at 18 V. The unspecified
  D_REV/D_TVS cannot prove VIN_GS_PROT ≤17 V. The frozen 9–18 V system requirement
  remains open, not silently narrowed or waived. No energizing this board.
- TI fixed-output accuracy excludes line/load regulation: PWM ±3%, power-save
  −3.5/+4% gives 4.825–5.20 V. ADL5240 leaves only 75 mV downward / 50 mV upward
  before bead loss, ripple and transients. Worst-case RF voltage compliance is unproven.
- U_LDO remains unspecified and LDO_EN floating. This milestone repairs **buck**
  startup only, not MCU startup. Existing MCU 3.3 V and 1.1 V connections unchanged.
  Full MCU local/core decoupling and ADC overvoltage protection remain outstanding.
- Placeholder current limiter cannot establish no-LNA-fault MCU survival. RF pinmaps,
  RF bias/chokes, BPF parts, tee interface, EMI, thermal and capacitive load response
  still need authoritative schematic design and tests. No blanket readiness claim.
- No authoritative base `.kicad_sch`, no ERC, no new DRC/physical validation. Native
  PCB deliberately unchanged/rejected, no routing. Existing rejected-board report applies.

## Observed validation

Before implementation: `test_5v_supply.py` ran 7 tests, **FAILED (failures=7)**
(including three passive subtests): wrong fixed voltage, EN on output-fed REG_EN,
missing PG resistor, stale divider and unselected passives. Existing domain/parity
checks passed. After regeneration: **7/7 pass**, pin-map regressions **9/9 pass**,
legacy netlist topology checks **25/25 pass**. Generator: **42 components, 41 nets**.
Those legacy topology checks are NOT fault-isolation or electrical proof.

Reproduce from root:
```
/usr/bin/python3 tracker/hardware/base_station/gen_base_station_netlist.py
/usr/bin/python3 tracker/hardware/base_station/test_5v_supply.py
/usr/bin/python3 -m unittest discover -s tracker/hardware/base_station -p 'test_*pinmap.py'
/usr/bin/python3 tracker/hardware/base_station/test_netlist_implements_spec.py
```
`test_spec_transcription.py` remains blocked by its pre-existing hardcoded missing
`/home/c08r4d0r/worktrees/v9-route/.../spec.json` path. Not claimed green.
