# ADR index — canonical number → filename map

**This file is GENERATED.** Do not hand-edit it: run
`python3 scripts/gen_adr_index.py` after adding or removing an ADR.

## The numbering rule (binding)

- A new ADR takes its number from `scripts/adr_next_number.py`, which
  prints the next free number at or above **044** and exits
  non-zero if its target path already exists. Do not pick a number by hand.
- **044 and above are reserved for sequential allocation.**
  Numbers 001–043 are historical.
- **Do not rename or renumber an existing ADR file again.** References to them exist
  outside `docs/adr/` (code, coordination docs, branch names, external links)
  and a rename silently breaks them. The one authorised exception was the
  **2026-10-07 duplicate-number fix** (branch `adr/renumber-collisions`): where two
  or more files shared a number, the live record kept it and the displaced
  historical records moved into the **100 range**, which is outside the sequential
  allocation band so it can never race it. That displacement is done; treat the
  100-range numbers as permanent. Any *new* collision is a defect to report,
  never to fix by another rename.
- Where a collision cannot be resolved from evidence (a file's own Status
  header, or a supersede pointer inside a committed record), this index says
  `UNRESOLVED - needs an operator decision`. It never guesses.

Generated from `docs/adr/`: **136** distinct
numbers, **136** numbered files, **1** non-conforming filenames.

## Collisions

None.

## Number → files

