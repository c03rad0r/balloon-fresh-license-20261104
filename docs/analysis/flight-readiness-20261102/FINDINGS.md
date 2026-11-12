# Flight-board readiness audit — 2026-11-02

**Question this answers:** which board is the flight board of record, and what actually measures
between it and a fabricable state. Every number below came from a fresh native run on an isolated
copy; none is recalled from a record.

**Board of record:** `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`,
sha256 `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`
(project `01063b32…`, schematic `360a0404…`, registry `04975e8a…`).
It is **not** `hub_board_v10.kicad_pcb` (`ea9d1bc2…`): that file still carries `U_E28` and 730
segments / 52 vias, versus `U_LORA1280` and 843 / 41 here. Different component set — different board.

## 1. Fresh native measurement (kicad-cli 9.0.9)

| check | result |
|---|---|
| `pcb drc` | **40 violations, 86 unconnected** |
| error/warning split | 18 error / 22 warning |
| `clearance` / `shorting_items` / `solder_mask_bridge` | **0 / 0 / 0** |
| `starved_thermal` | 2 — `U_LORA1280.14` and `J_PROG.1`, one spoke of two |
| `copper_edge_clearance` | 16 — all `J_W1..J_W4` pads 2 and 3, on Edge.Cuts by design |
| `silk_over_copper` | 3 — all `U_LORA1280` |
| `sch erc` on `v10_flight.kicad_sch` | **11 errors** (7 `label_dangling`, 2 `pin_not_driven`, 2 `power_pin_not_driven`) |
| `check_schematic_parity.py` + registry | **7 failures** |
| `registry.py check` | **DRIFT 4, MISSING 52** |
| `model_resolution_census.py` | 49 fp, 34 model refs, 29 resolved, **5 unresolved**, 2 required refs with no model |

Unconnected items decompose as 47 power/ground returns (`GND` 27, `+3V3` 15, `/VSCAP` 5) and 39
signal nets. Only **3** items name a `U_LORA1280` pad, and all three are plane joins — the nine
interface nets are still 9/9 routed, consistent with ADR-140 D3.

## 2. The real blocker is the schematic, not the copper

`check_schematic_parity.py` G1 and G2 pass (ERC is within its documented, count-keyed allowance) and
G5 passes, but:

- **G3** — five nets exist only in the schematic: `ANT1_433_TX`, `ANT2_2G4_RANGE`, `ANT3_2G4_RX`,
  `ANT4_GNSS_L1`, `ANT_C_2G4`.
- **G4** — six nets disagree on nodes: board has `U_LORA1280`, schematic has `U_E28`
  (`+3V3`, `E28_BUSY`, `E28_CS_N`, `E28_DIO1`, `E28_DIO2`, `E28_DIO3`).

