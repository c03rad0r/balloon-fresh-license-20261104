# Dual MS5611 measurement milestone — NOT PHYSICALLY QUALIFIED

**Land-pattern update:** [FOOTPRINT-REPORT.md](FOOTPRINT-REPORT.md) supersedes the
retained-stock-footprint decision below with a manufacturer-derived local footprint.
Copper mismatch repaired; assembly, thermal and port-access qualification remain open.

## Motivation and scope

Implement the approved internal-minus-ambient measurement chain on the native S3 core,
without inventing a balloon pressure limit. Supply unchanged; no motor block, actuation,
PCB, purchases or firmware changes. Branched from live master 871f23fc. Related: #531
(native S3 core), #528 (quarantined scaffold). This report supersedes the README's
statement that sensors remain absent, not its supply qualification gates.

## DECISIONS / primary evidence

- U3 internal and U4 ambient are **MS5611-01BA03** (thin stainless cap, 5x3x1mm,
  eight contacts; TE calls the package QFN, KiCad calls its land pattern LGA).
  Ordering options in manufacturer p22: MS561101BA03-00 waffle, -50 tape/reel.
  Use stock `Sensor_Pressure:MS5611-01BA` (inherits MS5607 pin graphics), not an
  invented connector or fake pad shape. Its datasheet URL explicitly selects 01BA03.
- Pins: 1 VDD=3V3; 2 PS=3V3 selects I2C; 3 GND; **4 and 5 CSB internally connected**;
  6 SDO deliberately NC in I2C; 7 SDA; 8 SCLK. Both CSB pads explicitly wired alike.
  Manufacturer pp6–7,12,15: address is 111011C, **C = complement of CSB**.
  U3 CSB low -> **0x77 internal**; U4 high -> **0x76 ambient**. These are 7-bit
  addresses, not R/W bytes. Fixed straps avoid floating mode/address jumpers.
  **Correction for docs worker:** RIG-ELECTRONICS-SPEC.md lines114–116 currently
  reverses this polarity. That documentation is outside this worker's edit scope.
- SDA GPIO8 = S3-WROOM-1 module pad12; SCL GPIO9 = pad17, verified against
  Espressif pin table. Both were unused/NC on the base schematic. They are not S3
  strapping pins (GPIO0/3/45/46); C3 GPIO8/9 restrictions do not apply to S3.
  N8R8 memory restrictions on GPIO35–37 do not consume these pins.
- C7/C8 each 100nF ceramic local bypass (manufacturer pp3,17); R9/R10 each 4.7k
  to existing 3V3, one pair per shared bus. Nominal low-line current 3.3/4700 =
  0.702mA. Target 100kHz; no unmeasured bus-length guarantee.
- Stock `Package_LGA:LGA-8_3x5mm_P1.25mm` has real numbered pads1–8 and its
  hash is recorded in library-sha256.json. Independent consultation identified a
  deliberate review gate: stock pads **0.95x0.55mm**, column centres **2.15mm**,
  versus manufacturer p16 recommendation **1.1x0.6mm**, centres **2.2mm**; both
  use 1.25mm row pitch. Retain the real stock footprint rather than invent geometry,
  but require land-pattern/assembly acceptance or a datasheet-derived replacement
  before layout release. No claim that stock lands exactly match recommendation.
  Reserve area between sensor pads against routing per p16; solder all contacts.
- Schematic source properties identify `P_INTERNAL_ABS` and `P_AMBIENT_ABS`, with
  `DELTA_P = P_INTERNAL_ABS - P_AMBIENT_ABS; mbar; ACTUATION DISABLED`.
  These are measurement-domain annotations, not fabricated analog signal nets.
  A3 sheet accommodates the measurement row without modifying the supply block.

Manufacturer TE/Measurement Specialties datasheet, 06/2017:
https://amsys-sensor.com/downloads/data/MS5611-01BA03-AMSYS-datasheet.pdf
SHA256 `1fac201505813c97e0b9dff4d562a416b1ab67bb203dab138559f5e6234700b7`.
Official TE DocumentDelivery link in stock symbol returned HTTP403; this is a
mirror of the manufacturer document, not a substitute third-party pinout.
Espressif official:
https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
SHA256 `27d71971da07c280c6068d08c74720d1a25b8f20cf8494dc1765bdd28d40d435`.
Read-only independent topology consultation confirmed pins, complement polarity,
and S3 endpoints; surfaced stock-land discrepancy above. Served model family
was not exposed by delegation, so this is not claimed cross-family review.

