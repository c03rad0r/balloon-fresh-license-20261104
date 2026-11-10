# OPEN-25 independent review — partial electrical design

Reviewed PR526 at fcbff171c3dea11e69b77f4b943ee59ffc12a6e1, 2026-11-10.
Runtime exposes model alias `tier/delegation`, provider `custom`; actual served model/family is not exposed. This is independent-context review, NOT established cross-family verification.

## Verdict

No blocking defect found in PR526's deliberately incomplete electrical prerequisite contract. It is not a schematic, release gate closure, or fabrication authorization. Live ADR148/051/129 were read; the two-ADC architecture and full v11 scope are retained. Open PR list includes PR526 as the only named OPEN-25 electrical-contract effort; other solar/wing/fab work remains untouched.

Executed the committed script: six arithmetic checks PASS, I=2.477064 A, Vshunt=0.0247706 V, counts=3170.6. The prose's 3174 counts uses its explicitly rounded 2.48 A: 2.48*0.01/7.8125e-6 = 3174.4. Thus rounding, not a different circuit or arithmetic failure; prefer 3170.6 for consistency with the exact current. The original ADR148's 248-count claim is wrong. Its spare-channel claim is also wrong: ADC2 allocates all four inputs.

Primary datasheet checked directly: https://www.ti.com/lit/ds/symlink/ads1115.pdf . Absolute analog input limit GND-0.3..VDD+0.3 V and continuous pin current +/-10 mA agree with PR526. Neither is a license to back-power the ADC. Single-ended inputs require an actual ground-referenced shunt; stacked solar negative is not a general cutter return. Idle zero cannot establish continuity, and heater-open cannot prove release of a nylon restraint.

## Concrete next step, not a component-qualified closure

Freeze the two-wire cutter harness first. Retain RF_FEED as the driven conductor and add a dedicated per-wing heater return to the hub's individual 10 mOhm Kelvin shunt; do not reuse any floating solar conductor. This needs an explicit connector/harness amendment, current rating and wing netlist. The existing three-pin U_CUT block is an abstract placeholder, not proof that a complete drive/control/return interface exists. If adding a conductor is mechanically impossible, put the heater and shunt entirely on the hub side of the release interface and separately document restraint geometry; do not pretend one conductor closes an isolated circuit.

Candidate isolation component: TI TMUX1511 (four SPST channels), primary source https://www.ti.com/lit/ds/symlink/tmux1511.pdf downloaded and read. It offers powered-off protection only up to **3.6 V** on its signal path, despite a powered signal ceiling of 5.5 V. Therefore it is a candidate **after suitably bounded dividers**, NOT directly on a raw 5.4 V cutter node and not an open-shunt fault isolator without upstream protection. Power from the ADC rail, default selects low, provide ADC-side discharge/bias; qualify maximum off leakage, resistor error, ramp behavior and voltage at every pin before selection. A 5.4 V raw-node fault fails its off-state bound by 1.8 V. Solar worst-case voltage must be independently bounded; a nominal 1:1 divider is not a qualification.

Drive architecture requirement: independent normally-off series inhibit plus per-channel selection, non-retriggerable bounded hardware pulse, hardware brownout/reset inhibit, and persist-before-arm per-channel fired state. The pulse limiter must terminate despite stuck I2C, stuck-high request, or absent ADC samples. Firmware serialization alone does not prove the hardware cannot select two channels. An RC gate delay or transparent latch is insufficient. A timeout IC alone does not provide persistent retry lockout across power cycles. No exact timer/supervisor/MOSFET combination was qualified within this bounded review; naming one without startup, voltage, SOA and timing-corner evidence would be unsafe.

Next implementation deliverable: pin-by-pin candidate schematic with power-domain truth table and per-fault proof, followed by dummy-load-only verification. Keep OPEN-25 electrical closure blocked until that exists. No copper, cutter, pump, purchase or scope reduction in this review. Hub v11, solar connectors, S3 pressure board and base-station scope remain unchanged.
