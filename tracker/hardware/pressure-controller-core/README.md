# Pressure controller core — partial, NOT FAB READY

Full official 41-pin ESP32-S3-WROOM-1 and matching footprint preserved, including
10k/1u reset timing, RESET/BOOT switches, boot pullup, 10u + 100n bypass.
No motor rail, pump/cutter actuation, purchase or PCB included.

## USB and supply implementation

J1 is official KiCad USB_C_Receptacle_USB2.0_16P with native GCT USB4105
16-pin footprint. All 16 contacts plus shield are represented; footprint pad
number sets are checked. Both VBUS pairs join USB5V; all grounds and shield join
GND. SBU1/2 explicitly NC. Separate R3/R4 5.1k 1% CC-to-ground resistors implement
a sink, not PD negotiation or source-current detection. A/B duplicate D-/D+
contacts join through R5/R6 22-ohm resistors to S3 pads 13/14 (GPIO19/20).
Place resistors near MCU; route USB as a differential pair. USB operation has
not been physically tested. ESD protection remains outstanding.

U2 AP2112K-3.3TRG1 (SOT25/SOT-23-5): pin 1 VIN=USB5V, 2 GND,
3 EN=USB5V, 4 NC, 5 VOUT=3V3. No feedback divider required (fixed output).
C4 input and C5 output are 2.2uF 10V X7R; selection must retain >=1uF effective
capacitance at bias/tolerance/temperature, placed immediately by regulator.
Module C2/C3 remain additional local bypass. Only USB5V/GND have power flags;
3V3 is genuinely driven by regulator pin 5, not a fictitious external supply.

**Supply qualification NOT achieved:** regulator guaranteed current rating is
600mA, 20% above Espressif's >=500mA recommendation, but that does NOT establish
continuous thermal adequacy. At 5.25V input / 3.3V / 500mA dissipation is 0.975W;
datasheet SOT25 thetaJA 184 C/W implies ~179C rise without heat spreading.
This exceeds operating limits. Do not operate this as a sustained 500mA supply.
A switching converter or thermally proven larger-package solution must replace
this bounded prototype circuit before release. Earlier proposed TPS62162 buck
has not been implemented. This milestone closes USB connectivity, NOT power
qualification. It must not be represented as a completed adequate supply.

Power-source assumption: USB only, regulated 4.75–5.25V, explicitly provisioned
>=1A source/data-capable powered hub with adequate current permission. Ordinary
USB host pre-enumeration current limits are NOT satisfied by this assumption;
no current negotiation/enforcement circuitry or firmware is included. Never
back-feed 3V3 or USB5V from another source. Motor supply remains excluded.

## Verification

Native netlist export passed. Exported-pin tests cover connector duplicate pins,
CC resistors, both USB series paths, regulator pin map/passives, module/reset.
The former two USB label_dangling findings are closed. Native ERC reports **one
warning**: `lib_symbol_mismatch` for U2 AP2112K-3.3 (flattened inherited official
symbol). No electrical ERC errors; ERC with --exit-code-violations exits 5.
This warning is recorded, not suppressed or represented as zero findings.

```sh
D=tracker/hardware/pressure-controller-core
python3 "$D/generate.py"
kicad-cli sch export netlist --format kicadxml -o "$D/core.xml" "$D/core.kicad_sch"
kicad-cli sch erc --format json --exit-code-violations -o "$D/erc.json" "$D/core.kicad_sch"
python3 "$D/test_core.py"
```

## Primary sources inspected

- https://www.diodes.com/assets/Datasheets/AP2112.pdf — DS39724 rev 2-2,
  pp1–3: 600mA rating, pin table, 1uF input/output application, thermal resistance.
- https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html
  — 3.3V >=500mA recommendation.
- https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
  — module reference retained from preceding milestone.

Remaining release gates: regulator redesign/thermals, effective capacitor BOM,
connector manufacturer drawing cross-check and exact ordering suffix, USB ESD,
source permission/inrush, layout, physical USB and transient tests, module suffix,
sensors, independent motor shutdown and all full-board safety provisions.
PR528 scaffold remains quarantined; v10 unchanged.