ADR-139 replaced the E28 with the LoRa1280 on the **board** only; `build_flight_sch.py` still emits
`U_E28` (`V10_E28_PINS`, line ~2808) and `connectivity/v10_pinmap.reg` still lists `U_E28.1..16`.
Under ADR-128 the schematic is the source of truth, so on these six nets the **board** is the
non-conforming artefact. The repair is a schematic change (pin remap is documented in
`swap_u_e28_to_lora1280.py`'s docstring), not a board change, and it owes its own reviewed commit.

## 3. Rules in force are NOT the frozen rules

No same-stem `.kicad_dru` exists beside the board, so `jlcpcb-s1-frozen.kicad_dru` is never loaded by
native KiCad. The supplied project carries clearance 0.20 / track 0.20 / via 0.60-0.30 in the Default
netclass, but a **global minimum of via 0.50** and clearance/track 0.0. Measured vias:

| via | count | vs frozen 0.60 / drill 0.30 |
|---|---|---|
| d0.50 / dr0.25 | 22 | below **both** |
| d0.54 / dr0.30 | 13 | below diameter |
| d0.60 / dr0.30 | 6 | conforming |

**35 of 41 vias are below the frozen via-diameter rule.** Minimum annular ring 0.12 mm. Minimum
non-wing-seat copper-to-edge **0.4375 mm** (`U_CUT4.3`), below the frozen 0.50 mm edge rule. Nothing
measured against this board may be called frozen-rule-approved until either a same-stem `.kicad_dru`
is supplied or the 0.50/0.4375 values are ruled the design rule.

## 4. A silkscreen defect and two tool defects found by doing the repair

`fix_silk.py` reduced 3 `silk_over_copper` to 1. The residual had two distinct causes, both real:

1. `build_lora1280_footprint.py:116` emits `fp_text user "${REFERENCE}"` — an **unsubstituted
   placeholder**, which prints as literal ink next to the real reference. No DRC rule names it; it
   only surfaces as `silk_over_copper` on the module body.
2. The module's body silk segments sit on its own pads.

`clear_starved_thermal.py` was also found to be unsafe on this board: it sets **every** pad of an
offending footprint to a SOLID zone connection (measured: all 16 `U_LORA1280` pads, including signal
pads that never touch a zone), and its own gate then FAILED (`starved_thermal 1`, `J_PROG.1` untouched
because the ref is not matched by its regex). Recorded here rather than patched in place, because the
scoped tool below supersedes it for this board.

## 5. Scoped thermal repair, gate-passed on a copy

`tools/repair_scoped_thermal.py` takes the pads the DRC itself names and applies the repo's existing
documented rule (a pad whose short axis cannot host two spokes gets a SOLID connection —
`docs/fab/HUB-V9-FULL-ROUTE-RESULT.md`). Control vs result, both refilled:

| | control | result |
|---|---|---|
| errors | 18 `{copper_edge_clearance 16, starved_thermal 2}` | **16** `{copper_edge_clearance 16}` |
| warnings | 19 | 19 |
| unconnected | 86 | 86 |
| new error class | — | none |
| copper segments / vias / pads | 843 / 41 / 301 | **identical** |

Only the three GND zone **filled areas** change (−5.9, −10.1, −3.2 mm²), which is the expected
consequence of removing two thermal reliefs. The candidate board is deliberately **not** committed
here: it must land after the schematic repair above, and a staged `.kicad_pcb` would trip the
board-gate hook.

## 6. Visual review — what was actually reviewed, and by which model

`gpt-6-astra` was **unavailable**: 14 consecutive attempts on a control image returned
`moonshotai/kimi-k3.1-pro` for a `gpt-6-astra` request (served-model mismatch, rejected) and one
returned HTTP 503 `all providers exhausted`. **No Astra verdict exists.**

`moonshotai/kimi-k3.1-pro` reviewed the front-copper plot, served id verified twice, including on a
control image it read correctly (`CONTROL-7Q4`, `TRIANGLE=LEFT`, `SQUARE=RED`). Its verdict:
`DEFECTS_PRESENT 5`. Two of its claims were then measured rather than accepted:

- **"upper-right ~20-25% of the board is unrouted"** — **REFUTED.** Ink coverage in that region is
  68-100% per 1/8 cell; the only 0% cells lie outside the board outline. Its own caveat ("red fill is
  copper pour, not evidence of routing") is the correct reading.
- **"detached reference labels"** — **CONFIRMED and worse than reported**: 49 visible references, of
  which **7 sit 15.6-34.2 mm from the footprint they name** (`R_BAL1` 34.15, `U_CUT2` 27.85,
  `U_HUB_CVT` 18.52, `C4` 17.68, `R_F1` 17.67, `C_HF` 16.18, `R_BAL2` 15.57 mm). This is
  `fix_silk.py`'s margin fallback parking stubborn labels in the free margins. No DRC rule reports it.

A 3D render was **not** used for any judgement: with two required references carrying no 3D model and
five unresolved package paths, component bodies are silently absent and a render would misrepresent
population.

## 7. What is NOT proven

- No fabrication approval. This board is not orderable: 86 unconnected, parity failing, ERC allowance
  load-bearing, and 35/41 vias below the frozen rule.
- No SPI/electrical performance claim; no impedance or stackup qualification.
- The candidate thermal repair is a **candidate**, graded against as-supplied rules only.

## Reproduce

```bash
kicad-cli pcb drc --format json --severity-all -o /tmp/d.json \
  tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb          # 40 / 86
kicad-cli sch erc --format json --severity-all -o /tmp/e.json \
  tracker/hardware/schematics/flight_board/v10_flight.kicad_sch    # 11
PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3 \
  tracker/hardware/check_schematic_parity.py \
  --board tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb \
  --sch tracker/hardware/schematics/flight_board/v10_flight.kicad_sch \
  --registry tracker/hardware/connectivity/v10_pinmap.reg          # 7 failures
PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3 \
  tracker/hardware/connectivity/registry.py check \
  --board tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb   # DRIFT 4 / MISSING 52
python3 scripts/model_resolution_census.py --check \
  --require-refs U1,U2,U3,U5,U_C,U_LORA1280 \
  tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb           # exit 1
python3 tools/flight_readiness/electrical_mechanical_audit.py \
  tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb           # via histogram, rings, edges
```
