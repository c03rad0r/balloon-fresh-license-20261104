# Pressure controller core — buck schematic milestone, NOT FAB READY

Official ESP32-S3-WROOM-1, all 41 pads, reset/boot circuit and USB-C data/CC
connections preserved. No motor rail, pump/cutter actuation, purchase or PCB.

## Implemented supply

U2 is **TPS62160DSGR**, 1A synchronous adjustable buck, official KiCad
`Regulator_Switching:TPS62160DSG` and official WSON-8 exposed-pad/thermal-via
footprint. Not the thermally rejected AP2112 LDO or the poorer-thermal DGK package.
TI SLVSAM2E §6 verifies: 1 PGND, 2 VIN, 3 EN, 4 AGND, 5 FB, 6 VOS,
7 SW, 8 PG, exposed pad ground (KiCad 9). VIN and EN join USB5V; all grounds
and pad join GND. PG unused/NC. SW feeds L1 then 3V3; VOS directly senses
3V3, NOT FB. R7=100k and R8=32k, both 0.1%, set 0.8*(1+100/32)=3.300V.
Internal feedforward capacitance is included by TI; no external Cff required.

L1 is Coilcraft XAL6030-332MEC, 3.3uH ±20%, official
`Inductor_SMD:L_Coilcraft_XAL6030-XXX`. Manufacturer specifies 20.8mΩ maximum
DCR at 25°C, 12.2A typical saturation at 30% inductance loss, 6A RMS for
20°C reference temperature rise. Oversized intentionally for current margin.
C4 input is Murata GRM32ER71E226KE15L 22uF/25V/X7R/±10%/1210;
C5/C6 are two of the same in parallel at output (44uF nominal).
C2/C3 remain S3-local bypass. All footprints are stock, pad sets checked.

**Capacitor qualification remains open:** nominal voltage is NOT proof of
biased capacitance. Require C4 >=10uF effective at 5.5V and C5+C6 >=22uF
at 3.3V across tolerance, temperature and aging; verify input ripple >=0.5A
without unacceptable heating. Manufacturer part specification verified, but
numeric DC-bias curve not obtained in this milestone. Thus this is a real
complete buck topology, NOT a fully qualified production supply.

## Operating envelope and arithmetic

Dedicated rig input: 4.75–5.5V at connector, 1A maximum 3V3 load, 0–60°C
ambient target. TI recommended VIN 3–17V and TJ -40–125°C cover voltage
range; 150°C absolute max/thermal shutdown are not operating targets.
No PD higher voltage, reverse/backfeed or motor power permitted.

The source MUST be a suitable regulated USB supply with externally verified
**1.5A or 3A Type-C current advertisement** and suitable cable. The two 5.1k
Rd resistors only identify a sink; they do NOT authorize arbitrary current.
This block does not detect advertisement, negotiate PD or enforce current.
Do not use arbitrary PC USB ports or rely on enumeration for power permission.
External verification/interlock and inrush qualification are deployment gates.

`test_supply.py` checks the exported BOM and conditional calculations:
- L envelope = 3.3uH * 0.8 * 0.7; engineering f floor 1.5MHz yields
  0.476A p-p ripple, 1.238A peak at 1A, 1.009A RMS.
- 20% peak margin remains far below the inductor's 25°C saturation reference.
- TI specifies 2.25MHz **typical**, not a guaranteed minimum. The 1.5MHz
  floor/30% inductance allowance are explicit validation assumptions, not
  datasheet guarantees. Hot/fault saturation must still be checked.
- WSON reference thetaJA=61.8°C/W gives 1.052W IC loss budget at 60°C/125°C.
  Actual copper/thermal vias and measurement determine real thetaJA.
- 75% efficiency is a future acceptance threshold, NOT guaranteed from typical
  efficiency plots. At that threshold input is 0.926A at 4.75V/1A output.
  Total loss would be 1.10W; measure IC loss/temperature separately.
- Initial PWM accuracy is ±3% excluding line/load effects. Divider tolerance
  and up to 40mV FB leakage error also apply. Check rail overshoot and S3 limits
  in load-step tests; no precision rail claim.

Layout must implement TI §11: short VIN/PGND capacitor loop, SW/L/output loop,
Kelvin VOS at output capacitors, quiet FB/AGND, single-point ground connection
and soldered exposed pad/thermal vias.

## Placement candidate — UNROUTED, PENDING OPERATOR GATE

`placement/core-placement.kicad_pcb` is a native, **unrouted** placement derived from
`kicad-cli sch export netlist` (125 endpoints, 26 references) with the exact qualified
footprints; see [PLACEMENT-CANDIDATE.md](PLACEMENT-CANDIDATE.md) for the geometry, the
measured DRC/opens figures, the decisions and the remaining placement issues.

```sh
/usr/bin/python3 "$D/placement.py" && /usr/bin/python3 "$D/verify_placement.py"
/usr/bin/python3 "$D/test_placement.py" && /usr/bin/python3 "$D/poison_placement.py"
```

No routing, no fab release, no motor circuit. `placement/top.png` / `placement/bottom.png`
are the operator views, hash-bound to the board in `placement/view-proof.json`.

## Verification and saved report

`SUPPLY-REPORT.md` records observed red/green results. Fresh KiCad 9.0.9 export
and ERC pass: **zero violations**, exit 0, no exclusions. Inherited-symbol
loader now inherits base pin/display flags as well as renamed units; this fixes
the mismatch rather than suppressing ERC. Output PWR_FLAG documents power
through passive L1 (KiCad does not propagate a driver through an inductor).
Independent exported-pin tests require the actual SW/L/3V3 and VOS/FB paths.

```sh
D=tracker/hardware/pressure-controller-core
python3 "$D/generate.py"
kicad-cli sch export netlist --format kicadxml -o "$D/core.xml" "$D/core.kicad_sch"
kicad-cli sch erc --format json --exit-code-violations -o "$D/erc.json" "$D/core.kicad_sch"
python3 "$D/test_core.py"
python3 "$D/test_supply.py"
```

## Sources and remaining gates

- https://www.ti.com/lit/ds/symlink/tps62160.pdf — SLVSAM2E §§6–7, 9, 11;
  1A rating, pinout, 3.3uH low-input recommendation, capacitor range, thermals.
- https://coilcraft.com/en-us/products/power/shielded-inductors/molded-inductor/xal/xal60xx/xal6030-332
- https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM32ER71E226KE15-01.pdf
- https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html

Remaining: placement operator sign-off then routing, capacitor biased-capacitance/ripple
qualification, actual thermal
soak at 1A at both input extremes, startup/load-step/ripple measurement,
source permission/inrush, USB ESD and connector suffix/drawing cross-check,
physical USB tests, exact S3 suffix, sensors, independent motor shutdown and
full-board safety. PR528 scaffold remains quarantined; v10 unchanged.
