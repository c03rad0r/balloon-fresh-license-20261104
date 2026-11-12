# Solar gaps: 7 of 9 closed by a single B.Cu track, 2 need a via — measured, gate-verified

Follow-up to `docs/analysis/hub-solar-audit/FINDINGS.md` (master, `e27f39c0`), which established the
root cause: `Wing_Tab_4P` defines each pad **number** twice, once per outer face, so every
diode↔J_W pair **does** share `B.Cu`, and the "not board-fixable" verdict was an artefact of a
measurement error.

This report answers the next question: **with that structure understood, do the routes exist?**

Board: `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`, sha256 `732bfe88…`, read-only.
KiCad 9.0.9. Rules as supplied: clearance 0.20, track 0.20, edge 0.50, via 0.50.

## Result

| pair | net | ends | result |
|---|---|---|---|
| 0 | `/W1_SOLAR_N` | `J_W1.4` → `D_BP1.2` | **PATH 11.87 mm, 0 vias** |
| 1 | `/W1_SOLAR_N` | `J_W1.4` → `D_BP2.1` | **PATH 52.34 mm, 0 vias** |
| 2 | `/W1_SOLAR_N` | `J_W2.1` → `D_BP2.1` | **PATH 5.59 mm, 0 vias** |
| 3 | `/W2_SOLAR_N` | `J_W2.4` → `D_BP2.2` | **PATH 12.18 mm, 0 vias** |
| 4 | `/W2_SOLAR_N` | `J_W3.1` → `D_BP3.1` | **PATH 11.78 mm, 0 vias** |
| 5 | `/W3_SOLAR_N` | `J_W3.4` → `D_BP3.2` | **PATH 4.78 mm, 0 vias** |
| 6 | `/W3_SOLAR_N` | `J_W4.1` → `D_BP4.1` | **PATH 12.18 mm, 0 vias** |
| 7 | `/W3_SOLAR_N` | `J_W4.1` → `D_BP3.2` | **NO PATH on B.Cu** — blocked |
| 8 | `GND` | `U2.4` → `D_BP4.2` | **no B.Cu pad at `U2.4`** — needs a via |

**7 of 9 need nothing but a single B.Cu track.** No via, no layer change, no land change, no netlist
change. Pairs 7 and 8 still need work; both are characterised below.

## The negative control that changed the answer

An earlier run of the same router reported **8 of 9**, including pair 7 at 47.91 mm. That run was
wrong, and a deliberately-failing test proved it:

```
=== clearance 1.50 mm on pair 2 (must FAIL or get much longer than 5.59 mm) ===
PATH 5.59 mm ... length at 1.50 mm clearance = 5.59 mm vs 5.59 mm at 0.20
   -> SAME LENGTH: rule NOT applied
```

The endpoint "clearance exemption" was a 2.5 mm **disc** around each pad, and pair 2's pads are
5.59 mm apart — so the two discs covered nearly the whole route. The path existed only inside
exempted space, i.e. it was not a route. The exemption now applies **only to the board-edge rule**,
and only under the endpoint pad's own body (the J_W lands sit on Edge.Cuts by design; the repo's own
DRC allow-list scopes `copper_edge_clearance` to exactly those refs). With that fixed:

```
RESULT: PASS -- router discriminates     (all three controls)
```

Pair 7 then correctly reported NO PATH, and pair 0 moved 11.78 → 11.87 mm — small changes, because
the paths near the pads were no longer free.

**This is the third time in this investigation that a test that can say NO found the defect**, after
the phantom 4 mm pad disc and the doubled pad fill. The pattern is consistent enough to state as a
rule: a router result is not evidence until a negative control shows the router refusing.

## Pairs 7 and 8, characterised

- **Pair 7** (`J_W4.1` ↔ `D_BP3.2`, `/W3_SOLAR_N`): both ends are B.Cu, and a 0.20 mm track at
  0.20 mm clearance does not get through in the corridor that spans the two pads 43 mm apart. Needs
  either a via-assisted path (two layers) or the pour geometry changed at one end.
- **Pair 8** (`U2.4` ↔ `D_BP4.2`, `GND`): `U2.4` carries copper on **F.Cu only**, `D_BP4.2` on
  **B.Cu only**, so they share no layer at all — a via is structurally required, unlike the others.
  This is the one pair where the original "different layers" reasoning was correct.

## What this does and does not establish

**Does:** the seven routes exist as single-layer B.Cu copper at the board's supplied rules, verified
by a router whose refusal behaviour is itself tested.

**Does not:** this is geometry, not a DRC result. The paths are not on the board — applying them means
writing copper, refilling zones, and re-grading with `kicad-cli pcb drc`. It also does not decide that
routing these is the right engineering call; master's audit records that the nets were never routed in
any commit, which makes routing them the obvious completion rather than a new decision.

## Reproduce

```sh
cd docs/analysis/solar-8land-verify
export PYTHONPATH=/usr/lib/python3/dist-packages
/usr/bin/python3 verify_jw_lands.py  ../../tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb
/usr/bin/python3 route_solar_bitmap.py ../../tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb --grid 0.15
/usr/bin/python3 negative_control.py     # must print PASS -- router discriminates
```
