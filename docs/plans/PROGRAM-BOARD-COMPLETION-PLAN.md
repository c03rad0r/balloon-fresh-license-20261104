# PROGRAM — Complete every board end-to-end, then order from JLCPCB

**Created:** 2026-10-11
**Owner:** balloon-hermes (manager)
**Objective (operator, 2026-10-11):** 3D models, schematics, board designs and
**routed** PCBs for every board the end-to-end system needs — balloons as a
*bent pipe* connecting base stations via FLRC. Lock geometry early, DRC clean
before advancing a stage, LLM spatial review (Astra-class) before `done`, RF
decisions must be defensible, and every board fab-ready at JLCPCB — then place
the order.

---

## Current priority and tool-investigation backlog (2026-11-02)

**P0: continue JLCPCB order preparation now.** Owner: balloon-hermes manager;
status: ongoing. This update adds no research-before-order gate and no dependency
from G0–G8 onto any investigation below. Existing electrical, RF, mechanical,
review and fabrication gates remain binding; this is not a declaration that the
board is ready to order. PR [#380](https://github.com/felixfelix-bot/balloon-fresh/pull/380)
(zone-island analysis) stays separate and is not merged by this roadmap update.

The sections below this backlog retain their dated October planning snapshot,
not a live board census. In particular, old v9 counts, Python 3.14 instructions
and model-library availability claims must not drive today's order. Use the
current [agent rules](../../AGENTS.md), [ADR index](../adr/INDEX.md),
[fab index](../fab/README.md) and the selected board's current gate evidence.

### Order-prep boundary and immutable evidence

- Continue the existing order-prep lane without waiting for tool evaluations.
  Before an experiment, pin its input source commit and SHA-256 hashes of the
  schematic, board, project/rules, netlist and relevant libraries in its evidence
  record. Work only on an isolated copy; never regenerate the order source.
- The order-prep owner freezes the selected source revision and records exact
  SHA-256 hashes of the final Gerbers, drill, BOM, CPL and package archive in the
  order evidence. Recheck hashes before submission. An experimental output cannot
  replace that package without a separate reviewed change and complete re-gating.
- Preserve 0.20 mm clearance and 0.50 mm copper-to-edge rules, including only
  already-approved scoped exceptions. No automatic rule relaxation. Preserve RF
  matching/impedance and return paths, keepouts, locked copper, connector/wing
  interfaces, outline, placement and mechanical constraints.
- JLCDFM is an adjunct manufacturing check, not proof of circuit correctness or
  a substitute for ERC, connectivity, DRC, simulation or RF review. BOM approval
  requires actual manufacturer part numbers, footprints and current sourcing/
  availability evidence; generated substitutions are not approved parts.

### Bounded investigations — none on the order critical path

Owner for every row: **balloon-hermes manager** (may delegate read-only research;
retains the decision). Status is **deferred / not started** unless stated otherwise.
P2 starts only after the current order-prep handoff, or in independently available
capacity with no contention for its tools, reviewers or compute. P3 follows P2.
Budgets are cumulative wall-clock caps per row, not permission for retry loops;
stop at the cap and record adopt / defer / reject plus evidence and next trigger.
No account creation, paid job, purchase, external design upload or cloud routing
is authorized by this roadmap. Money budget: **zero**; request separate approval
for any paid/API inference work. Stop and defer immediately if order prep needs
those resources. Model price/ranking claims are outside this evaluation.

| ID / priority | Investigation and bounded budget | Exit criteria / evidence |
|---|---|---|
| T1 / P2 | **AI-PCB-Generator: 90 min** source inspection only. Its [README](https://github.com/22507260/AI-PCB-Generator) describes structured `CircuitSpec` and an internal A* fallback when Freerouting fails or produces no SES. Evaluate reusable ideas, not its production-readiness marketing. | Pin upstream commit; inspect implementation, license/dependencies, credential/network handling and tests. Identify whether failure/fallback is observable and independently validated. Produce a small reuse/reject list for structured specs, checks or export handling; no generated board adoption. Defer if safety or license cannot be established within budget. |
| T2 / P2 | **Freerouting incremental evaluation: 90 min**, including at most one 30-min local routing trial. The [official README](https://github.com/freerouting/freerouting) documents DSN/SES CLI; the [MCP guide](https://github.com/freerouting/freerouting/blob/master/docs/API/MCP.md) documents integration options. Existing pipeline already uses Freerouting: compare only version/integration gains, not a wholesale migration. | Record existing and candidate versions, commands and hashes; compare the same frozen input using local execution only. Measure runtime, unconnected items, DRC classes, constraint/locked-copper preservation and deterministic export/re-import. Missing SES or failed run is a failure, never silent fallback success. Retain current pipeline unless repeatable benefit is demonstrated under unchanged rules. |
| T3 / P2 | **Quilter feasibility: 60 min**, official-document review only. [Quickstart](https://docs.quilter.ai/get-started/quickstart) requires a complete schematic plus outline, footprints and netlist; pre-placed components and pre-routed copper are locked. | Document supported formats and constraint preservation; verify any supported API/CLI from official evidence before proposing automation. `quilter submit` is unverified and must not be used as an assumed command. If no official API evidence is found, record that limitation rather than invent an integration. Any later candidate run needs separate upload/account/spend approval, an isolated future-board copy and preserved RF/mechanical locks; it cannot gate this order. |
| T4 / P3 | **Attic PcbRouter compatibility: 30 min** source/format review only. [README](https://github.com/The-OpenROAD-Project-Attic/PcbRouter) states KiCad 5.1.2-format support versus our KiCad 9.0.9 environment. | Establish a credible lossless KiCad-9 round trip before proposing a sandbox trial; otherwise park. Main OpenROAD silicon routing is not a drop-in PCB router. No board conversion on the order source. |
| T5 / P3 | **Backplane: parked, 0 min execution budget** until a concrete primary-source repository/product URL is supplied. | Owner records the primary source and a new bounded proposal before evaluation. A name alone is not sufficient provenance; no dependency on it. |

**DECISIONS:** retain the existing fabrication gate chain and order-prep priority;
reject replacing it with research or production-ready marketing claims. Official
sources above establish candidate capabilities, not suitability for this board.
Adoption requires a separate evidence-backed review after the bounded evaluation;
failed or inconclusive investigations are deferred, not added as order blockers.

## 0. Where the truth lives

| Source | What it owns |
|---|---|
| `docs/analysis/GAP-TRACKING-CHECKLIST.md` | reconciliation of rounds 1+2; the row ids quoted below |
| `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` | round 2 gap analysis (base doc: `PROGRAM-GAP-ANALYSIS.md`, 620 lines) |
| `docs/adr/INDEX.md` | every design decision; `scripts/adr_next_number.py` owns the next number |
| `board_status_census.py` + `docs/analysis/board-status/` | machine census of what is actually routed, per layer |
| `AGENTS.md` | measured environment gotchas (`pcbnew` only under `/usr/bin/python3.14`, 3D render limits) |

**Measured machine state (this session, `kicad-cli` 9.0.8 + pcbnew):**

| board | layers | fp | segments | vias | zones(filled) | DRC unconnected | verdict |
|---|---|---|---|---|---|---|---|
| `hub_board_v9` | 4 | 39 | 0 | 0 | 3 (3) | 101 | `plane_only` |
| `wing_board_v9` | 2 | 15 | 20 | 8 | 0 | 0 | `routed` |
| `auto-bootsel-interposer` | 2 | 14 | 9 | 0 | 1 (1) | 0 | `routed` |
| `v8g_krt_routed` (old gen) | 4 | 20 | 398 | 55 | 2 (2) | 0 | `routed` |

**DRC split — errors vs warnings (re-measured with `--severity-all`).** Quoting a
single "violations" number is how a board gets green-washed, so both are stated:

| board | errors | unconnected | warnings |
|---|---|---|---|
| `wing_board_v9` | **0** | **0** | 37 (`lib_footprint_issues` 15, `silk_edge_clearance` 9, `nonmirrored_text_on_back_layer` 6, `silk_overlap` 2, `track_dangling` 2, `text_height` 2, `silk_over_copper` 1) |
| `hub_board_v9` | **28** (`copper_edge_clearance` 16 + `drill_out_of_range` 12) | **101** | 41 (`silk_over_copper` 16, `silk_overlap` 12, `lib_footprint_issues` 7, `silk_edge_clearance` 6) |

The hub's 28 errors and all of the warnings above are **pre-existing** — measured
at baseline before the GND pour; the pour added zero new ones. `lib_footprint_issues`
on all 15 wing footprints means the footprints do not match their library
definitions: not a fab blocker, but not "clean" either.

---

## 1. Board manifest — required vs. real

| # | Board | Purpose in the end-to-end system | Exists? | State |
|---|---|---|---|---|
| 1 | **Flight/payload hub** (`hub_board_v9`) | Balloon payload: MCU + FLRC radio + power + array interface | yes | 4-layer; **placement + GND planes only, 0 tracks/vias, DRC 101 unconnected** |
| 2 | **Wing** (`wing_board_v9`) | Deployable solar wing (double-sided cells) | yes | 2-layer; **routed, DRC 0 unconnected** (fixed this session, PR #47) |
| 3 | **Base station** | Ground gateway: RX chain, AGC, log detector, ADC/MCU, bias/rails, 2.4 GHz uplink PA | **NO** | `BS-01` — no schematic, netlist or gerber on any ref. ~16 `design/*` branches unmerged; ADRs 071–084 branch-only |
| 4 | **Pre-stretch / pressure bench rig** | Automated leak + pre-stretch cycle before flight | **NO** | `PRE-01` — protocol + breadboard firmware only; no schematic/footprint/layout/BOM |
| 5 | **Auto-BOOTSEL interposer** | Programming aid (ESP32-C3 ↔ RP2040) | yes | 2-layer; routed, DRC 0 |

**Old-gen archaeology:** ~100 `.kicad_pcb` variants under `tracker/hardware/output/`.
None of them is a deliverable; they are history. The `v8g/v8i` family is the most
complete old-gen lineage (4-layer, 398 seg / 55 via / 2 filled planes) and is the
closest thing to a routed flight board that exists.

---

## 2. The gate chain (operator's rules, made mechanical)

A board may advance a stage only when the previous gate has **observed output**,
not a self-report.

```
G0 GEOMETRY FREEZE      outline, modular grid, connector/land geometry, band plan
                        → ADR + single-source-of-truth parameter registry row
G1 SCHEMATIC            .kicad_sch, ERC clean, netlist exportable
G2 PLACEMENT            all parts placed, courtyards present on 100% of footprints
G3 ROUTING              tracks+vias on every net; DRC unconnected == 0
G4 DRC                  kicad-cli pcb drc: 0 errors, 0 unconnected (authoritative)
G5 3D + RENDER          3D models resolve; render shows real bodies (see 3D gap)
G6 SPATIAL REVIEW       Astra-class LLM review, cross-family, before `done`
G7 FAB SET              gerbers + drill + BOM + CPL exported, JLC rules checked
G8 ORDER                operator approves and places the JLCPCB order
```

**Non-negotiables carried from this repo's own rules (AGENTS.md, ADR-030):**
- `pcbnew` only under `/usr/bin/python3.14` — importing it under 3.11 **segfaults**
  the pytest run.
- **A total-only check is not evidence.** `test_3d_models_wing.py` asserted
  `(segment ) == 8` for a year while the back string was electrically isolated.
  Gates assert the **property** (e.g. F.Cu *and* B.Cu carry signal), never a magic total.
- **"Compile/parse clean" ≠ "DRC clean".** Only `kicad-cli pcb drc` counts.
- Vision must not be used to infer component positions from a render (3D library absent).

---

## 3. Blocking defects found now (must be fixed before their gate)

| id | defect | evidence | gates |
|---|---|---|---|
| **D1** | **`PCB-01` does NOT reproduce.** The checklist says the wing is "12 footprints / 0 with `CrtYd`"; measured now on **both `origin/main` and this branch: 15 footprints, 15 with `CrtYd`**. | re-measured this session, both refs | row must be re-measured at source before it gates anything — not claimed as fixed |
| **D2** | **Hub board is not routed at all** (0 tracks, 0 vias; 101 unconnected after the GND plane). | census above | G3/G4 |
| **D3** | **3D-model pipeline broken:** `KICAD9_3DMODEL_DIR` unset, no model library → every render is substrate+copper+silk only. Fix UNMERGED (`PCB-02`). | AGENTS.md lines 136–137 | blocks G5 *and* makes G6 blind — a spatial reviewer cannot judge part bodies it cannot see |
| **D4** | **RF-03: 2 MHz FLRC does not fit the 433 band.** ADR-073 fixes the 433 downlink at FLRC-max 2.6 Mbps = **2.666 MHz DSB** against a **1.74 MHz** allocation (1.53×). | `docs/adr/073`, ROUND2 §3.1 | **G0** — the band plan must be settled *before* the duplexer/filter is frozen, or the hardware is wrong at fab |
| **D5** | **RF-01: bent-pipe vs half-duplex.** ADR-035 mandates exactly one radio transmitting at a time; the operator's premise is a bent pipe (simultaneous). | ADR-035; ROUND2 §11.1 | **service model** — decides whether the relay is simultaneous or TDM store-and-forward |
| **D6** | **RF-02: uplink budget used LoRa sensitivity (−141.5 dBm) for an FLRC mission (≈ −99 dBm)** — ~40 dB optimistic. | `docs/2G4-LINK-BUDGET-ANALYSIS.md`; corrected in `uplink-budget-realistic-ground.md` | G0/RF defensibility |
| **D7** | **BS-05: the 433 RX LNA (TQP3M9037) vendor band is 0.7–6 GHz — it does not cover 433.92 MHz.** The whole 433 RX chain is built around it. | `433-lna-substitution-and-amateur-licence.md` §0.1 | G1 of the base station |

**D4, D5, D6 are the RF decisions that must be frozen before any base-station or
flight-board geometry is locked.** That is the operator's "make sure the RF
decisions make sense" gate, and it is a *pre-condition*, not a later review.

---

## 4. Phases

### Phase A — freeze the RF + geometry decisions (G0)
- A1 settle **D4** (433 band plan: real FLRC rates that fit 1.74 MHz, or move the
  high-rate link to 2.4 GHz) → ADR, superseding/amending ADR-073 as needed.
- A2 settle **D5** (bent pipe: simultaneous vs TDM store-and-forward) → ADR-035
  amendment. This decides the latency/throughput service model.
- A3 correct **D6** in place and record the corrected budget as authoritative.
- A4 resolve **D7** (433 LNA: substitute part or re-architect the RX chain).
- A5 write the **single-source-of-truth parameter registry** rows (outline, land
  size, flash, band split, wing orientation, cell class) and reconcile the four
  known duplicate-value defects recorded in AGENTS.md.
- **Exit:** every G0 decision has a landed ADR; no parameter has two live values.

### Phase B — flight/payload boards to fab-ready
- B1 fix **D1** (courtyards on 100%) and re-assert the overlap gate.
- B2 route the **hub** (D2): tracks + vias on every net → DRC 0 unconnected.
- B3 fix **D3** so renders show real bodies, then produce per-side/per-layer
  visual evidence.
- B4 3D models for every footprint on both boards (coverage doc exists for the wing).
- B5 fab set for hub + wing + interposer (G7).
- **Exit:** hub and wing pass G4→G7 with observed output.

### Phase C — base station board (the biggest gap)
- C1 merge/consolidate the ~16 unmerged `design/*` branches so there is a design
  of record (ADRs 071–084 on `main`).
- C2 schematic + ERC (G1) → placement with courtyards (G2) → route (G3) → DRC (G4).
- C3 select the missing 2.4 GHz uplink PA (BS-02) and price the 5 unpriced BOM rows (BS-03).
- C4 fab set (G7).
- **Exit:** base station passes G1→G7.

### Phase D — pre-stretch bench rig
- D1 schematic (pressure sensor, valve, relief/interlock per PRE-04) → layout → route → DRC → fab set.

### Phase E — review + order (G6, G8)
- E1 Astra-class cross-family spatial review on every board **before** `done`.
- E2 operator sign-off, then place the JLCPCB order (G8).

---

## 5. Live blockers (honest)

1. ~~DISPATCH IS QUOTA-BLOCKED~~ **CORRECTED: dispatch is ALLOW.**
   `zai-quota-gate.sh` first reported `BLOCK capacity`, then on re-check reported
   `ALLOW via fallback-probe` (exit 0). The two rails are separate and both were
   misread by me at first:
   - **z.ai cheap-gate** — balance-metered, now ALLOW.
   - **`openai_codex` (Astra)** — ChatGPT-subscription, not balance-metered.
     `enabled: true`, `price_skew: 1.5`, `codex_quota.json` = **used 3.0% /
     remaining 97.0%**, not exhausted, both kill switches absent. `gpt-6-astra`
     answered a live probe through the router. It is deliberately reserved for
     **SPATIAL/VISION + CROSS-FAMILY REVIEW** and can only be selected by an
     explicit pin — which is exactly the G6 gate.
   Therefore **G6 IS available**, and the correct statement is the opposite of my
   first report: the review rail is funded, the general-work rail is the one
   that fluctuates.
2. **PR #47 is open** (`fix/pcb-defects-v9`, MERGEABLE, 4 commits, 19 files):
   wing B.Cu interconnect fix + hub GND planes + machine-checked status figure.
   Not merged — awaiting review.
3. **`main` is behind the design work**: ADRs 071–084 live only on branches (`BS-06`).
4. Every HUMAN/BENCH row (S_crack coupon `PRE-02`, LiteVNA purchase, BNetzA
   enquiry `LEGAL-01`, descent/recovery `SAFE-01`) needs the operator, not an agent.

---

## 6. Token-cost triage — what to do cheaply vs. what to surface

Written at the operator's request ("do what you can do cheaply now, surface
tasks that could burn a lot of tokens"). Cost classes are relative to a
deterministic `kicad-cli`/`pcbnew` run, which costs **zero inference tokens**.

**Class A — deterministic, zero inference tokens. Run immediately, inline.**
`kicad-cli` DRC, `pcbnew` census, gerber/drill export, netlist/ERC, courtyard
geometry, BOM extraction, the status figure pipeline, generator re-runs. None of
this needs an LLM and none of it can be green-washed, because the numbers come
out of the tool.

**Class B — cheap LLM, bounded prompt. Fine to run.**
Reading one document and answering a specific question ("does ADR-073's bandwidth
fit the 433 allocation?"), summarising a diff, drafting a card body. Single-digit
thousands of tokens.

**Class C — expensive LLM, must be surfaced to the operator first.**
Routing a 128-pad, 4-layer board; a full spatial review of every board; a
multi-hundred-request autoroute retry loop; a whole-program re-derivation
(`deleg_0b9d4ef2` died exactly this way at 8 API calls). These are the ones to
mark **SOON**, not NOW.

### The decision matrix

| task | class | cost driver | recommendation |
|---|---|---|---|
| D1 re-measure `PCB-01`/`PCB-02` at source | **A** | none | **NOW — done, D1 does not reproduce** |
| D3 fix the 3D-model pipeline | **A** | none (env + lib path) | **NOW** — highest leverage: unblocks G5 *and* unblocks the G6 reviewer |
| G4 re-run DRC on every board, errors vs warnings | **A** | none | **NOW — done above** |
| Gerber/drill export for a board | **A** | none | **NOW, per board, once that board's G4 is clean** |
| D2 route `hub_board_v9` (39 fp, 4-layer) | **C** | autoroute loop | **SOON.** Deterministic floorplan + critical nets first; escalate to an LLM router only with a cost estimate on the table |
| D4 RF-03 band plan (2 MHz FLRC vs 1.74 MHz) | **B** | one focused analysis + ADR | **NOW — cheap, and it gates G0, so every other board waits on it** |
| D5 bent-pipe vs half-duplex (ADR-035) | **B** | one focused analysis + ADR | **NOW — same reason, gates the whole service model** |
| D6 uplink budget re-derivation | **B** | one link-budget calc | **NOW — arithmetic, I can do it deterministically and check it with an LLM** |
| D7 433 LNA band mismatch | **B** | part-substitution analysis | **NOW — cheap, and it changes the BOM** |
| Base station design from ~16 `design/*` branches | **C** | reconciliation + schematic + route | **SOON, and staged**: merge branches (A) → schematic (A/B) → placement (A) → route (C, surfaced) |
| Pre-stretch bench rig | **C** | new board, simpler | **SOON** |
| G6 spatial review, per board | **B/C** | pinned `gpt-6-astra`; **97% of the window unused** | **NOW for each board as it reaches G5** — cheap at current usage, and it is the gate the operator mandated |

**The one thing I want you to decide:** `hub_board_v9` routing (D2) is the single
largest token risk in the program. A 39-footprint, 4-layer board routed by an LLM
router can burn a large multiple of everything else combined. My recommendation:
**do the deterministic parts first** (floorplan, net classes, critical RF nets
placed by geometry), then bring a concrete estimate before any LLM autoroute loop
runs. If you would rather I attempt it now and report the spend, say so and I will
mark it NOW instead of SOON.

---

## 7. What "done" means

The program is done when, for **each** board in §1: G0–G7 have observed output in
the repo, an Astra-class review is attached, and the board is in a JLCPCB-orderable
fab set — at which point the operator places one order covering the set.
