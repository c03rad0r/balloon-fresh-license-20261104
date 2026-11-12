# ADR-142 — The wing-socket edge exemption does NOT extend to tracks, and must not

**Status:** ACCEPTED — operator decision 2026-11-03 ("accept and continue"). **No rule file has been edited.**
**Date:** 2026-11-03
**Supersedes:** nothing. **Extends the record of:** `docs/fab/EDGE-EXEMPTION-MECHANISM.md`
(2026-10-16).
**Board under test:** `hub_board_v10_lora1280_7of9.kicad_pcb`, sha256 `60ffd763…4cd5`
(the 7-pair intermediate from the solar-route work; it is the only board in the
investigation that actually carries tracks at the socket edge).

---

## 1. The decision that was requested

The operator asked to **"extend `.kicad_dru` to terminating tracks"** so that the two
remaining solar-return pairs (`J_W2.4 ↔ D_BP2.2`, `J_W4.1 ↔ D_BP4.1`) could be routed
on `B.Cu` instead of being waived to assembly.

## 2. Why that request cannot be granted as stated

**It is not that the exemption is hard to scope. No `.kicad_dru` form reaches a track at
the socket edge at all.** Seven condition forms were measured against native
`kicad-cli pcb drc` (KiCad 9.0.9), zones refilled, one board, one run each
(`tracker/hardware/dru_edge_form_sweep.py`):

| # | rule form | `copper_edge_clearance` | track-at-edge items waived |
|---|---|---|---|
| A | no `.kicad_dru` at all (control) | 20 | 0 of 4 |
| B | **conditionless** `edge_clearance (min 0.00mm)` | **4** | **0 of 4** |
| C | `A.Type == 'Track'` | 20 | 0 of 4 |
| D | `A.Type == 'Track' && A.NetName == '/W1…'/…` | 20 | 0 of 4 |
| E | `A.Reference == 'J_W1' \|\| …` (the existing form) | 20 | 0 of 4 |
| F | `B.Type == 'Track'` (opposite pair side) | 20 | 0 of 4 |
| G | `A.Type == 'Track' \|\| B.Type == 'Track'` | 20 | 0 of 4 |

**B is the decisive row.** A conditionless rule is the widest possible waiver — it can
match nothing *except* by failing to load, and it demonstrably loads and executes here:
it removes all 16 pad items (20 → 4). Yet **every one of the 4 track items survives it.**

So the limit is not in the condition language, and there is no further form to try.
This also **corrects** the earlier reasoning in `EDGE-EXEMPTION-MECHANISM.md`: that
document attributes the pad-item residue to "rule-applicability", implying tracks were a
matter of scoping. They are not. A custom rule cannot suppress a track-vs-edge item.

## 3. And the underlying claim was wrong anyway

The pairs were described as having "no legal landing" because the land sits ~0.05 mm from
its socket cavity. Measured, the actual geometry is a **crossing**:

| net | segment (mm) | nearest edge | copper-to-edge gap | rule needs |
|---|---|---|---|---|
| `/W2_SOLAR_N` | (66.55, 41.65)→(66.55, 33.55) | `J_W3` | **−0.100** | 0.500 |
| `/W2_SOLAR_N` | (37.80, 79.35)→(30.30, 79.35) | `J_W2` | **−0.095** | 0.500 |
| `/W3_SOLAR_N` | (37.80, 0.60)→(30.30, 0.60) | `J_W4` | **−0.095** | 0.500 |
| `/W1_SOLAR_N` | (5.35, 41.80)→(5.35, 33.55) | `J_W1` | **−0.092** | 0.500 |

A **negative gap means the track crosses the edge line** — these are not copper sitting
0.05 mm too close; each runs straight across the 6.0 × 0.5 mm socket cavity and lands on
the pad on the far side. The pads are on the *opposite* side of the cavity from the
board interior (`J_W1` pads span y 36.70–43.30; the cavity is y 39.75–40.25). Reaching a
pad from inside the board therefore *requires* crossing the cavity.

**Any exemption that would wave these tracks through would be approving a track that is
physically cut by a board edge.** No ADR should do that.

## 4. Decision

**Do not extend the edge exemption to tracks. Do not edit any `.kicad_dru`.**

The exemption stays exactly as it is: pads of the edge-launched wing sockets, and
nothing else. The 5 routed pairs stand. Pairs 3 and 6 (`J_W2.4↔D_BP2.2`,
`J_W4.1↔D_BP4.1`) and pair 7 (`J_W4.1↔D_BP3.2`) are **not routable in board copper at
any rule setting**, because the geometry demands crossing a board edge.

They are completed **in assembly**, which is what the wing tab already does: ADR-120 R1
and `WING-TO-HUB-SOCKET-SPEC.md` §2 specify SMD lands on *both* faces so the tab bridges
F and B when soldered. The two-cent land sets exist precisely so the tab, not a track,
makes the connection at the edge.

## 5. Alternatives, and why they were rejected

| alternative | verdict |
|---|---|
| **(a) conditionless / net-scoped track exemption** | **REFUSED — measured impossible** (§2) and would approve copper cut by a board edge (§3) |
| **(b) socket respin: move the land ≥0.5 mm from the cavity** | **technically real, refused for this build** — it is a board respin for two pads whose connection the tab already makes; no functional gain, and it invalidates every routed board in the investigation |
| **(c) accept 5 pairs; tab bridges 3, 6, 7 in assembly** | **ACCEPTED** — matches the specified interface and the shipped state |

## 6. What would change this answer

- A socket respin that puts the land on the interior side of the cavity, **or** a
  through-slot land that bridges both faces by construction (this is a real option and
  belongs to a v11 interface review, not to a rule file).
- Evidence that the wing tab does **not** bridge F/B at these lands. ADR-120 R1 and the
  socket spec say it does; if a first-article inspection showed a cold joint or a gap, the
  assembly path would fail and (b) would become mandatory.

## 7. Reproduce

```sh
cd docs/analysis/hub-solar-route   # or any checkout with the board
/usr/bin/python3 tracker/hardware/dru_edge_form_sweep.py <board>.kicad_pcb
```

Writes per-form reports under `~/.hermes/profiles/manager/cache/scratch/solar-fix/dru-forms/`
and prints the seven-row table in §2. The board is copied per form and never edited.

## 8. References

- `docs/fab/EDGE-EXEMPTION-MECHANISM.md` — the 2026-10-16 measurement this ADR extends
  (24 → 16 conditionless; reference conditions inert). **Its §"residual" reasoning is
  superseded on one point:** see §2 above, tracks are unreachable by any rule, not merely
  by `Reference`.
- `docs/fab/handoff/hub_board_v9.kicad_dru` — the live exemption, **unchanged by this ADR**.
- ADR-120 R1 — two-sided wing lands; the tab solders from both faces.
- `docs/WING-TO-HUB-SOCKET-SPEC.md` §2 — SMD lands on both outer faces.
- ADR-046 / ADR-048 — the wing sockets are edge-launched by design.
- `solar-8land-verify/APPLIED.md`, `hub-solar-route/REG-RADE.md` — the 5-pair applied state
  and the two-pair analysis this ADR rules on.
