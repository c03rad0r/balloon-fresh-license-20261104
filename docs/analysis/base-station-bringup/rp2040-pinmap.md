# RP2040 logical correction — NOT a working controller or shipment gate

PR532 continuation, verified OPEN, owner felixfelix-bot, branch
`pr-base-station-bringup`, clean starting HEAD
`d140e327c1fb296853e30bd672e5d02ca28d45db`.

## Manufacturer basis and scope

Read official [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf),
§1.4 Figure 3 (printed p11, PDF p12, visually inspected) and §2.9 supplies.
The diagram's exposed GND pad has no printed number; existing footprint calls it 57.
This repairs the direct-netlist generator, not a native schematic or copper.
No PCB/project/footprint/placement edits or routing, no v10 changes, no purchase/actuation.

The old source did **not** define an authoritative GPIO allocation. New explicit allocation:
GPIO18/19/20 gain0/1/2; GPIO21 LNA_EN; GPIO22 LNA_FLT;
GPIO25 REG_PG; GPIO26/ADC0 DET_VOUT. These preserve interface **net names and opposite
endpoints**, not compatibility with unspecified firmware. Firmware must adopt this map.
The table records every package pad, including the already-correct RUN and exposed GND.
Unused GPIOs are now unconnected instead of grounded or incorrectly powered.

IOVDD, ADC_AVDD, USB_VDD and VREG_VIN use the existing +3V3_MCU domain.
VREG_VOUT and both DVDD pins join a separate +1V1_CORE net, per §2.9.7.1.
C_MCU1/2 move off the floating IOVDD net onto +3V3_MCU; full bypass network is still missing.
QSPI flash pin2 is DO/IO1, pin5 DI/IO0 (previously swapped), using the standard serial-NOR
logical convention; **exact flash MPN and EP package remain unselected/unqualified**.
All other 40 components' values, footprints and complete pin pairs compare identical to starting HEAD,
including regulator and RF interfaces. No claim their existing mapping is correct.

## Exhaustive physical-package audit

| Physical pad | Manufacturer function | Before net | Corrected net |
|---|---|---|---|
| 1 | IOVDD | IOVDD | +3V3_MCU |
| 2 | GPIO0 | GND | unconnected |
| 3 | GPIO1 | ADC_AVDD | unconnected |
| 4 | GPIO2 | GND | unconnected |
| 5 | GPIO3 | IOVDD | unconnected |
| 6 | GPIO4 | GND | unconnected |
| 7 | GPIO5 | DET_VOUT | unconnected |
| 8 | GPIO6 | GND | unconnected |
| 9 | GPIO7 | GND | unconnected |
| 10 | IOVDD | QSPI_SS | +3V3_MCU |
| 11 | GPIO8 | QSPI_SCLK | unconnected |
| 12 | GPIO9 | QSPI_SD0 | unconnected |
| 13 | GPIO10 | QSPI_SD1 | unconnected |
| 14 | GPIO11 | QSPI_SD2 | unconnected |
| 15 | GPIO12 | QSPI_SD3 | unconnected |
| 16 | GPIO13 | +3V3_MCU | unconnected |
| 17 | GPIO14 | GND | unconnected |
| 18 | GPIO15 | VGA_GAIN0 | unconnected |
| 19 | TESTEN | VGA_GAIN1 | GND |
| 20 | XIN | VGA_GAIN2 | XIN |
| 21 | XOUT | LNA_EN | XOUT |
| 22 | IOVDD | LNA_FLT | +3V3_MCU |
| 23 | DVDD | GND | +1V1_CORE |
| 24 | SWCLK | XIN | SWCLK |
| 25 | SWDIO | XOUT | SWDIO |
| 26 | RUN | RUN | RUN |
| 27 | GPIO16 | GND | unconnected |
| 28 | GPIO17 | SWCLK | unconnected |
| 29 | GPIO18 | SWDIO | VGA_GAIN0 |
| 30 | GPIO19 | GND | VGA_GAIN1 |
| 31 | GPIO20 | GND | VGA_GAIN2 |
| 32 | GPIO21 | GND | LNA_EN |
| 33 | IOVDD | USB_DM | +3V3_MCU |
| 34 | GPIO22 | USB_DP | LNA_FLT |
| 35 | GPIO23 | GND | unconnected |
| 36 | GPIO24 | GND | unconnected |
| 37 | GPIO25 | GND | REG_PG |
| 38 | GPIO26/ADC0 | GND | DET_VOUT |
| 39 | GPIO27/ADC1 | GND | unconnected |
| 40 | GPIO28/ADC2 | GND | unconnected |
| 41 | GPIO29/ADC3 | GND | unconnected |
| 42 | IOVDD | GND | +3V3_MCU |
| 43 | ADC_AVDD | GND | +3V3_MCU |
| 44 | VREG_VIN | GND | +3V3_MCU |
| 45 | VREG_VOUT | GND | +1V1_CORE |
| 46 | USB_DM | GND | USB_DM |
| 47 | USB_DP | GND | USB_DP |
| 48 | USB_VDD | GND | +3V3_MCU |
| 49 | IOVDD | GND | +3V3_MCU |
| 50 | DVDD | REG_PG | +1V1_CORE |
| 51 | QSPI_SD3 | GND | QSPI_SD3 |
| 52 | QSPI_SCLK | GND | QSPI_SCLK |
| 53 | QSPI_SD0 | GND | QSPI_SD0 |
| 54 | QSPI_SD2 | GND | QSPI_SD2 |
| 55 | QSPI_SD1 | GND | QSPI_SD1 |
| 56 | QSPI_SS_N | GND | QSPI_SS |
| 57 | GND exposed pad (footprint convention) | GND | GND |

