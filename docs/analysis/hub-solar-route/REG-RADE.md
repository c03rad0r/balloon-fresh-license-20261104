# Independent re-grade: the applied solar routes on a second, unrelated router

**Why this file exists.** `solar-8land-verify/APPLIED.md` (#440) reports the
applied result using `route_solar_bitmap.py`. `hub-solar-route/FINDINGS.md` (#435)
reports a *different* router reaching *different* conclusions. Two tools, two
answers, one board. This is the third measurement, taken with a router that
shares no code with either, and it is the one that decides which claim survives.

**Verdict:** the **applied set is right (5 pairs, unconnected 86 → 82, DRC error
multiset unchanged)** and **FINDINGS.md's "3 geometrically blocked" reasons are
wrong** — one of those three routes perfectly well, and the other two are stopped
by a socket slot rather than by a closed corridor.

## Board

| | |
|---|---|
| input (untouched) | `hub_board_v10_lora1280_7of9.kicad_pcb`, sha256 `94038dd0…6c1155` |
| output | `hub_board_v10_lora1280_7of9.kicad_pcb`, sha256 `84bad0dd8f35647bc51105cc21ec8ec8d40f57282b05383a2cea0920afc33a4d` |
| toolchain | pcbnew **9.0.9** / Python 3.12, zones refilled before DRC |
| method | path search delegated to `solar-8land-verify/route_solar_bitmap.py`; copper written, then graded by native DRC |

Router choice is deliberate: it is the only one in the repo carrying a negative
control (`negative_control.py` raises clearance to 1.50 mm and asserts the paths
change or lengthen). A router that cannot be made to refuse is not evidence.

## Native DRC — before vs after

```
violations          38 -> 38          multiset IDENTICAL
  new identities     0
  removed identities 0
unconnected items   86 -> 82
  /W1_SOLAR_N        5 -> 2
  /W2_SOLAR_N        5 -> 4
  /W3_SOLAR_N        5 -> 4
  /W1_SOLAR_P        1 -> 1   (untouched, not in scope)
```

Per-net counts are quoted rather than item identities because KiCad re-pairs the
remaining unconnected records of a net when copper merges equipotential groups:
the item-level list changes for reasons that are not defects (`86 → 83` and
`86 → 82` are both "no record that was connected became unconnected").

## The 5 that ship, and the 2 that do not

| # | net | pair | verdict | copper |
|---|---|---|---|---|
| 0 | `/W1_SOLAR_N` | `J_W1.4` ↔ `D_BP1.2` | **ROUTED** | 4 segs, 9.19 mm |
| 1 | `/W1_SOLAR_N` | `J_W1.4` ↔ `D_BP2.1` | **ROUTED** | 8 segs, 50.95 mm |
| 2 | `/W1_SOLAR_N` | `J_W2.1` ↔ `D_BP2.1` | **ROUTED** | 2 segs, 3.43 mm |
| 4 | `/W2_SOLAR_N` | `J_W3.1` ↔ `D_BP3.1` | **ROUTED** | 4 segs, 9.13 mm |
| 5 | `/W3_SOLAR_N` | `J_W3.4` ↔ `D_BP3.2` | **ROUTED** | 2 segs, 3.05 mm |
| 3 | `/W2_SOLAR_N` | `J_W2.4` ↔ `D_BP2.2` | **geometry exists, KILLED by the slot** | — |
| 6 | `/W3_SOLAR_N` | `J_W4.1` ↔ `D_BP4.1` | **geometry exists, KILLED by the slot** | — |
| 7 | `/W3_SOLAR_N` | `J_W4.1` ↔ `D_BP3.2` | **no B.Cu path** | — |
| 8 | `GND` | `U2.4` ↔ `D_BP4.2` | **needs a via** (`U2.4` is F.Cu-only) | — |

Pairs 0,1,2,4,5 reproduce #440's set exactly, from an independent implementation
of the write-and-grade step. Pairs 3 and 6 are where the reports disagree and
where this file adds something.

## Why pairs 3 and 6 cannot be routed — measured, not asserted

Each `J_W` footprint carries **four `Edge.Cuts` graphics forming a 6.0 × 0.5 mm
slot** cut into the board edge:

```
J_W1   (0.000,39.750)->(6.000,39.750)   (0.000,40.250)->(0.000,39.750)
       (6.000,39.750)->(6.000,40.250)   (6.000,40.250)->(0.000,40.250)   w=0.050
J_W4   (35.750,0.000)->(36.250,0.000)   (35.750,6.000)->(35.750,0.000)  ...      w=0.050
```

`J_W` pad 2 ends **0.05 mm** from that cavity. The DRC allow-list exempts the
`J_W` **pads** from `copper_edge_clearance`; it does **not** exempt a **track** —
that scoping is deliberate, and #440 records the same finding from the other side
("the allow-list scopes that rule to `J_W*` pads only, precisely so a TRACK at
the edge still fails").

Two ways to model the slot were tried, and the DRC result separated them:

| slot model | `copper_edge_clearance` |
|---|---|
| obstacle at track half-width (0.10 mm) | **+4** new, actual 0.10–0.18 mm |
| obstacle at the full 0.50 mm rule | **0** new — and pairs 3, 6 lose their only landing |

So the honest statement is: **pairs 3 and 6 have a corridor, and no legal
landing.** That is a design question, not a routing one, and it is left for a
decision:

- **(a)** extend the `.kicad_dru` exemption to tracks terminating on `J_W` lands, scoped to the
  terminating segment only — cheap, but it weakens an edge rule that exists for a
  reason, and needs an ADR;
- **(b)** change the socket geometry so the land is ≥0.5 mm from the cavity —
  correct, but it is a board respin;
- **(c)** accept 5 and route 3/6 in assembly, as the wing tab already bridges the
  faces mechanically.

No option is taken here. The board shipped at 5 pairs is the maximum that is
legal under the rules as written, which is a defensible place to stop.

## Reproduce

```sh
cd docs/analysis/hub-solar-route
# board copies + DRC, control board untouched
/usr/bin/python3 drc.py output/before/<board>.kicad_pcb
/usr/bin/python3 drc.py output/after/<board>.kicad_pcb
# independent route search with the tested negative control
cd ../solar-8land-verify && /usr/bin/python3 negative_control.py   # must print PASS
```

`output/before/drc-summary.json` and `output/after/drc-summary.json` in this
directory are the two summaries compared above; the `unconnected_ids` /
`violation_ids` multisets are the machine-readable form of every number here.
