# Native placement candidate — INCOMPLETE CONTROLLER, NOT FAB READY

> **Current checkpoint:** operator authorized routing 2026-11-10. Bottom-first GND pours
> reduced native opens 77→72→47, zero shorts/clearance/new violations. See
> [routing/REPORT.md](routing/REPORT.md) and its per-batch proofs/current images.
> `placement/core-placement.kicad_pcb` now contains that partial route. The unrouted
> numbers and gate status below are historical; `routing/batch0.kicad_pcb` preserves their
> exact source. Do not run `placement.py` over the routed file.

Unrouted, operator-gated placement of the real merged core. **No routing has started and none
may start until the operator signs off this placement (ADR-120 R3).** No S0 waiver, no pump or
motor actuation, no purchase, nothing flashed.

## What this board is derived from

| Input | Value |
|---|---|
| Base commit | `229bfafa` (`felixfelix-bot/balloon-fresh` master, merge of PR541 qualified MS5611 lands) |
| Schematic | `core.kicad_sch`, hash in `placement/mapping-proof.json` |
| Netlist | **fresh native export** `kicad-cli sch export netlist --format kicadxml` → `placement/core.xml` |
| ERC | `kicad-cli sch erc --exit-code-violations` → **0 violations** (`placement/erc.json`) |
| Board | `placement/core-placement.kicad_pcb`, sha256 `9ee4f157…ff23ed` |

Connectivity is **not authored here**. `placement.py` reads the exported XML, and every pad's net
comes from that file. It never writes a net name from its own head; a missing or extra endpoint
aborts the build.

## Preserved invariants (all machine-checked on the SAVED board, then re-loaded)

