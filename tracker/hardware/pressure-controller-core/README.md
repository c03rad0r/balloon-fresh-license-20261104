# Pressure controller: verified module/reset sub-block — NOT FAB READY

Bounded first stage from live master 2449ad8a. PR521 is specification, not schematic;
PR528 quarantines the unsafe seven-pad scaffold. Inspected its electrical blockers
and competing origin/feat/pressure-rig and origin/pr/pressure-rig-electrical-fix.
No old scaffold reused, no PCB generated, v10 unchanged, no hardware actuation.

## Delivered

Native KiCad RF_Module:ESP32-S3-WROOM-1 symbol (41 pins), native matching footprint
with exact pad-number-set comparison, reset 10k/1u RC and pushbutton, boot 10k
pullup and pushbutton, 10u + 100n local supply decoupling. Every unused module pin
is explicitly NC for this SUB-BLOCK, not a final reservation decision. Pin map
records every pin, its official name, footprint and assigned net. Stock symbol and
footprint files are hashed. Embedded symbols make the schematic loadable; installed
KiCad libraries are required for regeneration/ERC library comparisons.

Power flags model an EXTERNAL verified 3.3V source at this stage, not a regulator.
USB_DN_BOUNDARY and USB_DP_BOUNDARY deliberately end here. ERC reports exactly two
label_dangling errors at those boundaries; **not ERC-clean**, and no waiver for a
final assembly. Tests enforce this exact count and actual exported connectivity.

## Selected next-stage architecture (not implemented/qualified here)

Logic powered only from USB5V through a >=1A-rated 3.3V synchronous buck (target
TPS62162 fixed 3.3V family, exact package/application circuit still to verify).
1A output rating provides 2x Espressif's 500mA minimum recommendation; source current,
startup, capacitor DC bias, transient droop, thermals and USB allowed current must
still be validated. Do NOT infer 1A available from any USB host simply because a
converter is rated 1A. Before enumeration/current permission, enforce source limits
or require an explicitly suitable USB supply. This is a selected architecture, not
a completed adequate supply schematic.

External 6V pump rail stays OUTSIDE logic power path: no diode bridge to USB5V,
no pump-rail-to-3V3 converter and no motor connection in this sub-block. Later common
ground arrangement is not galvanic isolation and needs return-current review.
USB-C connector selection/native footprint, both independent 5.1k CC pulldowns,
A/B duplicate D+/D- contacts, VBUS/GND/shield, ESD and recommended USB series resistor
provisions are still outstanding. No claim that USB programming already works.
Reset/boot are manual; USB serial/JTAG uses module pads 13/14 (GPIO19/20).

## Source basis

- Espressif hardware guidance, retrieved 2026-11-10 via curl:
  https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html
  recommends 3.3V and >=500mA, >=10u at entrance, and EN RC typically 10k/1u.
- Official module datasheet linked by the KiCad symbol:
  https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
  Full ordered module suffix, PSRAM GPIO restrictions and independent manufacturer
  land-pattern cross-check remain release gates; this stage verifies native-library
  pin-to-pad identity, not purchasing readiness.

## Reproduce (KiCad 9.0.9, Python standard library only)

From repository root:

```sh
D=tracker/hardware/pressure-controller-core
python3 "$D/generate.py"
kicad-cli sch export netlist --format kicadxml -o "$D/core.xml" "$D/core.kicad_sch"
kicad-cli sch erc --format json -o "$D/erc.json" "$D/core.kicad_sch"
python3 "$D/test_core.py"
```

Future connector-to-motor edges, dual MS5611, default-OFF motor suppression,
independent shutdown, alarm, firmware and pressure-unit ambiguity remain BLOCKED
per PR528. No fabrication or inflation approval follows from this sub-block.
