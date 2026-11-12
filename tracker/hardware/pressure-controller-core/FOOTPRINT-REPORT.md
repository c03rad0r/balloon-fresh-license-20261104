# MS5611 recommended-land repair — not board/fab release

## Source and independent orientation check

TE / Measurement Specialties MS5611-01BA03 datasheet, 06/2017,
[AMSYS manufacturer-document mirror](https://amsys-sensor.com/downloads/data/MS5611-01BA03-AMSYS-datasheet.pdf).
Downloaded and inspected actual rendered PDF pp15–17; SHA256
`1fac201505813c97e0b9dff4d562a416b1ab67bb203dab138559f5e6234700b7`.

- p16 recommended PCB lands: exactly eight **1.1 x 0.6 mm rectangles**, **2.2 mm column-centre spacing**, **1.25 mm row pitch**.
- p15 cap/top illustration establishes numbering: **1–4 down left, 8–5 down right**. The adjacent contact/underside illustration is mirrored. p16 alone is unnumbered. The shipping-tape inset is not the PCB orientation oracle.
- Origin at body centre, KiCad Y down: left x=-1.1, right x=+1.1; rows y=-1.875,-0.625,+0.625,+1.875 mm.
- p15 body 3 x 5 mm, general tolerance +/-0.05 mm. Two cap holes diameter 0.50 at (+0.65,-1.65),(-0.65,+1.65). These are **F.Fab graphics, not PCB holes**, and do not grant a pneumatic seal/interface design.

## DECISIONS

Replace stock lands (0.95 x 0.55, centres 2.15 mm) with project-local
`PressureSensor:MS5611-01BA03_TE_Recommended`, not another stock alias.
Source contact dimensions 0.90 x 0.50 on p15 are NOT the recommended lands.
Pin1 has a chamfered Fab corner and visible silk triangle; every copper pad remains rectangular.

Courtyard is **project policy**, not a dimension claimed from TE: 0.25 mm beyond
max body/copper envelope, rounded outward to 0.05 mm gives +/-1.90 x +/-2.80 mm.
Nominal body/Fab outline and dimensioned cap ports preserve mechanical visibility.

p16 forbids tracks between pads. The implemented **F.Cu rule area is the inter-pad
strip only: local x -0.55..+0.55, y -2.50..+2.50 (1.10 mm wide)**, i.e. exactly the gap
between the land columns (left lands span x -1.65..-0.55, right lands +0.55..+1.65), so it
does not extend over the pads. It prohibits tracks, vias and pours and allows
pads/footprints. This is now **aligned to the quoted TE wording** ("Please do not route
tracks between pads", p16): the prohibition covers the space between pads and nothing more.

Blocking **vias and pours** as well as tracks is **project policy, not quoted TE wording**:
a via in the gap is a track passing through it in the third dimension, and a pour there
would re-create the copper the reserved area exists to keep out. Pads and footprints are
allowed because TE's constraint is about routing, and forbidding them would make the
footprint unable to host its own lands. Lands extend outside the body so outward escape
remains possible; measured escape band at a pad centre is now **975 um** per side for a
0.25 mm track (land outer edge 1.650 - rule edge 0.550 - 0.125 mm end-cap), against 25 um
when the rule area still covered the body.

**Historical note (corrected over-reach).** The first qualification of this footprint put a
"conservative F.Cu rule area over the nominal 3 x 5 body" here, with the intent of encoding
the same TE sentence. That was wider than the cited constraint: all eight pad centres sat
inside it, so every centre-anchored escape was an `items_not_allowed` DRC record and the only
legal anchor band was 0.150 mm of land overhang minus a 0.125 mm track end-cap = 25 um. The
over-reach was measured and drawn before it was changed
([sensor-port-keepout-conflict.png](sensor-port-keepout-conflict.png), commit `5e628f86`),
the narrowing was chosen by the operator (option A of three drawn), and the result is drawn
against the old shape in [sensor-port-keepout-strip.png](sensor-port-keepout-strip.png).
The body-wide shape is now a **negative control** in `test_keepout_strip.py`: it must be
REJECTED, so the fix cannot silently regress.

No invented all-layer or pneumatic clearance dimension; final placement/escape remains a
layout task.

F.Cu/F.Mask/F.Paste pad layers provided. Manufacturer does not specify mask
expansion, paste reduction, stencil thickness or courtyard. Project defaults are
zero expansion/reduction (1:1 aperture), **provisional assembly-process choices**;
verify_footprint.py measures effective native coupon mask/paste margins for all
pads, rather than assuming local zero overrides board settings. Assembly house
must approve final mask/stencil/reflow and inspect all eight joints. No IPC land
pattern compliance claim or invented MSL/floor-life/bake schedule.

Independent source consultation and named spatial consultation performed before
implementation; **served model gpt-6-astra** confirmed dimensions/handedness and
requested reservation, polarity marks, effective-aperture verification, all addressed.
See footprint-evidence/source-consult.txt. This is not full-board approval.

## Handling / IPC applicability

Datasheet p17: solder **all eight contacts**, including I2C-unused SDO; protect
openings against particles; use no-clean paste, cleaning may damage sensor;
ground machinery/personnel and use antistatic transport. Place 100 nF close to VDD.
p2 maximum soldering temperature is 250 C for maximum 40 seconds, not a generic
260 C profile authorization.

p17 explicitly refers to [AN808](https://www.amsys-sensor.com/downloads/notes/Soldering-sensors-in-regard-to-the-RoHS-directive-AMSYS-an808e.pdf),
download SHA256 `b665fe826a2463d4e22e50c6fd5f9ffc01c50c84adc660c140569be4a61cf1e6`.
AN808 bases profiles on **IPC/JEDEC J-STD-020B**, requires application-specific
profile evaluation, recommends forced convection and discourages hand soldering.
It calls for at least 48 h at room temperature after last soldering before best
calibration. This legacy application note is not a declaration of compliance with
current IPC revisions: assembler must reconcile actual lot/product limits and
paste/process; do not blindly substitute a hotter generic lead-free profile.

## Actual verification

Based on live master **57d654ff**; open PR list had no competing footprint repair
(#539/#540 firmware deliberately untouched). Read MEASUREMENT-REPORT and pinned
stock library provenance before replacement.

- KiCad 9.0.9 native footprint load succeeds.
- test_footprint.py rejects old size, old centre spacing, mirror, 180-degree pin1,
  extra/missing pad, PCB drill, and actual installed deficient stock footprint.
- Native schematic export and ERC: **zero violations**; core, supply,
  measurement, and measurement negative-control tests pass.
- verify_footprint.py compares all **125 exported net endpoints** against pinned
  base: unchanged; U3/U4 export points to the new local library.
- Isolated **no-net coupon** native reload and DRC: zero violations/unconnected.
  This exercises library linkage, native geometry and courtyard, NOT routing.
  The coupon carries the narrowed keep-out (measured at the coupon origin 10,10:
  strip x 9.45..10.55), so the regenerated evidence is evidence of the CURRENT
  shape, not the pre-fix one.
- Native SVG plus raster render: [coupon.png](footprint-evidence/coupon.png).
  Render includes overlaid Fab port circles (not drills), copper, courtyard,
  silk; purple plot-origin graphics are not copper tracks. Features inspected
  visible/uncropped. No numbered pads in native plot: numbering is tested natively.
  **Limit, measured:** KiCad's SVG plotter does not draw rule-area zones, so this
  render CANNOT show the keep-out. It is cited for pad/courtyard/port geometry only.
  The keep-out shape is drawn instead by `draw_keepout_strip.py`, which reads the
  zone from the footprint with `pcbnew` and prints the measured box:
  [sensor-port-keepout-strip.png](sensor-port-keepout-strip.png).
- `test_keepout_strip.py` pins the keep-out itself: the strip edges, that
  tracks/vias/pours stay forbidden, that every pad CENTRE lies outside it, that a
  pad-centre escape is DRC-clean AND electrically connected, that a track BETWEEN
  the pads is still REFUSED (the TE constraint), and two negative controls
  (the body-wide shape and an over-narrow strip must both be rejected).
- [proof.json](footprint-evidence/proof.json) binds exact footprint, schematic,
  XML, coupon and render hashes. Coupon UUIDs may vary on rebuild.

Reproduce from this directory:
```sh
python3 generate.py
kicad-cli sch export netlist --format kicadxml -o core.xml core.kicad_sch
kicad-cli sch erc --format json --exit-code-violations -o erc.json core.kicad_sch
python3 test_core.py && python3 test_supply.py
python3 test_measurement.py && python3 test_measurement_negative.py
/usr/bin/python3 test_footprint.py
/usr/bin/python3 -O test_footprint.py
/usr/bin/python3 verify_footprint.py
/usr/bin/python3 test_keepout_strip.py
~/venvs/kicad/bin/python draw_keepout_strip.py   # needs matplotlib AND pcbnew
```
Requires distro pcbnew, KiCad CLI and rsvg-convert. Matching core.kicad_pro is
necessary for KiCad to load project-local fp-lib-table during ERC.

## Remaining gates

The **documented copper-land mismatch is repaired**; this does not qualify a PCB,
assembly process or pressure system. Thermal isolation from buck/RF, physical cap
port access/contamination protection, tubing/sealing, local bypass placement,
pressure uncertainty/calibration, supply and safety gates remain OPEN. No full PCB
routing, flash, pump actuation or purchases were performed. Firmware consolidation
is separate. This report supersedes only the retained-stock-footprint decision in
MEASUREMENT-REPORT.md, not its other qualification constraints.
