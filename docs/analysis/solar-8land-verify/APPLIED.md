# Solar routes applied: unconnected 86 → 82, DRC errors unchanged — candidate, not a flight build

Applies the B.Cu routes proven in `route_solar_bitmap.py` to a **copy** of
`tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb` (sha256 `732bfe88…`, untouched) and grades
the result with native DRC. Refill-first, control-vs-result, same rules throughout.

## Result

| | control (refilled, untouched) | candidate |
|---|---|---|
| **errors** | 18 `{copper_edge_clearance 16, starved_thermal 2}` | **18, identical set** |
| **warnings** | 22 | 22 |
| **unconnected** | 86 | **82** |
| clearance / shorting_items | 0 / 0 | **0 / 0** |
| new error class | — | none |

**4 unconnected items closed, zero new violations.** Copper diff against the source: **+116 track
segments, 0 removed**, pads and vias untouched (`onlyB=0` in `compare_copper.py`).

Five of the nine pairs closed: 0, 1, 2, 4, 5. Skipped: pair 3, 6, 7 (no path on B.Cu at these rules)
and pair 8 (`U2.4` has no B.Cu pad — a via is structurally required).

## Why this took three attempts, and what each attempt taught

**Attempt 1 — 86 → 80, but errors 18 → 22.** Four new `copper_edge_clearance` items were **my own
tracks**, 7.5–8.25 mm long:

```
Segment of J_W1 on Edge.Cuts | Track [/W1_SOLAR_N] on B.Cu, length 8.2500 mm
```

The repo's allow-list scopes `copper_edge_clearance` to `J_W*` **pads only**, precisely so that a
TRACK at the edge still fails. My router only knew the board rectangle.

**Root cause of attempt 1.** Each `J_W` footprint carries **four Edge.Cuts graphics forming a 6 × 0.5 mm
slot** cut into the board edge (measured: `J_W2` at x 35.73–36.27, y 73.97–80.03; 4 graphics per
connector, 16 total). A router that tests only the bounding rectangle thinks running down that slot is
legal. Both are now stamped as obstacles, and the endpoint exemption applies **only** to the edge rule.

**Attempt 2 — 86 → 82 with errors unchanged.** That is the candidate. The count of provable pairs also
fell 7 → 5 once the slots were treated correctly: two pairs had been "routing" through the slot.

## The consultant's edge claim, checked rather than accepted

`moonshotai/kimi-k3.1-pro` (served id verified) reviewed the B.Cu plot and returned
`DEFECTS_PRESENT 1`, claiming a track runs along the lower-left perimeter. Measured with
`check_edge_approach.py`, which computes the nearest approach of **every new segment** to **every**
Edge.Cuts graphic including the footprint slots:

```
MINIMUM: 0.650 mm (/W2_SOLAR_N to J_W3)
```

The rule requires 0.50 mm. So the tracks **are** close to the slots — the observation is sound and
useful — but nothing violates the rule, and native DRC agrees (edge-clearance 16 → 16). The claim is
correct in direction and wrong in severity: it read a sub-millimetre approach as a defect.

That is the second time this session a consultant's *number* needed checking and its *observation* was
worth having. Both are recorded because "the model was wrong" and "the model was right about something
I had not measured" are different lessons.

## What this candidate is and is not

**Is:** real copper on a copy, graded by the same native DRC as the baseline, with every rule at its
supplied value — no relaxation, no allow-list widened, no rule file changed.

**Is not:** a flight build, a fab approval, or frozen-rule-verified. 35 of 41 vias remain below the
frozen 0.60 mm rule with no same-stem `.kicad_dru`; 82 items remain unconnected; 16 edge-clearances
still need the operator's mating decision; 19 library findings and 15 missing 3D models stand.

The candidate board is **not committed** — it is a `.kicad_pcb`, and staging one trips the pre-commit
board gates by design. It lives at
`~/reports/flight-readiness-20261102/apply/solar-v2.kicad_pcb` with its DRC report beside it.

## Reproduce

```sh
cd docs/analysis/solar-8land-verify
export PYTHONPATH=/usr/lib/python3/dist-packages
/usr/bin/python3 negative_control.py   # must say PASS -- router discriminates
/usr/bin/python3 apply_solar_routes.py \
    ../../tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb /tmp/out.kicad_pcb --grid 0.15
/usr/bin/python3 check_edge_approach.py \
    ../../tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb /tmp/out.kicad_pcb
```
