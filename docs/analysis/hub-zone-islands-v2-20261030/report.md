# Hub zone islands v2 — inventory and endpoint proof

> **SUPERSEDED CAVEAT.** This document was written when the endpoint proof was
> incomplete and carries the heading "INCOMPLETE DRAFT". That is no longer the
> state: the full pipeline has since run to completion with all stages exit 0.
> Read **`FULL-PIPELINE-RESULTS.md`** for the current numbers — coverage 88%
> total, and **22 of 29** arms proven as geometric main-joins with zero new native
> violation identities, 7 recorded as not-proven.
> `native_per_island_proven` remains **false** for every arm: the installed SWIG
> bindings expose no per-filled-polygon membership, so the native check is
> aggregate only. These are not fabrication or batch approvals.

## Outcome and boundary

The recovered inventory was rerun, not restarted from a new hypothesis. **35 filled
zone islands**, **29 provisionally outside their net's designated main component**.
The independent graph gives **Σ(components−1) = 86 over 22 affected nets**, matching
native connectivity's 86 unconnected items. Refill is byte-identical. These are
measured counts, not proof that every inferred graph edge is correct.

**Stitchability: 22 of 29 arms proven, 7 not.** All 29 isolated-island candidate
sites were individually inserted as a 0.50/0.30 mm through via on fresh copies,
refilled and checked by native KiCad DRC. Per-island endpoint proof
(`endpoint_validation.json`) then required each candidate to reach the **pinned
original** main-component member set, with the full after-refill partition equal to
the before-partition except exactly those two components joined, plus a no-via
control graph reproducing the original partition.
**22/29 pass that and introduce no new native violation identities** (verdict
`GEOMETRIC_MAIN_JOIN_NATIVE_LEGAL_SAMPLE`). **7/29 are
`SAMPLED_CANDIDATE_NOT_PROVEN`** and carry their individual reasons.
Baseline: 40 violations, 86 unconnected items.
Count reduction alone does NOT prove a candidate reaches main — see the caveat above.

Source: `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`.
SHA256 before and after:
`732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.
No source copper, placement, silkscreen or routing was modified.

| Net | Layer | Filled islands |
|---|---|---:|
| GND | F.Cu | 12 |
| GND | B.Cu | 18 |
| GND | In1.Cu | 1 |
| +3V3 | B.Cu | 3 |
| VSCAP | B.Cu | 1 |

`islands.json` gives every island's zone UUID/index, area, bounds, centroid,
component/pad membership, same-layer nearest copper and provisional candidate.
Main means most pads in the independent graph, with deterministic tie order;
it is a convention, not an electrical intent waiver.

## Correctness repairs and retained refutations

- Edge check now uses **0.50 mm**, not the erroneous 0.20 mm copper spacing.
- Candidate score considers edge, hard-copper, conservative hole clearance and
  landing on the **designated main component**, not merely any different component.
- Exact distance minima over modeled polygon unions replace the incomplete
  search-window `1e9` sentinel. No-net tracks/graphics and footprint graphics are
  conservative obstacles. Native DRC, not this approximate geometry, tests legality.
- Nearest-feature search checks every per-layer node rather than only the first.
- Graph mismatch with 86/22/native 86 aborts **before classification**.
- Fresh work paths must not exist: earlier evidence is never recursively deleted.
- Native comparison uses a multiset of rule/type/severity/description and sorted
  item UUID/descriptions, not violation counts. Added and removed identities are
  both retained in `native_validation.json`.
- USB_DN graphic copper in `GetDrawings()` is included. Omitting it previously
  yielded the false graph total 87.
- Historical `stitch_validation.json` and `stitch_verification.json` are retained
  **refuted intermediate evidence**, not current proof. Their 27/29 prediction
  agreement and candidate-success counts must not be quoted as legal stitches.
  `verify_stitchable.py` is retired and fails closed.
- The earlier DRC-record-index attribution was invalid because equivalent DRC
  runs can choose different unconnected pairs. Polygon enumeration avoids that
  identity assumption; native violation identity comparison is separate from
  unconnected-record indexing. Related predecessor: PR #379.

A failed sampled site means **no legal candidate found in this sample**, never
proven non-stitchable. The 0.10 mm candidate grid is not exhaustive.

## Intent evidence: no floating-copper waiver

ADR-136, `docs/adr/136-flight-wing-interface-two-land-and-routing-sequence.md:47–48`:

> - **pad 2 (`GND`)** — the wing has no ground plane to reference (ADR-134 removed it), so on the
>   flight build this land carries nothing. It stays on the hub as an unused pad.

`docs/fab/HUB-V9-ORDER-READINESS.md:71–74`:

> ### 2. GND wing-pad stitching (5 of the 10 unconnected items)
>
> `Pad 2 [GND] of J_W1 / J_W2 / J_W3` is unconnected **F.Cu ↔ B.Cu** (its own two layers), and the
> F.Cu pad is not reached by `Zone 'GND_PLANE_F.Cu'`.

The latter is a historical v9 readiness finding, not a measurement of this v10
source. “Unused pad” is not a statement that attached floating copper is intended.
Neither passage authorizes waiving floating copper. This report makes no intent
classification and changes no ADR.

## Reproduction

Requires system Python with pcbnew and Shapely 2, plus `kicad-cli` (this run used
KiCad 9 bindings). From the repository root, use NEW work directories each time:

```sh
D=docs/analysis/hub-zone-islands-v2-20261030
/usr/bin/python3 "$D/run_island_inventory.py" --repo "$PWD" \
  --work "$PWD/.zi2scratch/reproduce-inventory" --out "$D/islands.json"
