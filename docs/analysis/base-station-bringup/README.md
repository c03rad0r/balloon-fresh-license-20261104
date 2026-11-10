# Base station: logical pin-map prerequisite repairs (NOT layout-ready)

**Supply continuation:** [fixed-5-V logical correction and remaining blockers](5v-supply.md).
Earlier regulator-voltage/startup findings below are historical; no PCB readiness implied.

**Continuation:** [RP2040 package-pin correction and current blockers](rp2040-pinmap.md).
The report below records the earlier regulator-only milestone; its RP2040 mapping failure
and stale netlist-test path are repaired by that continuation, not the PCB or supply design.

Base inspected: master `2449ad8a`; live PR list inspected before work (no active base-station repair identified). Artifact of record per ADR-147: `tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb`. Read ADR-084, ADR-114, ADR-147 and D14 freeze. RF intent is unchanged: 433 RX only, VGA after LNA, second 433 BPF before detector, separate LNA/VGA/detector/MCU rails, no added 2.4 GHz PA.

## Applied decision

Correct **only U_REG's pin assignment in the logical generator and generated netlist**. TI SLVSAM2E §6 gives DSG pins PGND=1, VIN=2, EN=3, AGND=4, FB=5, VOS=6, SW=7, PG=8, exposed pad=AGND. For the selected fixed-output variant, FB connects to AGND. Previously VIN was on PGND, ground on VIN, SW on EN, feedback on AGND, output on FB, ground on VOS and enable on SW. This was a real electrical blocker, invisible to native DRC.

Source: https://www.ti.com/lit/ds/symlink/tps62160.pdf (SLVSAM2E, sections 5/6 and DSG package drawing). Stock KiCad WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm loads natively; numbered pads 1–4 left top-to-bottom, 5–8 right bottom-to-top, 9 centre; two unnamed paste apertures are not electrical pins. The 2 mm body / 0.5 mm pitch / 0.9×1.6 mm exposed pad matches the DSG drawing. No new footprint geometry.

Alternative rejected: routing any net or updating the board now. The board is electrically invalid and lacks an authoritative ERC-clean schematic. **The committed board remains unchanged and intentionally does not yet match the repaired netlist.** This PR is a logical-source prerequisite, not copper progress or a working regulator. A schematic-first controller/power rebuild must precede board regeneration. No ERC waiver, rules relaxation, purchases or hardware access.

## RED → GREEN

Command: `/usr/bin/python3 tracker/hardware/base_station/test_regulator_pinmap.py`.
Before repair: exit 1, manufacturer pin-map assertion failed (full expected mapping vs legacy mapping). After repair: exit 0, 3 tests pass: source mapping, generated netlist mapping, known reversed-input negative control. Regenerate with `/usr/bin/python3 tracker/hardware/base_station/gen_base_station_netlist.py` (exit 0; 44 parts, 44 nets). `git diff --check`: exit 0.

Legacy `test_netlist_implements_spec.py`: **NOT RUN successfully**, exits 1 because it hardcodes missing `/home/c08r4d0r/worktrees/v9-route/...`. It does not constitute ERC. No `.kicad_sch` exists in the base-station directory. ADR-114's intended SKiDL/forward schematic flow has not been implemented by this legacy direct-netlist generator.

## Native board evidence (unchanged rejected artifact)

KiCad CLI / pcbnew 9.0.9. Run from repository root:

```
kicad-cli pcb drc --format json --exit-code-violations \
  -o docs/analysis/base-station-bringup/native-drc.json \
  tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb
kicad-cli pcb export svg --layers F.Cu,F.Silkscreen,Edge.Cuts \
  --output docs/analysis/base-station-bringup/rejected-board.svg \
  tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb
```

DRC exit **5**, 143 violations + **63 unconnected**. Classes: clearance 37, solder-mask bridge 37, silk overlap 48, silk-over-copper 16, silk-edge-clearance 5. Native census: **44 footprints, zero tracks**. Matching existing `.kicad_pro` loaded in place; no `.kicad_dru` exists in this directory, none added. No before/after improvement claimed: board, project and placement remain byte-identical. Render export exit 0. [Rejected board 2D render](rejected-board.svg), not a 3D/model or assembly approval.

SHA256:

| Object | SHA256 |
|---|---|
| board | `095d0278410465f24a2f229969a21017d469bfd34c31f597fea24a6d6afe61af` |
| matching project | `d2d19f93e8df91d04bf8a0c3bcd10f25e863d3948a38412be4d17b15cc51d214` |
| repaired generator | `c82adec3ccabec87f0a7cc4bf3b4680dc7ba9fb66a35d5f39c15ef1dab536f3d` |
| repaired netlist | `89efee41564f0d731379c9df13255cd959e576ce00ac0bf6e572a541e025bfe3` |

## Untouched blockers — no shipment readiness claim

- **Wrong regulator voltage in frozen specification**: TI §5 states TPS62162 is fixed **3.3 V**, TPS62163 is fixed **5 V**. D14/spec/generator label claiming TPS62162 5 V is false. This bounded patch does not silently override the freeze or claim the rail is repaired. Resolve part selection in a reviewed schematic; legacy feedback divider is now disconnected from U_REG and must be removed/reworked there.
- **Regulator enable bootstraps from its own output** via R_EN. No guaranteed startup; input 18 V also exceeds 17 V operating rating. Protection and startup circuit remain unresolved. PG pull-up absent.
- **RP2040 mapping fails official pinout**: manufacturer datasheet §1.4 Figure 3 (printed p11, PDF p12), visually read from downloaded official PDF: SWCLK=24, SWDIO=25, QSPI_SS_N=56, USB_DM=46, USB_DP=47, ADC_AVDD=43. Generator instead assigns SWCLK=28, SWDIO=29, QSPI_SS=10, USB=33/34, ADC_AVDD=3. Several true supply pins are grounded. This is not a routable controller.
- RP2040 library loads (70 pad objects including paste/EP subdivisions, not 70 package pins), but came from a demo, not manufacturer qualification; full landpattern verification against Chapter 5 and power/core decoupling redesign remain required. Datasheet: https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf . No claim full controller footprint qualification passed.
- Unspecified LDO/load switch, incomplete RF IC mapping/parts, bias-tee interfaces and ADC range protection require schematic validation. RF netlist untouched; preservation is not validation.
- 37 native clearance violations plus assembly/silk failures, unrouted board, missing ERC, no tested forward schematic-to-board parity, RF placement/impedance qualification and manufacturing gates remain open.

Parent must independently review/merge; no v10 tags or shared flight-ready worktree touched.