| # | file | title | own Status |
|---|---|---|---|
| 001 | `001-esp32-c3-as-mcu.md` | ESP32-C3 als Mikrocontroller | Akzeptiert |
| 002 | `002-lr2021-as-rf-chip.md` | Semtech LR2021 als LoRa-Transceiver (Gen 4) | Akzeptiert |
| 003 | `003-dual-track-hardware.md` | Dual-Track Hardware-Design (Dev + Flight) | Akzeptiert |
| 004 | `004-3d-yagi-antenna-structure.md` | 3D Yagi-Antennen-Struktur (4 Wings + Hub) | Akzeptiert |
| 005 | `005-sky66112-fem.md` | SKY66112-11 als Front-End-Module (PA + LNA) | Akzeptiert |
| 006 | `006-supercapacitor-power.md` | Supercapacitor-Stromversorgung (Solar + Supercaps) | Akzeptiert |
| 007 | `007-adaptive-protocol.md` | Adaptive Protokoll-Strategie (LoRa/FLRC/Sub-GHz) | Akzeptiert |
| 008 | `008-telemetry-protocol.md` | Telemetrie-Paketformat | Akzeptiert |
| 009 | `009-antenna-strategy-v1-v2.md` | V1 Omnidirectional Antennas with V2 Directional Upgrade Path | Accepted |
| 010 | `010-adaptive-tx-power.md` | Adaptive TX Power and Modulation per TDMA Slot | Accepted |
| 011 | `011-first-flight-strategy.md` | First Flight Strategy — Single Balloon, Helium, Minimal Variant | Accepted |
| 012 | `012-mesh-networking-strategy.md` | Mesh Networking Strategy — FIPS + MeshCore + TollGate + Nostr | Accepted |
| 013 | `013-cluster-aware-stratorelay.md` | Cluster-Aware Stratorelay for MeshCore | Proposed |
| 014 | `014-bent-pipe-fpga-bridging.md` | Bent-Pipe FPGA/RP2040 Bridging for Multi-Balloon Mesh | Proposed |
| 015 | `015-three-board-hardware-strategy.md` | Three-Board Hardware Strategy | Proposed |
| 016 | `016-fips-implementation-keep-cpp-microfips.md` | FIPS Implementation — Keep C++ microfips | Accepted |
| 017 | `017-phase-sync-via-reference-clocks.md` | Phase Synchronization via Independent Reference Clocks | Accepted |
| 018 | `018-multi-mode-range-characterization.md` | Multi-Mode Range Characterization Protocol | Accepted |
| 019 | `019-gps-synchronized-mode-switching.md` | GPS-Synchronized Time-Division Mode Switching | Accepted |
| 020 | `020-deprecate-radiolib-adopt-raw-lr2021-spi.md` | Deprecate RadioLib LR2021 Driver — Adopt Raw 2-Byte Opcode Protocol | Accepted |
| 021 | `021-absolute-utc-phase-sync.md` | Absolute UTC Phase Synchronization — No Boot-Time GPS Gate | Accepted |
| 022 | `022-mandatory-test-coverage.md` | Mandatory Full Test Coverage for Walk Test Firmware | Accepted |
| 023 | `023-tx-autonomy-and-mode-sync.md` | TX Full Autonomy and TX/RX Mode Synchronization | Accepted |
| 024 | `024-extract-only-source-repository-policy.md` | Extract-Only Source Repository Policy | ACCEPTED |
| 025 | `025-shared-hardware-flock-mutex.md` | Shared Hardware Access — Mandatory flock Mutex for ESP32-C3 + LR2021 | ACCEPTED |
| 026 | `026-dual-mcu-radio-architecture.md` | Dual MCU Radio Architecture — RP2040 Radio Processor + ESP32-C3 Application | ACCEPTED |
| 027 | `027-blossom-on-ip-layer.md` | Blossom Server Stacks on IP Layer — Not Raw Mesh Datagram | ACCEPTED |
| 028 | `028-schematic-first-three-variants.md` | Schematic-First PCB Design with Three MCU Variants | Proposed |
| 029 | `029-dual-band-flight-board.md` | v9 tri-band flight board (ESP32-S3-WROOM-1U + LoRa2021F33-2G4 + SX1280 + MAX-M10S) | Proposed |
| 030 | `030-deterministic-zero-inference-pcb-pipeline.md` | Deterministic, zero-inference PCB placement and routing | Proposed |
| 031 | `031-board-bring-up-isolation-and-staged-population.md` | Board bring-up isolation, testability, and staged population | Accepted |
| 032 | `032-simulation-evidence-ltspice-openems.md` | Simulation evidence for PCB design (LTspice + openEMS + stackup impedance) | Accepted |
| 033 | `033-giftwrap-single-construction-path.md` | Gift-wrap construction has one canonical primitive | Proposed |
| 034 | `034-radio-band-split-433-tx-2g4-rx.md` | v9 radio band split: 433 MHz TX / 2.4 GHz RX on two separate chips | Proposed |
| 035 | `035-tdm-radio-schedule.md` | TDM radio schedule: dedicated ranging windows, one transmitter at a time | Proposed |
| 036 | `036-energy-policy-burst-storage-daylight-only-tx.md` | Energy policy: burst-sized storage, daylight-only TX | Proposed |
| 037 | `037-mcu-s3-no-fem.md` | v9 MCU = ESP32-S3; SKY66112 front-end module omitted from v9 | Proposed |
| 038 | `038-wifi-bt-disabled.md` | v9 ESP32-S3: Wi-Fi/BT is never enabled, external antenna path left unpopulated | Proposed |
| 039 | `039-licence-exempt-433-design-point.md` | Licence-Exempt 433 MHz Design Point | Proposed |
| 040 | `040-v9-radio-site-optionality.md` | v9 dual radio-site optionality: one LP-or-HP variant site plus one LP-only site | Proposed |
| 041 | `041-rf-frontend-licence-exempt.md` | v9 RF front end under the ≤ 10 mW licence-exempt regime: gain on the ground, F33 internal LNA in circuit, no balloon FEM | Proposed |
| 042 | `042-thermal-drift-strategy.md` | Thermal / frequency-drift strategy for the balloon radio | Proposed |
| 043 | `043-cold-qualification-heating.md` | Cold Qualification — Heating Rejected, Below-Rated Parts Gated | Accepted |
| 044 | `044-v9-power-rails.md` | v9 power rails: the F33 5 V rail (resolves ADR-029 item O5) | Proposed |
| 045 | `045-antenna-solder-access.md` | Antenna solder-access constraint (hand-soldered RF parts must be reachable from outside the module body) | Proposed. The *decision* this ADR records is the operator's standing |
| 046 | `046-wing-board-interface.md` | Wing-board interface: tab/socket geometry, 4-wire pinout, wing outline, order shape | Proposed |
| 047 | `047-v9-power-provisioning.md` | v9 F33 power provisioning: over-provisioning the 5 V PA rail for the module's maximum draw | Proposed |
| 048 | `048-v9-hub-wing-interfaces.md` | v9 hub-side wing interfaces: four socket land sets at 90° | Proposed |
| 049 | `049-wing-architecture.md` | Wing architecture: cell class, structure, orientation and protection | Proposed |
| 050 | `050-mppt-charge-path.md` | Charge-path converter between the solar array and the supercap bank | Proposed |
| 051 | `051-hub-array-and-cut-topology.md` | Hub-mounted solar array as an INDEPENDENT string: the wing cut topology and the cut-sense provision | Proposed |
| 052 | `052-cell-mounting-end-only.md` | Bare cells are mounted END-ONLY: no adhesive bond, no bonded-and-vented carrier | Proposed |
| 053 | `053-per-cell-bypass-diodes.md` | Per-cell / per-group bypass Schottky diodes: a cracked or shaded cell costs one cell, not the whole series string | Proposed |
| 054 | `054-array-topology-final.md` | Array topology, final: the 12-cell series string is RETAINED, the hub-side per-interface bypass diode is MANDATORY, per-cell bypass is REJECTED, and the bypass-diode mechanism is CORRECTED | Proposed |
| 055 | `055-hub-geometry-final.md` | Hub geometry, final: the array plane is HORIZONTAL (flat, no tilt, zero ripple), the area is a DUTY CHOICE, the board is 0.4 mm, the hub is ≈103 mm square, and the cells go on the UPPER face under a raised attachment standoff | Proposed |
| 056 | `056-thermal-and-frequency-drift.md` | Thermal and frequency drift: no oscillator heater, TCXO where a radio needs one, and GPS 1PPS discipline as the zero-mass/zero-watt provision | Proposed |
| 057 | `057-flrc-drift-strategy.md` | FLRC drift strategy: FLRC's offset tolerance is band-independent in Hz, so the 2.4 GHz uplink is the exposure, the degradation ladder must not slow the FLRC rate, and the ranked mitigations | Proposed |
| 058 | `058-onboard-temp-compensation.md` | On-board temperature-sensor-based drift compensation: the LR2021's XOSC-adjacent sensor as the primary instrument, a per-unit calibration curve, GPS 1PPS verification, and an MS5611 cross-check | Proposed |
| 059 | `059-ntc-temp-compensation-provision.md` | LR2021 on-chip NTC temperature compensation: the provision, the TCXO-vs-NTC mutual exclusion, the thermal-coupling siting rule, and the module pin-breakout blocker | Proposed |
| 060 | `060-sx1280-drift-strategy.md` | SX1280 drift strategy: the retained 2.4 GHz ranging radio, whether its ranging role needs drift control at all, and the ranked provisions | Proposed |
| 061 | `061-onboard-storage.md` | On-board storage: the module's own 8 MB flash is sufficient; no external storage part is fitted; the TX buffer is sized to the link, not to the flash | Proposed |
| 062 | `062-variant-b-design-basis.md` | Variant B design basis: a separate, under-20 g vehicle with its own mass, energy, array and outline | Proposed |
| 063 | `063-decouple-board-area-from-array-overhang.md` | Hub board area and array area are DECOUPLED: panels may overhang, the outline follows the components, and the array rides a separate carrier | Proposed |
| 064 | `064-hub-outline-trim.md` | Hub outline trim: 103 × 103 mm → 102 × 102 mm, to cross the JLCPCB size-tier boundary | Proposed |
| 065 | `065-wing-skeletonised-double-sided.md` | Wing board: skeletonised frame carrier + double-sided cells | Accepted |
| 066 | `066-conservative-hub-unfreeze.md` | Conservative hub baseline: unfreeze board work without claiming an unmeasured cell allowable | Proposed — operator direction recorded 2026-10-09; this record is the interim design basis and is not an order authorization |
| 067 | `067-hub-board-ground-plane.md` | Hub board: continuous GND return on the 4-layer stack | Accepted |
| 068 | `068-hub-v9-outline-60x60.md` | The hub v9 outline is 70 × 70 mm, sized by COMPONENTS | Proposed |
| 069 | `069-mcu-s3-confirmed-and-strap-contradiction-resolved.md` | MCU: ESP32-S3-WROOM-1U is CONFIRMED, and the C3/S3 strapping contradiction is resolved | Proposed |
| 070 | `070-keep-both-lora2021-sites.md` | The v9 hub keeps BOTH LoRa2021 sites: F33 for TX, bare for RX | Proposed |
| 071 | `071-ground-station-gateway-design-basis.md` | Ground-station design basis: a full-duplex INTERNET GATEWAY through the balloon as a bent pipe | Accepted by operator |
| 072 | `072-band-split-duplex-two-antennas-no-circulator.md` | Band-split duplex at the gateway: two band antennas, and NO circulator | Accepted by operator |
| 073 | `073-433-downlink-flrc-max-lora-rejected.md` | 433 MHz downlink: FLRC at maximum throughput, and LoRa REJECTED | Accepted by operator |
| 074 | `074-two-flight-board-variants-licence-free-replication.md` | Two flight-board variants: an F33 high-power board and a low-power LR2021 board, so others can fly without a licence | Accepted by operator |
| 075 | `075-f33-cheapest-db-range-multiplier.md` | The F33 is the cheapest dB in the system (~0.40 USD/dB) and it multiplies every ground candidate's range 3.55× | Accepted by operator |
| 076 | `076-positioner-stow-on-wind-survival-policy.md` | Positioner survival policy: stow on wind, anemometer cutoff, mechanical latch | Proposed — an agent-derived engineering policy |
| 077 | `077-print-structure-buy-gearing-self-locking-worm.md` | Print the structure, buy the gearing: a self-locking worm reducer is mandatory | Accepted by operator |
| 078 | `078-right-size-antenna-cliff-and-mesh-rule.md` | Right-size the antenna: small dish / wide beam over big dish / narrow beam; the positioner-class cliff and the mesh rule | Proposed — an engineering analysis |
| 079 | `079-amplifier-led-receive-chain-owned-tqp3m9037-lna.md` | Amplifier-led receive chain using the owned TQP3M9037 LNA | Accepted by operator |
| 080 | `080-xr613-resistive-divider-bench-tool-not-array-combiner.md` | The XR-613 divider is a resistive bench tool, NOT an array combiner (resistive ⇒ 6 dB, no array gain) | Accepted by operator |
| 081 | `081-ground-station-tier-ladder-and-option-b.md` | The ground-station tier ladder, and the recommended option B (Diamond A-430S15R + DIY tracker P2, ≈ EUR 735) | Proposed — the ladder is a recommendation with measured/estimated rungs; the |
| 082 | `082-rate-adaptation-size-for-min-rate-at-max-range.md` | Rate adaptation: size the dish/antenna for the minimum useful rate at maximum range | Accepted by operator |
| 083 | `083-2g4-reflector-production-ku-offset-dish.md` | The 2.4 GHz reflector is a BOUGHT production Ku offset dish (new or used), never a hand-built one | Proposed — an engineering recommendation with sourced prices and a computed |
| 084 | `084-ground-station-automatic-level-control.md` | Automatic level control at the gateway: AGC on the 433 receive chain, telemetry-driven attenuation on the 2.4 GHz uplink | Accepted by operator |
| 085 | `085-wing-slot-placement-rule.md` | Wing-socket slot placement on a 70 × 70 mm hub: rotations derive from the footprint datum, and every slot must reach its own edge | Proposed — the *defect and the rule* are measured; the text is not |
| 086 | `086-base-station-fixed-5v-correction.md` | Base-station fixed 5 V source correction | Proposed |
| 087 | `087-pressure-rig-differential-basis.md` | Differential-pressure rig basis and separate qualification gates | ACCEPTED — operator approved 2026-11-10. Implementation and physical qualification remain incomplete |
| 088 | `088-prestretch-differential-pressure-qualification.md` | Differential-pressure basis and qualification before pump arm | ACCEPTED — explicit operator decision, 2026-11-10 |
| 100 | `100-tollgate-over-fips-mesh-udp.md` | TollGate Payment Messages Transport Over FIPS Mesh UDP | ACCEPTED |
| 101 | `101-lr2021-only-ban-sx1280.md` | REVISED — LR2021 SPI Protocol Clarification | SUPERSEDED by ADR-020 |
| 102 | `102-version-tagging-policy.md` | Version Tagging Policy — Tag on Progress Without Regressions | Accepted |
| 103 | `103-tx-autonomy-requirement.md` | TX Board Must Operate Fully Autonomously | Superseded |
| 104 | `104-tx-rx-sync-invariant.md` | TX-RX Synchronization Invariant — Same 56-Phase Sweep | Accepted |
| 105 | `105-reproducible-build-flash-test.md` | Reproducible Build, Flash, and Test via Make Targets + pytest | Accepted |
| 106 | `106-e-hash-relay-transport-layer.md` | 106-e-hash-relay-transport-layer | Proposed |
| 107 | `107-three-variant-pcb-design.md` | Three-Variant PCB Design (C3, S3, C3+RP2040) | Proposed |
| 108 | `108-f33-sx1280-pin-plan.md` | V9 D2b(b) — LoRa2021F33 + SX1280 pin plan | proposed implementation baseline, pending schematic ERC and module-datasheet |
| 109 | `109-firmware-output-harmonization.md` | Firmware Output Harmonization | APPROVED |
| 110 | `110-tollgate-over-lr2021.md` | TollGate Balloon Uses LR2021 Radio as Data Link | Proposed |
| 111 | `111-canonical-board-production-order.md` | Canonical Board-Production Order of Operations | Accepted |
| 112 | `112-placement-gate-human-and-spatial-review.md` | Placement Gate with Human + Spatial-LLM Review Before Routing | Accepted |
| 113 | `113-drc-blockers-feedback-tool.md` | DRC-to-Blockers Feedback Script as a Standard Board Tool | Accepted |
| 114 | `114-skidl-netlist-authoring.md` | SKiDL for Netlist Authoring of New Boards | Accepted |
| 115 | `115-tooling-sourcing-policy.md` | Tooling Sourcing Policy for Board Production | Accepted |
| 116 | `116-simulation-gate-ngspice.md` | Simulation Gate — ngspice Testbenches as a Blocking Pre-Order Check | Accepted |
| 117 | `117-wing-airframe-foam-selection.md` | The wing airframe is a bought XPS/Depron sheet, end-mounted, 3 mm first build | Accepted by operator |
| 118 | `118-flight-board-v10-directives.md` | Flight board v10: two-sided population, three LR2021 sites, E28-2G4M27SX ranging module, minimal outline, human placement gate, visual-first reporting | ACCEPTED — operator instruction, 2026-10-20 |
| 119 | `119-v10-radio-sites.md` | v10 radio sites: three LR2021 slots (2× LP + 1× F33) + E28-2G4M27SX ranging module | ACCEPTED — operator instruction, 2026-10-20 |
| 120 | `120-v10-placement-process.md` | v10 placement process: population sides (measured per AGENTS §1b), minimal outline, human placement gate, visual-first reporting | ACCEPTED — operator instruction, 2026-10-20; R1 precedence added 2026-11-10 |
| 121 | `121-programming-interface.md` | Programming/debug interface: 6-pin J_PROG header on every flight board | ACCEPTED — operator question and direction, 2026-10-21 |
| 122 | `122-v10-esp32-radio-bus.md` | v10 ESP32-S3 ↔ four-radio interconnect: one shared SPI bus, four CS, 29-GPIO budget | SUPERSEDED by ADR-123 |
| 123 | `123-v10-two-spi-buses.md` | v10 radio interconnect v2: TWO SPI buses, partitioned by band (bent-pipe capable) | ACCEPTED — operator instruction, 2026-10-21: *"make sure that one of the low power LR2021 is on one SPI bus and the F33 … on the other SPI bus so that we can have a real time bent pipe without being forced to do TDMA if we want to."* |
| 124 | `124-tether-holes.md` | Tether holes: four NPTH line-attachment holes on the flight hub | ACCEPTED — operator instruction, 2026-10-21: *"include holes in the board so that a string can be attached for tying it to the balloon."* |
| 125 | `125-wing-string-holes.md` | Wing string-attachment holes + deterministic hole-clearance test | ACCEPTED — operator instruction, 2026-10-21: *"Also please make holes for attaching the wing boards via a string. Please make a deterministic geometric test for ensuring that the holes don't overlap with any components or lanes in the circuit board."* |
| 126 | `126-astar-routing-mandatory.md` | Grid A* routing with via support is the ONLY permitted routing method | ACCEPTED — operator directive, 2026-10-21: *"(a) a real grid/A* router with via |
| 128 | `128-schematic-is-source-of-truth.md` | The Schematic Is The Source Of Truth — Board Derived From It, Mechanically Enforced | Accepted |
| 129 | `129-v10-power-restoration-and-bypass-diodes.md` | v10 power-management restoration, per-cell bypass diodes, and the hub panel connector | ACCEPTED — operator instruction, 2026-10-22 |
| 130 | `130-foam-wing-geometry-authority.md` | The FOAM wing is the wing of record; the wing has no PCB, and its geometry is parametric | Proposed — the design direction is worker-derivable; the operator |
| 131 | `131-wing-hub-interface-and-release.md` | Wing↔hub interface redesigned for a FOAM wing: the 4-pin row stays, the insertion feature changes, and the release is designed with it | Proposed — design direction is worker-derivable; the operator |
| 132 | `132-wing-per-cell-bypass-interconnect-board.md` | The wing carries its own interconnect board with a PER-CELL bypass diode, and that board is the wing↔hub interface | Accepted by operator |
| 133 | `133-gnd-and-rf-feed-purpose.md` | What GND and RF_FEED are actually for, and what happens to them when the wing loses its Yagi | Proposed — explanatory record; operator corrects pass 2 |
| 134 | `134-wing-tab-two-pin-dead-copper-removal.md` | The wing tab is TWO pins; GND and RF_FEED are removed as dead copper, and antennas attach to the hub by U.FL | Accepted by operator |
| 135 | `135-wing-interconnect-schematic.md` | The wing interconnect has a schematic, and forward-generation is the direction of truth for a board that has no netlist | Accepted |
| 136 | `136-flight-wing-interface-two-land-and-routing-sequence.md` | The flight wing interface is TWO lands; cut-sense is deferred DNP; routing is sequenced AFTER the interface | Accepted |
| 137 | `137-no-rf-on-hub-antenna-at-module.md` | No RF on the hub: antennas connect at the radio module, never on our PCB | Accepted |
| 138 | `138-e28-ranging-capability-unproven-flight-gate.md` | The E28-2G4M27SX's ranging capability is UNPROVEN; the flight is gated on it | Accepted — this is a gate, not a part change. The part decision stays open until |
| 139 | `139-v10-2g4-site-non-pa-sx1280-recommendation.md` | v10's 2.4 GHz site should be a NON-PA SX1280 module; the 27 dBm class is where ranging dies | Accepted — operator decision 2026-10-26. Part: `LoRa1280` |
| 140 | `140-placement-approval-requires-route-trial.md` | Placement is approved on legality, never on routability; that is the defect | Accepted — process change, effective immediately |
| 141 | `141-drill-minimum-020-fab-limit.md` | Drill minimum is 0.20 mm, set by the fab, not by us | Accepted |
| 142 | `142-wing-socket-edge-exemption-does-not-extend-to-tracks.md` | The wing-socket edge exemption does NOT extend to tracks, and must not | ACCEPTED — operator decision 2026-11-03 |
| 143 | `143-hv-lane-discipline-by-stack-position.md` | H/V lane discipline: direction assigned by STACK POSITION, never by layer ID | ACCEPTED — operator decision 2026-11-07: *"Don't make it a blocking gate for this |
| 144 | `144-two-face-lands-and-gnd-anchors-excluded.md` | Two-face wing lands and GND zone anchors are excluded from the unconnected count | ACCEPTED — operator decision 2026-11-08: *"sounds good, lets go with these |
| 145 | `145-v11-gpio-economy.md` | v11 GPIO economy: three pin-saving measures, deferred from v10 | PROPOSED for v11. Not applied to v10. Operator directive 2026-11-09: *"put all |
| 146 | `146-v11-wing-bypass-diodes-to-top.md` | v11: move the four wing bypass diodes `D_BP1..D_BP4` to the top side | PROPOSED for v11. Not applied to v10. Operator directive 2026-11-09: *"lets move the |
| 147 | `147-no-merge-pressure-rig-into-base-station.md` | Do not merge the pressure rig into the base station; order separate boards in one basket | ACCEPTED · 2026-11-10 · supersedes the assumption that the base station carries an ESP32 |
| 148 | `148-ads1115-analog-sense-and-rail-telemetry.md` | One ADS1115 resolves `OPEN-25` and the `/SCAP_ADC` orphan, with zero new MCU pins | ACCEPTED · 2026-11-10 · closes `OPEN-25` |
| 149 | `149-base-station-control-board-rescope.md` | The base station stops being a discrete analogue RF instrument and becomes a **CONTROL BOARD**; the 433 MHz receive front end is a purchased SPI module. **Supersedes in part** ADR-072/073/079/084 *as they apply to the ground end's receive front end* — those records still govern the radio system, this changes only how it is realised. Two independent reasons. (1) **A sensitivity wall, not a price trade-off:** an AD8318 log detector needs roughly −55 to −65 dBm to register, while an SX1276 demodulates at −137 dBm (SF12) — about **75 dB, a factor of 30 million in power**. Against ADR-009's ~300 km link budget the detector chain cannot be a link receiver at any price; it is only a short-range proximity meter. (2) **The RF work was ours and only ours:** `FLT_433_A/B` are generic package placeholders (never selected devices), and the whole chain still had to be laid out as RF copper. Operator standing preference: *"buy the RF parts as modules that connect via SMA so that we don't need to do any RF engineering."* Decisions: D1 control board; D2 purchased SX1276-class SPI module returning packets + RSSI + SNR; D3 all RF becomes SMA inline, no RF copper laid out; **D4 the AGC loop is DROPPED, not deferred** — ADR-084 already called it an enhancement with manual gain as baseline, and with the detector gone there is no sensor left to control, so the SX1276's own RSSI/SNR supersedes it; D5 buying removes RF *layout* risk, not integration risk (logic level, sequencing, current, torque); D6 no qualification claimed. Measured consequence on `base_station_v1_placed_v2.kicad_pcb`: **44 footprints → 26 kept / 18 retired** (`FLT_433_A/B`, `U_DET`, `U_VGA`, `TEE1/2`, `Q_LNA_SW`, `C_DET1/2`, `C_VGA1/2`, `C_LNA1/2`, `C_TAP`, `FB_DET`, `FB_VGA`, `R_LNA_ILIM`, `J_LNA_FEED`). `J_2450_TX` untouched — separate band, separate function. BOM: `docs/fab/base_station/BOM-RESCOPE.md`. **Open blocker:** the RFM96W breakout is 3.3 V logic only — the 5 V rail and module `VIN` tolerance must be reconciled explicitly in the schematic, not assumed. | **Accepted by operator 2026-11-11** — *"Yes please write the superseding record and re-scope. Yes please make it a control board and please update the bill of materials accordingly."* No board re-fabricated, nothing purchased, nothing powered up. |
| 150 | `150-inflator-and-radio-on-one-board.md` | The inflator and the tracking radio share ONE PCB. **SUPERSEDES ADR-147**, whose Decision 2 ("the cost goal is met WITHOUT merging") is overridden; ADR-147's measurements remain valid, its conclusion does not. **Why the objection no longer holds:** ADR-147 rejected the merge because it "would put a WiFi radio next to an LNA" — ADR-149 then retired the entire discrete receive chain (`FLT_433_A/B`, `Q_LNA_SW`, `TEE1/2`, `U_DET`, `U_VGA`, `J_LNA_FEED`), so there is no longer an on-board low-noise 433 MHz front end to protect. The concern is **reduced, not eliminated**: what survives is supply ripple and ground bounce from a pump into a device resolving sub-mbar (an analog problem), not RF desensitisation (no LNA remains). Decisions: D1 one PCB; **D2 TWO MCUs, not one — RP2040 for radio/host, ESP32-S3 for pressure/inflation** (option table: two MCUs = zero firmware cost; S3-only re-does the tested USB host stack; RP2040-only means porting the dual-MS5611 acquisition and losing WiFi, i.e. rewriting the safety-critical layer to save a part); **D3 the interlock stays entirely inside the ESP32-S3 — the inter-MCU link carries TELEMETRY ONLY**, so no path exists by which the RP2040, radio or USB host can command actuation, preserving "disabled by construction"; D4 shared power, so pump inrush must not brown out the radio and radio TX bursts must not corrupt pressure measurement, both to be measured; D5 the 2.4 GHz antenna keep-out becomes a layout constraint on the pressure side; D6 nothing qualified. Measured: base station after ADR-149 **26 fps / 562 mm²**, pressure controller **26 fps / 2407 mm²**, **combined 52 fps / 2970 mm²** → roughly 70 × 70 mm at the compact board's ~60 % packing (an area estimate, not a placement). Pressure side dominates at 81 % of area. Clearest cost accepted: **a shared failure domain** — one fault takes down radio AND inflator, where ADR-147 gave independent failure. | **Accepted by operator 2026-11-11** — chose option 3, *"Both on one board, the inflator and the tracking radio share one PCB."* No board laid out, fabricated or powered up; no pump run; no actuation. |
| ≥044 | *(reserved)* | next free: `scripts/adr_next_number.py` → 089 | — |

## Non-conforming filenames (not `NNN-description.md`)

These are listed so they are not mistaken for free numbers. They are NOT
renamed by this script (see the rule). Note that `110-tollgate-over-lr2021.md`
effectively competes for number **001** with `001-esp32-c3-as-mcu.md`; it is
recorded here rather than silently renumbered, and that pair also needs an
operator decision.

- `adr-e-hash-relay-DECISIONS.md` — ADR: E-Hash Relay Transport — LOCKED DECISIONS LOG (own Status: UNKNOWN)

