# v11 cut channels — four nichrome cutters, hardware-serialised

**NOT FAB READY.** v11 is unrouted and D_BP top placement is unresolved. This closes one design
item, not the board.

Scope item 3 of 4. Base: master `89fcbab5` (PR #546 merged). Worktree `~/worktrees/pr-v11-cutdrivers`.

## The architecture question, answered by arithmetic

The open problem was protecting an unpowered ADS1115 from a 5.4 V cutter fault. **Option (A), a
held-up ADC supply domain, was rejected on arithmetic — not preference.** The hazard is not a
transient: `/VSCAP` is a 1.65 F bank holding 16.63 J and stays above the hazard threshold for
**~46 h** at the 100 µW night load. Holding the ADS1115 up at its 300 µA maximum needs
**0.83 F for one hour, 38.2 F for 46 h**. The TPS3808's 20 µs *typical* delay is nine orders of
magnitude short and has no guaranteed maximum.

**Option (B) adopted:** divider-only, sense tap taken so the pin sees a bounded voltage with the
switch off.

## Measured electrical result

Loop = heater wire + shunt + R_DS(on) = 2.17 + 0.1 + 0.048 = **2.318 Ω** (the 100 Ω gate resistor
is in the *gate* path and does not carry heater current).

| quantity | value |
|---|---|
| peak current | **2.3296 A** |
| shunt voltage | **233.0 mV** |
| total loop dissipation | **12.58 W** |
| cut time (2.59 J into the wire) | **220 ms** |
| shunt | 0.1 Ω, 2512, 1 % |
| ADC counts at ±4.096 V FSR, 125 µV LSB | **465.9** (5.0 mA/count) |
| sense divider | 300 k / 100 k = ¼ |
| pin voltage at the 9.28 V fault | **2.320 V** — **1.280 V inside** the 3.6 V abs max |
| divider loading error | **0.50 %** vs 15 MΩ typ |

The earlier 193 ms figure had no shunt and no R_DS(on); 220 ms is the corrected value. The earlier
10 mΩ shunt figure came from computing against the ±0.256 V PGA, which is not this board's FSR.

## Serialisation is HARDWARE, not a promise

`SN74LVC1G139` one-hot decoder drives the four latch `/OE` lines. Table 4 of its datasheet
guarantees exactly one output LOW per address, so **no firmware defect can conduct two FETs**.
Four simultaneous would be 9.32 A = **198 % of the 4.7 A @ 70 °C rating** — the same hazard the
212 % framing described.

## Two-conductor loop — the earlier defect removed

`/VSCAP` → J_HT pin 1 → heater → J_HT pin 2 → drain → source → shunt → GND.

The `/CUT_SENSE_W<n>` single-conductor nets on `J_W<n>.3` are **released to UNASSIGNED**. That
release *is* the fix: a shared drive/sense conductor through the floating solar negative was the
defect the earlier review found.

## Gates — all executed, none asserted

- `test_v11_cut_channels.py`: **ALL GATES PASSED**, exit 0
- `--self-test`: **PASSED** — solar-negative return, missing shunt, force-node tap and two-hot
  decoder are each **REJECTED**, so the gate is proven able to fail
- **ERC: 9 = 9**, and `diff` shows the violation *set* is identical — zero net new
- `test_v11_scap_adc.py` passes after inverting PR #546's now-obsolete "unused AINs must be
  grounded" assertion — correct, because AIN0–3 now carry the cut-sense channels

Two real defects the ERC caught and were **fixed rather than suppressed**: `R_Shunt` is a genuine
four-terminal Kelvin part (8 unconnected pins; the sense now taps the Kelvin pad, excluding
force-path IR drop), and `AO3400A` is a *derived* KiCad symbol whose flatten trips
`lib_symbol_mismatch` (now uses the parent `Q_NMOS_GSD` with value AO3400A).

## Not proven — recorded, not papered over

1. **The powered-off voltage bound is violated:** the pin sees 2.320 V against a collapsed 0.3 V
   bound. Current is bounded at **26.6 µA** against the 10 mA rating (376×), but **TI publishes no
   Ioff / powered-off input characteristic**. The honest claim is "bounded stress by resistor
   division alone" — not "protected".
2. **SN74LVC1G373 has no CLR pin and no guaranteed power-up state.**
3. **Latch leakage margin is thin:** I_OZ 5 µA × 100 kΩ = 0.5 V against V_gs(th) min 0.65 V →
   **0.15 V**. A 10 kΩ part gives 50 mV and is recommended, but 100 kΩ is the ADR-051 §2.5.1 value
   and was not changed unilaterally.
4. **No series arming gate** (ADR-051 §2.5.1) — the GPIO budget is 3 of 3, all used.
5. **No hardware on-time bound** — a hung MCU holding `/CUT_FIRE` runs one channel indefinitely.
6. **The four-land wing tab cannot carry the two-conductor loop.** J_HT is a stand-in with no
   established current rating.
7. The 9.28 V rail figure is an estimate; nothing is qualified below −40 °C; nothing is
   bench-tested.

## Verification note on parity

Netlist parity is proven **registry↔sheet** (byte-identical generated block). The parity run
against `hub_board_v10.kicad_pcb` "fails" meaninglessly: there is no v11 PCB, and that board's
`CUT_SENSE_W1..4` rows are precisely the old single-conductor topology this change removes. It
needs a v11-aware target, not a v10 comparison.

## Remaining v11 order

1. D_BP top placement (PR #530 evidence stands)
2. `/SCAP_ADC` + solar dividers — **merged** (#546)
3. **cut channels — this item**, with the seven open items above
4. GPIO / MCP23017
5. route
