# Wing export verification — NOT ORDER READY

Base: origin/master 2449ad8a, KiCad CLI/bindings 9.0.9. Source SHA256 values are in source-sha256.json. No source PCB, copper, rule or v10 tag changed.

## Verified repair

`/usr/bin/python3 tests/test_wing_order_export.py`: RED exit 1 (no front paste file), then GREEN exit 0 (six diode paste flashes and two drilled holes). Explicit layer selection alone was insufficient: native export skips disabled paste layers. Export-only pcbnew copy enables symbolic F_Paste/B_Paste; unpopulated tab and solar-tail pads are excluded from paste. No numeric layer IDs are guessed. Native export now supplies F.Paste for D1-D3. `build_wing_order.py` ran successfully and regenerated both zip files.

Runtime enabled-layer inspection mapped F.Mask to 1 and B.Mask to 3 in this installed KiCad API. These are observed runtime values, NOT portable serialization constants. Existing mask export was not repaired by hand-numbering.

Interconnect Excellon has exactly two holes, both 0.400 mm. Carrier has eight 0.300 mm vias plus three 2.200 mm mounting holes.

## Blocking/unverified items

- CPL origin repaired: JLC rows now come directly from native KiCad absolute-origin CSV (D1/D2/D3 X=14/22/30, Y=-6), matching absolute Gerber/drill coordinates. The outline height is no longer used. A native asymmetric-pad regression checks footprint datum (13.25,-7.75) despite displaced pad geometry and bogus height=999; this is not two handwritten transforms compared against each other.
- C50645 datasheet pad-1 cathode and JLC rotation correspondence were NOT verified in this bounded pass.
- Declared 0.4 mm assembly compatibility is NOT verified. Published bare-board thickness support does not prove assembly capability. Sources for next review: https://jlcpcb.com/capabilities/pcb-assembly and https://jlcpcb.com/resources/pcb-thickness (the latter says 0.4 mm only ENIG and cannot be panelized). Obtain assembly-specific capability/quote confirmation; do not change thickness silently.
- No new DRC, schematic parity, independent spatial review or human fabrication preview was performed. This is an export repair, not manufacturing sign-off.
- Existing --verify-only flag still builds; not repaired here.

## Decisions

Preserve source copper/rules; enable paste and remove non-fitted paste only in a temporary native KiCad export copy. This repairs the missing assembly artifact without inventing footprint geometry. Explicit export layer list removes unrelated courtyard/adhesive/user layers from the upload. Both regenerated zips are review candidates only, NOT approved orders.

## Scoped follow-up

Carrier exports and carrier zip restored byte-for-byte to base 2449ad8a. The previous
whole-package regeneration changed unrelated carrier artwork and export layer selection;
that delta was not justified as part of the diode paste repair and is excluded. Original
regenerated artifacts remain in commit fc2326cf. Use `--interconnect-only` for this repair.

Executed `/usr/bin/python3 tests/test_wing_order_export.py`: 2 tests PASS, exit 0.
Executed build with `--interconnect-only`: exit 0, six paste flashes covered by regression,
two 0.400 mm drills, three native placement rows. Source PCB/rules untouched.

Assembly capability checked against JLCPCB's assembly-specific table:
http://www.jlcpcb.com/capabilities/pcb-assembly-capabilities
Economic PCBA: 0.8–1.6 mm; Standard PCBA: 0.4–2.0 mm. Thus 0.4 mm is NOT economic
assembly. Standard also lists minimum 70×70 mm, edge rails and fiducials required.
**Manufacturer question / BLOCKED:** can this ~35×20 mm, 0.4 mm interconnect be
accepted for Standard assembly with a suitable support carrier/rails, given published
thin-board panel restrictions? Obtain written confirmation and an assembly quote.
No thickness or copper changes are authorized by this evidence.

C50645 datasheet and JLC cathode/rotation correspondence remain UNVERIFIED; no claim
of assembly readiness or polarity approval. No merge or purchase performed.