## Actual RED / GREEN evidence

Before implementation, `python3 test_measurement.py` returned 1: `ValueError: U3 missing`.
After generation and fresh native export, KiCad 9.0.9 ERC returned 0: **0 violations**,
no exclusions. Existing core and supply tests passed. New measurement test passed.
`test_measurement_negative.py` passed clean and eight corrupted/missing input cases
under both normal Python and `-O` (16 required rejection runs): missing CSB endpoint,
PS, SDA, SCL, S3 SDA, swapped source label, empty XML, missing XML. Tests are
read-only and do not import the generator. These prove exported schematic
connectivity and labeling, NOT hardware performance or safety.

Reproduce from repo root:
```sh
D=tracker/hardware/pressure-controller-core
python3 "$D/generate.py"
kicad-cli sch export netlist --format kicadxml -o "$D/core.xml" "$D/core.kicad_sch"
kicad-cli sch erc --format json --exit-code-violations -o "$D/erc.json" "$D/core.kicad_sch"
python3 "$D/test_core.py"
python3 "$D/test_supply.py"
python3 "$D/test_measurement.py"
python3 "$D/test_measurement_negative.py"
```

## Exact remaining gates — all OPEN, actuation DISABLED

1. **Pressure envelope:** both absolute pressures must remain in 10–1200mbar;
   require `10 <= Pambient <= 1200` and `10 <= Pambient + DELTA_P <= 1200`,
   including uncertainty, overshoot and margin. For positive delta,
   `DELTA_P <= 1200 - Pambient` before margin. This is a sensor constraint,
   **not an authorized balloon operating limit**. Full-accuracy region is only
   450–1100mbar (p4); extended range is not the same accuracy claim. 6bar absolute
   maximum overpressure is survival, not a measurement or balloon rating.
2. **Uncertainty budget:** 0.012mbar RMS at OSR4096 is typical per-sensor noise,
   not accuracy. Independent noise RSS is about 0.017mbar, conditional on independence;
   worst-case systematic absolute errors add rather than cancel. Datasheet p4
   gives +/-1.5mbar each at 25C/700–1100mbar without autozero (pair up to +/-3mbar
   before other terms); error varies with temperature, voltage and pressure.
   Establish acceptable delta uncertainty and leak-rate stability against the
   intended threshold before using the measurement for decisions.
3. **Offset/temperature:** separate PROM coefficients and CRC4 for each device;
   second-order compensation with each sensor's own D2 temperature; zero both on
   common ambient, record offset vs temperature/pressure, warmup/reflow aging,
   thermal gradients and RF/buck-induced bias. Same part as flight does NOT make
   numerical calibration automatically transferable between physical sensors.
4. **Manometer calibration:** traceable reference, leak-tight independent internal
   tap and ambient vent, common-pressure zero, several increasing/decreasing safe
   delta points, hysteresis/repeatability and uncertainty record. No pressure value
   is authorized here. Verify blocked tube, swapped tubes, condensation, leakage,
   lag and sensor media compatibility; keep openings uncontaminated, no wet cleaning.
5. **Firmware:** dual-address detection/identity, reset/PROM timing, conversion timing
   (OSR4096 maximum 9.04ms), pairing timestamps, stale/NACK/CRC/out-of-range handling,
   no fallback from missing ambient to absolute input. Explicit differential units
   and sign through all later safety logic. Existing legacy firmware is not certified.
6. **Physical electrical/layout:** footprint acceptance above; local cap placement,
   sensor isolation from SW/RF heating, rise time/low level at chosen capacitance,
   rail startup/ripple/overshoot within 1.8–3.6V, and two real responding devices.
   All inherited supply, USB protection/inrush and thermal gates remain open.
7. **Safety release:** operator-approved numeric balloon delta limit, calibrated
   uncertainty margin, independent cutoff/fault injection, final motor design and
   full-system qualification. None is implemented or authorized by this milestone.
