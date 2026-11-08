# PR470 JLC readiness inventory — NOT ORDERABLE

## Frozen object and scope

Base/head audited: `d5ced0ade0be7157420a89dfaea5db1e2cabdfdf` (PR470, API verified OPEN and draft). Candidate SHA256 `b899ad04f1e61bd4693b52f9a5275b4a406d8dfc59b778138d598ce768b90fbd`. Input hashes are in `input-hashes.json`; inputs are in sibling `../c10-silk-acceptance-20261106/`. PR468 is not the audit target.

Read-only inventory. No copper, source, rules, source trial, or candidate changed; no new DRC/refill/full geometry build or inference reviewer call. Reused the existing native DRC and saved native-shape/per-filled-polygon graph. A cheap adjacency traversal assigns component IDs (local to this ledger, not stable identifiers across builds). Native record numbers below refer ONLY to the frozen `candidate/drc.json`, never to a later reordered DRC run. UUIDs, coordinates, descriptions and full native records are retained in `open-ledger.json`.

## Prioritized blocking disposition

1. **24 missing-copper records remain** on power/solar/enable, radio/control and SPI nets. Native opens and disjoint saved graph components agree. SPI preservation PASS means no regression; it emphatically does not mean SPI buses are complete.
2. **4 unresolved zone-anchor records**: O22 VSCAP, O36–38 GND. Multiple filled polygon components share zone UUIDs. Their printed anchor is not the physical gap; exact native-to-polygon attribution remains owed. They are not assembly waivers or proven false positives.
3. **Source acceptance outstanding**: candidate-bound schematic/netlist/registry parity and ERC are not demonstrated. Historical source mismatch is a separate issue from copper repair; reconcile intent before bulk routing.
4. **C10 design margin/return path unaccepted**: actual prior Astra CHANGES_REQUESTED remains; silk repair only closes the explicit new silk regression. No later acceptance exists in this evidence.
5. **Production gates and inherited silk**: three U_LORA1280 defects still fail the strict silk gate; production custom suite, stackup/process and assembly qualification are not candidate-bound accepted evidence. Library configuration warnings and two dangling VSCAP vias also need disposition.

**11 records are documented assembly connections**, not missing PCB copper: exact same-number/net/XY opposing outer-face socket lands, with disjoint components and a documented both-face soldered wing tab. These are conditional assembly dispositions, not a claim a bare PCB has continuity or that the mating fit/process is qualified. Spec `docs/WING-TO-HUB-SOCKET-SPEC.md:60–74,81–89` documents both faces and explicitly leaves slot supplier tolerance unverified. `socket-pads.json` records all 32 actual pad identities, types, layers and XY from the frozen PCB; `probe_socket.py` ran with KiCad 9.0.9, exit 0. Track-anchored rows O03/O05/O25 are mapped by saved component membership to the exact opposing pad pair, not by approximate coordinate alone. Distinct components prove no PCB copper already joins those faces. No blanket connector/assembly waiver is applied to O27/O29/O32/O34.

## All 39 individual records

M = missing copper; A = documented assembly connection; U = unresolved. Endpoint descriptions are verbatim from frozen native DRC. Full endpoint UUIDs/positions and component proof are in JSON.