- **125 exported endpoints**, 51 nets, 36 single-endpoint nets, **26 references**, all unique.
- Footprint IDs equal to the schematic's, **byte-for-byte library hashes** from
  `library-sha256.json` (stock KiCad 9 + the project's `PressureSensor:MS5611-01BA03_TE_Recommended`).
- 0 pad-to-pad overlaps (individually transformed pad boxes, not a max-size envelope),
  0 courtyard overlaps (real courtyard polygons, `shapely`).
- 0 tracks, 0 vias: the board is placed, not routed.

## Placement intent, and how it is enforced

| Requirement | Implementation | Enforced by |
|---|---|---|
| S3 antenna at edge | U1 at (28, 6.75), rot 0; antenna section overhangs the north edge | position + rotation assertion |
| Manufacturer antenna keepout | stock courtyard bar `x 4…52, y −21.025…−6.75` (48 × 14.3 mm clear volume, 15 mm guidance met) | nothing but U1 may intersect it |
| USB accessible | J1 shell protrudes 2.8 mm past the west edge, mouth facing west | `bounds[0] < −0.5` and `bounds[2] < 8` |
| Buck compact per TI §11 | U2/L1/C4–C6/R7/R8 in one cell, 2.3–9.7 mm pad-centre gaps (see `power_loop_mm`) | reported each build |
| Sensors away from hot parts | U3/U4 at x 57/69, y 10 — 49.7 mm from L1, 29.4 mm from the S3 shield | positions + reservation test |
| Pressure-port access | both sensors unenclosed on the north-east, ports facing +y (Fab port circles clear, no part above) | courtyard/keepout checks |
| Motor / protection reserved | 30 × 24 mm rule area `x 48…78, y 34…58`, all copper layers, tracks/vias/pours/footprints forbidden; labelled on `Dwgs.User` | zone + "no part intersects" test |

Board outline: 80 × 60 mm, 2 copper layers, 1.6 mm — a **development** size, not a flight
envelope. Nothing in this file claims a mechanical fit.

## Measured result

`placement/view-proof.json` (regenerate with `verify_placement.py`):

- `shorting_items` **0**, `clearance` **0**, `copper_edge_clearance` **0**, `courtyards_overlap` **0**.
- `unconnected_items` **77** — all `same_net_open`, i.e. **expected opens on an unrouted board**,
  and equal to an independent geometric count (union-find over same-net pad boxes: **77**).
  By net: /+3V3 19, /GND 27, /USB5V 6, /EN 3, /I2C_SCL 3, /I2C_SDA 3, /BOOT 2, /BUCK_FB 2,
  /USB_DN_CONN 2, /USB_DP_CONN 2, /BUCK_SW 1, /CC1 1, /CC2 1, /USB_DN 1, /USB_DP 1.
  **Zero records connect different nets** — a cross-net record would be a mapping defect, and
  the verifier refuses on one.
- The only non-electrical record is one `lib_footprint_mismatch` on U1, caused by the declared
  silk→Fab move below. It is allow-listed **by exact class and count** in the verifier.

## Decisions and their evidence

1. **Candidate derived from the netlist, not from the PR528 scaffold.** `build_pressure_rig.py`
   is a quarantine tombstone that emits no PCB; reusing its coordinates would have invented
   connectivity. Rejected: any placement whose nets are not the export's.
2. **U1 silk body outline moved to `F.Fab`.** The antenna sits over the board edge by design, so
   the stock silk rectangle would be clipped (2 `silk_edge_clearance` warnings). Moving the
   outline to Fab is lossless (AGENTS §26) and changes no pad or copper. This is the only
   footprint deviation, and the verifier names it.
3. **`min_through_hole_diameter` set to 0.20 mm in the project file**, not left at the 0.30 mm
   stock default. The stock ESP32-S3 thermal vias are 0.20 mm and the WSON thermal vias 0.25 mm;
   0.20 mm is JLCPCB's standard minimum, and this is recorded rather than discovered as a
   relaxed "clean" score.
4. **Two copper layers, all parts on top.** A four-layer stack would need plane and return-path
   decisions that belong to the routing stage; this milestone is placement.
5. **Deterministic output.** UUIDs are name-based, footprint/child order is canonical, and the
   exporter's wall-clock `<date>` is normalised. Two consecutive builds are byte-identical
   (verified by hash).

## Open issues — exact, not summarised

1. **Routing is unstarted.** 77 opens remain by construction. Nothing here says the placement
   routes; ADR-140 §78–85 requires a route-completion trial on a copy before placement approval.
2. **`COUT_to_VOS_mm` = 9.66 mm** (C5 pad 1 → U2 pad 6) and **`FB_divider_to_FB_mm` = 4.91 mm**
   (R7 pad 2 → U2 pad 5). TI §11.1 wants a short Kelvin VOS at the output capacitors and the
   divider referenced to AGND away from SW. Both are acceptable at placement level but must be
   confirmed by the routed copper, not by these pad distances.
3. **Sensor thermal isolation is not established by distance.** 49.7 mm of separation does not
   account for ground-plane conduction, enclosure airflow or the tubing. Needs a thermal
   measurement on hardware.
4. **Pressure-port mechanics are not designed.** U3 needs a sealed internal tap, U4 an ambient
   vent; both ports must stay free of coating, adhesive and tube strain. No sealing or tubing
   geometry exists in this milestone.
5. **U1 stock footprint carries 9 unnumbered paste-only pads and 13 `41` thermal objects.** The
   pad audit classes these as standard idioms (0 findings, 10 warnings), but the paste apertures
   under the shield need an assembly-house decision.
6. **Still open from the schematic milestone:** capacitor biased-capacitance qualification,
   5V source advertisement/inrush, USB ESD, connector suffix cross-check, S3 suffix, actual
   thermal soak, and every motor-safety item. **No motor circuit is present or invented** — the
   reserved area is empty by design.

## Reproduce

```sh
D=tracker/hardware/pressure-controller-core
/usr/bin/python3 "$D/placement.py"          # ERC + netlist export + board, deterministic
/usr/bin/python3 "$D/verify_placement.py"   # native DRC, opens classification, top/bottom views
/usr/bin/python3 "$D/test_placement.py"     # 7 tests: clean control + 6 real regressions
/usr/bin/python3 "$D/poison_placement.py"   # 4 negative controls incl. a real copper short
```

`verify_placement.py` writes `placement/view-proof.json` binding the exact board hash to the
exact PNG/SVG hashes. Operator views: `placement/top.png`, `placement/bottom.png`.

## Gate status

**PLACEMENT — PENDING OPERATOR SIGN-OFF. ROUTING NOT STARTED.** This is an incomplete
controller candidate; it is not fab-ready, not safety-qualified, and must not be ordered.