/usr/bin/python3 "$D/validate_stitching.py" --repo "$PWD" \
  --work "$PWD/.zi2scratch/reproduce-native" \
  --inventory "$D/islands.json" --out "$D/native_validation.json"
/usr/bin/python3 -m unittest discover -s "$D" -p 'test_*.py'
sha256sum tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb
```

Executed recovery directories: `.zi2scratch/recovered-inventory-1` and
`.zi2scratch/recovered-native-1`. The original `.island_work`, `.stitch_work` and
`.zi2scratch` evidence remains local, outside the tracked deliverable.

## Verification and open gates

- Inventory execution: exit 0; 35/29/86/22, unchanged source, refill byte no-op.
- Native single-via execution: exit 0; all 29 arms completed and checkpointed.
- **20 regression tests pass**, including wrong-main/count-equal joins, split/merge,
  missing/added copper, layer mismatch, witness retention, index reordering,
  no-via topology change, extra joins and native disagreement.
- Coverage was installed in a system-site-packages venv, not system Python.
  Measured unit + 29-arm integration coverage for `endpoint_proof.py`: **122/134
  statements (91.04%), 40/52 branches (76.92%), combined 87.10%**. Unit-only combined
  coverage was 45% before the final guard additions. The whole legacy geometry
  pipeline is NOT ≥80% covered (inventory 35%, native validator 17% in this replay).
  `endpoint_coverage.json` preserves the measured scope; cross-family review pending.
- Native per-filled-polygon membership remains unavailable in the installed SWIG
  API. Geometric endpoint proof now exists for 22 legal samples; it is explicitly
  not promoted to native proof or fabrication approval.
- Graph geometry retains approximations (curves, holes/slots, fallback pad shapes,
  4 µm contact tolerance); agreement of global counts is not full topology proof.
- KiCad emitted `PCB_VIA::GetWidth called without a layer argument` warnings in
  inventory execution. Results are provisional, not a fabrication gate.

## Endpoint follow-up: full partition, pinned identity, and limits

`endpoint_proof.py` reuses the 29 preserved refilled single-via boards, verifying
**each board SHA against `native_validation.json` before reading it**. It does not
regenerate evidence or edit any board. Baseline native 86 and graph 86/22 are a
fail-closed gate, including exact per-net agreement with the published inventory.

For every arm, the full copper graph is rebuilt before and after. Hard copper is
mapped by UUID, unchanged geometry/net/layers; filled polygons are mapped by a
unique positive-area overlap within the same zone UUID/net/layer, not outline
index. Every polygon must retain ≥99% of its original area and its original
interior witness. Splits, merges, lost or extra polygons fail closed. Main is
**pinned to the entire original component's member set**, never reselected after
adding a via. The exact target polygon, inserted via and every main member must
reach one component. The complete after-partition must equal the before-partition
with exactly those two components joined. A separate graph of the after-refill
copper **excluding the new via** must equal the full original partition, ruling
out reassignment caused by refill alone. All these checks run both with the
legacy 4 µm tolerance and with zero-distance contacts. Native connectivity counts
are checked against both graph totals and the saved native DRC result, never used
to identify a particular island or to infer endpoint membership.

Results (`endpoint_validation.json`, per-island mappings and witnesses retained):

- **23/29** pass the conservative geometric endpoint/partition proof, including
  the zero-tolerance sensitivity check.
- **22/29** also have no new native DRC violation identities. These are qualified
  geometric-main-join samples, NOT native per-island proofs or combined approval.
- `GND_BCu|B.Cu|1`: geometric join passes, but native legality fails.
- `P3V3_BCu|B.Cu|0`, `|1`, `|2`: sampled via does not reach pinned main; native
  legality also fails. This does not prove no alternative via site exists.
- `GND_FCu|F.Cu|7` and `GND_BCu|B.Cu|9`: refill adds an unmatched filled polygon
  (respectively B.Cu index 4 and F.Cu index 11, UUIDs in evidence). Identity gate
  refuses a proof even though these samples introduce no new native violations.
- `GND_BCu|B.Cu|13`: target reaches main geometrically, but the change is not an
  exact two-component join (native 84, not 85); conservatively rejected rather
  than crediting a count improvement involving an additional component.

**Exact remaining limitation:** installed pcbnew SWIG map/vector bindings do not
provide usable per-filled-polygon native component membership. The already-proven
API failures were not retried. Native 86→85 agreement cannot authenticate the
geometric partition. Geometry still inherits the inventory's curve, pad-fallback
and hole/slot approximations; zero tolerance removes the proximity-only join
risk but not those shape-model risks. Thus native `connectivity_proven` stays
false on all 29 arms. This is the strongest measured geometric proof, explicitly
bounded, not an assertion that native endpoint proof was obtained.

Replay after the native experiment command above (substitute its new work path):

```sh
/usr/bin/python3 "$D/endpoint_proof.py" \
  --evidence "$PWD/.zi2scratch/reproduce-native" \
  --out "$D/endpoint_validation.json"
```

This run used `.zi2scratch/recovered-native-1`; logs and coverage data are retained
in `.zi2scratch/endpoint-run.log` and `.zi2scratch/endpoint.coverage`. Coverage
7.17.0 ran in `.zi2scratch/coverage-env` with system site packages. Coverage data
combine the actual 29-arm replay with the 20 passing unit regressions; they do not
pretend the historical native DRC execution ran under coverage.

## Decisions

Publish as an **incomplete draft**, rather than call 25 candidates stitchable.
Evidence supports inventory counts, 29 native single-site experiments and the
22 qualified geometric endpoint joins below; it does not support native
per-island connectivity or whole-pipeline coverage claims. Reject
silently accepting the older count-only results or inferring impossibility from
four failed samples. Promotion requires native landing proof, sufficient test
coverage and independent review. No merge or board edit is authorized here.