| ID | Class | Endpoint A | Endpoint B | Exact assembly or unresolved proof |
|---|---|---|---|---|
| O01 | M | PTH pad 2 [+3V3] of J_PROG | Pad 1 [+3V3] of R_F1 on F.Cu | disjoint saved components; components [[40], [63]] |
| O02 | A | Pad 3 [/CUT_SENSE_W1] of J_W1 on F.Cu | Pad 3 [/CUT_SENSE_W1] of J_W1 on B.Cu | J_W1.3; components [[130], [131]] |
| O03 | A | Pad 3 [/CUT_SENSE_W2] of J_W2 on B.Cu | Track [/CUT_SENSE_W2] on F.Cu, length 2.3500 mm | J_W2.3; components [[17], [16]] |
| O04 | A | Pad 3 [/CUT_SENSE_W3] of J_W3 on F.Cu | Pad 3 [/CUT_SENSE_W3] of J_W3 on B.Cu | J_W3.3; components [[117], [118]] |
| O05 | A | Pad 3 [/CUT_SENSE_W4] of J_W4 on B.Cu | Track [/CUT_SENSE_W4] on F.Cu, length 0.1000 mm | J_W4.3; components [[128], [127]] |
| O06 | M | Pad 18 [/F33_IRQ] of U2 on F.Cu | Pad 17 [/F33_IRQ] of U1 on F.Cu | disjoint saved components; components [[143], [88]] |
| O07 | M | Pad 4 [/SPI2_SCK] of U1 on F.Cu | Pad 12 [/SPI2_SCK] of U2 on F.Cu | disjoint saved components; components [[79], [142]] |
| O08 | M | Track [/F33_VSENSE] on F.Cu, length 0.3000 mm | Pad 1 [/F33_VSENSE] of R_MON2 on F.Cu | disjoint saved components; components [[50], [13]] |
| O09 | M | Pad 21 [/F33_VSENSE] of U1 on F.Cu | Pad 1 [/F33_VSENSE] of R_MON2 on F.Cu | disjoint saved components; components [[92], [13]] |
| O10 | M | Pad 2 [/HUB_PV_MID1] of D_HUB1 on F.Cu | Pad 1 [/HUB_PV_MID1] of D_HUB2 on F.Cu | disjoint saved components; components [[134], [110]] |
| O11 | M | PTH pad 2 [/HUB_PV_MID1] of J_HUB_PV | Pad 2 [/HUB_PV_MID1] of D_HUB1 on F.Cu | disjoint saved components; components [[54], [134]] |
| O12 | M | Pad 3 [/HUB_PV_N] of U_HUB_CVT on F.Cu | PTH pad 4 [/HUB_PV_N] of J_HUB_PV | disjoint saved components; components [[21], [56]] |
| O13 | M | Pad 1 [/HUB_PV_P] of D_HUB1 on F.Cu | Pad 1 [/HUB_PV_P] of U_HUB_CVT on F.Cu | disjoint saved components; components [[133], [20]] |
| O14 | M | Pad 1 [/HUB_PV_P] of U_HUB_CVT on F.Cu | PTH pad 1 [/HUB_PV_P] of J_HUB_PV | disjoint saved components; components [[20], [53]] |
| O15 | M | Pad 3 [/SPI1_MISO] of U3 on B.Cu | Track [/SPI1_MISO] on F.Cu, length 12.0000 mm | disjoint saved components; components [[164], [66]] |
| O16 | M | Track [/SPI1_MISO] on F.Cu, length 40.2000 mm | Pad 3 [/SPI1_MISO] of U_C on B.Cu | disjoint saved components; components [[66], [144]] |
| O17 | M | Pad 4 [/SPI1_MOSI] of U3 on B.Cu | Track [/SPI1_MOSI] on B.Cu, length 0.5000 mm | disjoint saved components; components [[165], [67]] |
| O18 | M | Pad 4 [/SPI1_MOSI] of U_C on B.Cu | Pad 4 [/SPI1_MOSI] of U3 on B.Cu | disjoint saved components; components [[145], [165]] |
| O19 | M | Pad 5 [/SPI1_SCK] of U3 on B.Cu | Track [/SPI1_SCK] on F.Cu, length 1.0500 mm | disjoint saved components; components [[166], [68]] |
| O20 | M | Pad 5 [/SPI1_SCK] of U_C on B.Cu | Pad 5 [/SPI1_SCK] of U3 on B.Cu | disjoint saved components; components [[146], [166]] |
| O21 | M | Pad 19 [/U3_IRQ] of U1 on F.Cu | Pad 15 [/U3_IRQ] of U3 on B.Cu | disjoint saved components; components [[90], [169]] |
| O22 | U | Zone 'VSCAP_BCu' [/VSCAP] on B.Cu, priority 0 | Zone 'VSCAP_BCu' [/VSCAP] on B.Cu, priority 0 | zone UUID maps to multiple polygons; components [[51, 61], [51, 61]] |
| O23 | M | Via [/VSCAP] on F.Cu - B.Cu | Pad 1 [/VSCAP] of R_BAL1 on F.Cu | disjoint saved components; components [[61], [135]] |
| O24 | A | Pad 4 [/W1_SOLAR_N] of J_W1 on B.Cu | Pad 4 [/W1_SOLAR_N] of J_W1 on F.Cu | J_W1.4; components [[15], [132]] |
| O25 | A | Track [/W1_SOLAR_N] on B.Cu, length 1.3509 mm | Pad 1 [/W1_SOLAR_N] of J_W2 on F.Cu | J_W2.1; components [[15], [14]] |
| O26 | A | Pad 1 [/W1_SOLAR_P] of J_W1 on F.Cu | Pad 1 [/W1_SOLAR_P] of J_W1 on B.Cu | J_W1.1; components [[52], [129]] |
| O27 | M | Pad 2 [/W2_SOLAR_N] of D_BP2 on B.Cu | Pad 4 [/W2_SOLAR_N] of J_W2 on B.Cu | disjoint saved components; components [[160], [19]] |
| O28 | A | Pad 4 [/W2_SOLAR_N] of J_W2 on F.Cu | Pad 4 [/W2_SOLAR_N] of J_W2 on B.Cu | J_W2.4; components [[18], [19]] |
| O29 | M | Pad 4 [/W2_SOLAR_N] of J_W2 on B.Cu | Track [/W2_SOLAR_N] on B.Cu, length 0.8485 mm | disjoint saved components; components [[19], [116]] |
| O30 | A | Pad 1 [/W2_SOLAR_N] of J_W3 on B.Cu | Pad 1 [/W2_SOLAR_N] of J_W3 on F.Cu | J_W3.1; components [[116], [115]] |
| O31 | A | Pad 1 [/W3_SOLAR_N] of J_W4 on F.Cu | Pad 1 [/W3_SOLAR_N] of J_W4 on B.Cu | J_W4.1; components [[125], [126]] |
| O32 | M | Pad 1 [/W3_SOLAR_N] of J_W4 on B.Cu | Pad 1 [/W3_SOLAR_N] of D_BP4 on B.Cu | disjoint saved components; components [[126], [175]] |
| O33 | A | Pad 4 [/W3_SOLAR_N] of J_W3 on B.Cu | Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu | J_W3.4; components [[120], [119]] |
| O34 | M | Track [/W3_SOLAR_N] on B.Cu, length 0.2121 mm | Pad 1 [/W3_SOLAR_N] of J_W4 on B.Cu | disjoint saved components; components [[120], [126]] |
| O35 | M | Pad 2 [GND] of D_BP4 on B.Cu | Track [GND] on F.Cu, length 2.0403 mm | disjoint saved components; components [[176], [8]] |
| O36 | U | Zone 'GND_FCu' [GND] on F.Cu, priority 0 | Zone 'GND_In1' [GND] on In1.Cu, priority 0 | zone UUID maps to multiple polygons; components [[2, 8, 103], [8]] |
| O37 | U | Zone 'GND_BCu' [GND] on B.Cu, priority 0 | Zone 'GND_In1' [GND] on In1.Cu, priority 0 | zone UUID maps to multiple polygons; components [[8, 156], [8]] |
| O38 | U | Zone 'GND_In1' [GND] on In1.Cu, priority 0 | Zone 'GND_FCu' [GND] on F.Cu, priority 0 | zone UUID maps to multiple polygons; components [[8], [2, 8, 103]] |
| O39 | M | Pad 3 [/EN] of U1 on F.Cu | PTH pad 3 [/EN] of J_PROG | disjoint saved components; components [[78], [108]] |

