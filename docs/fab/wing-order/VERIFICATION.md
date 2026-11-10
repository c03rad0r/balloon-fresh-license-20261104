# Wing export verification — NOT ORDER READY

Base: origin/master 2449ad8a, KiCad CLI/bindings 9.0.9. Source SHA256 values are in source-sha256.json. No source PCB, copper, rule or v10 tag changed.

## Verified repair

`/usr/bin/python3 tests/test_wing_order_export.py`: RED exit 1 (no front paste file), then GREEN exit 0 (six diode paste flashes and two drilled holes). Explicit layer selection alone was insufficient: native export skips disabled paste layers. Export-only pcbnew copy enables symbolic F_Paste/B_Paste; unpopulated tab and solar-tail pads are excluded from paste. No numeric layer IDs are guessed. Native export now supplies F.Paste for D1-D3. `build_wing_order.py` ran successfully and regenerated both zip files.

Runtime enabled-layer inspection mapped F.Mask to 1 and B.Mask to 3 in this installed KiCad API. These are observed runtime values, NOT portable serialization constants. Existing mask export was not repaired by hand-numbering.

Interconnect Excellon has exactly two holes, both 0.400 mm. Carrier has eight 0.300 mm vias plus three 2.200 mm mounting holes.

## Blocking/unverified items

- CPL remains unsafe: native absolute-origin positions (native-interconnect-pos.csv) are D1/D2/D3 X=14/22/30, Y=-6. Generated JLC CPL uses Y=14.1 (`GetBoardEdgesBoundingBox` height includes outline stroke). This is not a common-origin transform with the absolute-origin Gerber/drill exports. Do not upload the CPL unchanged. Repair/test the CPL generator in follow-up.
- C50645 datasheet pad-1 cathode and JLC rotation correspondence were NOT verified in this bounded pass.
- Declared 0.4 mm assembly compatibility is NOT verified. Published bare-board thickness support does not prove assembly capability. Sources for next review: https://jlcpcb.com/capabilities/pcb-assembly and https://jlcpcb.com/resources/pcb-thickness (the latter says 0.4 mm only ENIG and cannot be panelized). Obtain assembly-specific capability/quote confirmation; do not change thickness silently.
- No new DRC, schematic parity, independent spatial review or human fabrication preview was performed. This is an export repair, not manufacturing sign-off.
- Existing --verify-only flag still builds; not repaired here.

## Decisions

Preserve source copper/rules; enable paste and remove non-fitted paste only in a temporary native KiCad export copy. This repairs the missing assembly artifact without inventing footprint geometry. Explicit export layer list removes unrelated courtyard/adhesive/user layers from the upload. Both regenerated zips are review candidates only, NOT approved orders.