## Executed evidence

- `python3 tracker/hardware/base_station/test_rp2040_pinmap.py`: RED exit1, 4/6 failed
  (source map, emitted netlist, flash direction, floating MCU bypass supply); after repair GREEN 6/6.
  Negative controls mutate each of 34 assigned pads and inject a grounded unused GPIO: all refused.
- `test_regulator_pinmap.py`: 3/3 pass (earlier regulator correction preserved).
- `test_netlist_implements_spec.py`: 25/25 pass after replacing stale v9-route path
  with the script's own directory. These are legacy topology assertions, **not ERC**, and do
  not prove fault isolation, RF IC correctness or regulator voltage.
- Generator executed: 44 components, 43 nets (removed floating IOVDD/ADC_AVDD, added +1V1_CORE).
- `git diff --check`: pass. No native `.kicad_sch` found under base_station.
- PCB SHA256 `095d0278410465f24a2f229969a21017d469bfd34c31f597fea24a6d6afe61af` and project
  `d2d19f93e8df91d04bf8a0c3bcd10f25e863d3948a38412be4d17b15cc51d214` unchanged.
  Prior recorded native DRC therefore remains 143 violations / 63 opens / 44 footprints / zero tracks;
  not rerun or improved here. PCB intentionally does not match corrected logical netlist.

## Remaining blockers (explicit, no rail redesign)

1. **TPS62162 is fixed 3.3V, contradicting frozen 5V requirement** (TI SLVSAM2E §5;
   TPS62163 is the fixed 5V variant). Existing misleading value/spec preserved as unresolved,
   not silently substituted. Output-powered enable startup, 18V input vs 17V operating limit,
   PG pull-up, protection, disconnected legacy divider and component qualification unresolved.
2. No native schematic, native ERC, or tested forward schematic-to-board parity. Direct-netlist
   tests cannot provide these gates; must rebuild schematic before regenerating this invalid board.
3. RP2040 requires local 100nF at each IOVDD/DVDD/USB_VDD/ADC_AVDD and 1uF regulator input/output
   support; present two MCU caps do not satisfy this. Crystal selection/load/series resistance,
   flash exact MPN/footprint/pull-ups/boot access, SWD pull-up, firmware GPIO alignment remain open.
4. USB_DM/DP remain MCU-only singleton nets: no USB connector or required 27-ohm series termination.
   Pin correction is not an implemented USB port. ADC range/protection and REG_PG logic-level/pull-up
   safety remain unproven. Unspecified LDO and load-switch (including floating LDO_EN) remain invalid.
5. RF IC pin maps/parts and bias-tee interfaces still need schematic validation; preserved second BPF,
   no added PA, separate LNA/VGA/detector/MCU domains are only intent checks.
6. RP2040 footprint manufacturer qualification, 37 clearance plus assembly/silk violations,
   unrouted board, RF placement/impedance, manufacturing/assembly checks and bench bring-up remain open.

Not fab-ready, not shipment-ready, no merge performed.