## Actionable net groups (individual records retained above)

- **+3V3**: O01:missing copper.
- **/CUT_SENSE_W1**: O02:documented assembly connection.
- **/CUT_SENSE_W2**: O03:documented assembly connection.
- **/CUT_SENSE_W3**: O04:documented assembly connection.
- **/CUT_SENSE_W4**: O05:documented assembly connection.
- **/F33_IRQ**: O06:missing copper.
- **/SPI2_SCK**: O07:missing copper.
- **/F33_VSENSE**: O08:missing copper; O09:missing copper.
- **/HUB_PV_MID1**: O10:missing copper; O11:missing copper.
- **/HUB_PV_N**: O12:missing copper.
- **/HUB_PV_P**: O13:missing copper; O14:missing copper.
- **/SPI1_MISO**: O15:missing copper; O16:missing copper.
- **/SPI1_MOSI**: O17:missing copper; O18:missing copper.
- **/SPI1_SCK**: O19:missing copper; O20:missing copper.
- **/U3_IRQ**: O21:missing copper.
- **/VSCAP**: O22:unresolved; O23:missing copper.
- **/W1_SOLAR_N**: O24:documented assembly connection; O25:documented assembly connection.
- **/W1_SOLAR_P**: O26:documented assembly connection.
- **/W2_SOLAR_N**: O27:missing copper; O28:documented assembly connection; O29:missing copper; O30:documented assembly connection.
- **/W3_SOLAR_N**: O31:documented assembly connection; O32:missing copper; O33:documented assembly connection; O34:missing copper.
- **GND**: O35:missing copper; O36:unresolved; O37:unresolved; O38:unresolved.
- **/EN**: O39:missing copper.

## Actual Astra review recovered, not a new review

`../c10-silk-acceptance-20261106/prior-astra-review.md:3,19–35` records served model **gpt-6-astra**, actual verdict **CHANGES_REQUESTED**. Review concerns: crowded GND via annulus near SPI bend/U1 copper; refill continuity does not establish healthy neck cross-section; no minimum neck-width/return-path/decoupling impedance proof; layer-local graphics are not vertical interconnections. Its copper-only image could not qualify mask, bodies/courtyards, drill or fabrication tolerance.

The review called 0.208206 mm a predicted gap; the later acceptance report records unchanged measured minimum **0.208206115 mm**, giving **8.206115 µm** above the configured **0.20 mm** clearance rule (`../c10-silk-acceptance-20261106/REPORT.md:25`). Arithmetic headroom is not a process tolerance or a failure prediction. Native nominal clearance passes, but design robustness remains unaccepted. Neither this review nor that arithmetic establishes JLCPCB's capability for the chosen stackup, copper weight, etch/mask registration or assembled geometry. No invented safety factor, minimum neck width, etch allowance or tolerance threshold is adopted. Require actual fabrication construction/capability evidence separately from design return-path and decoupling analysis. The 0.22 mm reference move removes only the review's silk regression; it does not answer its copper concerns.

## Outstanding gate inventory and traps

All checker paths below are under `tracker/hardware/` unless specified. NOT RUN here means not newly run in this bounded inventory, not pass.

| Gate | Evidence/status and next bound check |
|---|---|
| Native as-is DRC | Reused exit 5; 39 opens, 24 warnings. Do not use rerouting `fab_grade` as grading this candidate. |
| C10/retained graph | Reused verification: 1,834 retained nonpolygon layer nodes, complete retained node/edge identity; C10.1 reaches U1.2 and C10.2 U7.2. Not entire-board connectivity acceptance. |
| `check_schematic_parity.py --board … --sch … --reg …` | Candidate-bound evidence missing. G1–G6 cover schematic existence/ERC/net sets/node sets/registry/tools. Default v10 canonical path is NOT candidate. ERC implementation allows 7 label_dangling + 2 power_pin_not_driven + 2 pin_not_driven, so G2 PASS is not zero ERC errors (lines 122–140,153–202). |
| `run_erc.sh --board … --sch …` | Candidate-bound evidence missing. Default v9 paths are wrong target; explicit source required. Exit 0 clean / 1 problems / 2 could not run. Empty `schematic_parity` array in DRC JSON is not a parity run. |
| Registry/source reconciliation | Historical `docs/analysis/flight-readiness-20261102/FINDINGS.md:7–46` targets hash 732bfe889…, not this board: ERC 11 errors, parity 7 failures, registry DRIFT4/MISSING52, five schematic-only antenna nets, U_E28 vs U_LORA1280 causing six node disagreements. Revalidate/reconcile, never relabel old counts as fresh candidate results. |
| `check_drc.py` | Default ignores opens and allows silk. Counterintuitive `--allow-unconnected` enforces opens; `--no-exit-code` forces success. Default green would not close this inventory (lines 43–76,108–149). |
| `check_silk.py` | Reused exit 1, strict no allowance, three defects below. 0 pass / 1 violation / 2 could not run. |
| Custom route suite | Candidate-bound runs owed: `check_lane_clearance.py`, `check_lane_integrity.py`, `check_copper_under_body.py`, `check_lane_isolation.py`, `check_hole_clearance.py`, registry, same-layer crossings and socket-edge. `AGENTS.md:600–620,659–666`; `tests/test_routing_method_binding.py:33–35`. Inspect each CLI before explicit candidate binding; preserve thresholds. |
| Commit-hook coverage | `scripts/git-hooks/pre-commit-board-gates.py:179–197` lists DRC/parity/socket-edge/silk only; not complete custom coverage. Socket gate rejects tracks within 0.50 mm of/across wing cavities. Docs-only commit success is not PCB approval. |
| Older 12/12 claim | `docs/fab/v10/ROUTING-CAPACITY-FINDING.md:1–15` concerns Oct22 753-track/22-via board, not this candidate. Cannot inherit green. |
| Manufacturing/assembly | Actual candidate stackup/drill/via construction/mask/assembly evidence and output parity remain unaccepted; do not confuse nominal design rule with JLC process qualification or request order/signoff yet. |

### Three inherited U_LORA1280 defects

All are `silk_over_copper`, “Silkscreen clipped by solder mask”; native warning but strict custom gate failure. Evidence `../c10-silk-acceptance-20261106/candidate/silk.json:912–955`:

- F.Silkscreen segment at **(45.0,76.1)**, UUID `1faf3492-15b9-4f0b-9396-c5d97f87f506`.
- F.Silkscreen segment at **(61.0,60.1)**, UUID `e97516be-ca8a-4061-819e-9b66ff243826`.
- Reference `U_LORA1280` at **(53.0,58.3)**, UUID `a9d40fa2-004f-4e15-93bb-ff812bf97689`.

Moving the reference alone cannot fix two footprint graphic segments. No waiver applied.

## Next bounded repair (proposal, not performed)

First bind and reconcile source/netlist intent for this frozen board. Then isolate **O35: D_BP4.2 GND on B.Cu versus F.Cu GND track at (29,6)** as a single missing interlayer-connection repair candidate. Exact native UUIDs and disconnected components 176/8 are in the ledger. Unlike opposing socket lands this is a diode SMD pad, not a documented assembly bridge. Measure B.Cu pad extent, legal via sites, drill/clearance and return connection before choosing a through-via/stub; no unmeasured via coordinate is prescribed. Work on a new copy, preserve all existing routes, refill and compare native DRC signatures and saved connectivity partition for no regressions; reject if local geometry cannot meet unchanged rules. Do not touch the C10 clearance neighborhood as a side effect. Independently localize the four zone records by polygon/component before any zone repair. Production acceptance still requires remaining net groups, source/custom gates and margin/assembly qualification; closing O35 alone is not readiness.

No merge, order, reroute, or source adoption authorized/performed by this inventory.
