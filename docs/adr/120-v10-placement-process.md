# ADR-120 — v10 placement process: two-sided population, minimal outline, human placement gate, visual-first reporting

- **Status:** ACCEPTED — operator instruction, 2026-10-20 ("lock these decisions in as ADRs"; process rules first recorded in ADR-118 §Process, split here per one-decision-per-ADR convention).
- **Decision owner:** Felix (operator)
- **Related:** ADR-118 (v10 umbrella), ADR-119 (radio sites), ADR-030 (deterministic zero-inference placement), ADR-085 (wing-slot seats constrain the outline).

## Decision

Four **binding process rules** for v10 (and the default posture for later boards):

### R1 — Two-sided population

Parts are distributed over **both sides** of the board. The digital/harvest section occupies the front; the radio sites (ADR-119) occupy the back, away from digital noise. RF-module keep-out rules (e.g. E28 manual §4.1) apply on **both sides** at each module site.

**Precedence (2026-11-10, operator-approved):** R1 states the *default to measure*, not an unconditional rule. The operative density rule is **`AGENTS.md` §1b Board density**: every placement milestone computes the smallest outline **both** single-sided and two-sided and adopts two-sided when it earns **≥10 % of board area**. Staying single-sided after a threshold win requires a **recorded operator decision** weighing assembly cost against the saved area — never an agent's shorthand. Measured counter-example that motivated this: on the 65 × 50 mm pressure-controller candidate, a 197.6 mm² "largest empty area" figure was read as proof that a second side would buy nothing; a two-sided placement then measured **52 × 46 mm, 26.4 % smaller**. "Is the single-sided board packed?" and "would a second side buy a smaller outline?" are different questions and only the second decides the board.

### R2 — Minimal outline

The outline shrinks to the surface the two-sided placement needs. Legacy outlines (70×70 v9) are **not** constraints. The wing sockets (ADR-085: four edge seats) frame the outline shape. Measured first pass: **52×62 mm = 3224 mm², 34% smaller than v9** — subject to the R3 gate.

### R3 — HUMAN PLACEMENT GATE (not skippable)

Placement is rendered (front + back) and shown to the operator **in Signal** for sign-off **before any routing begins**. Operator's words: *"This human gate is important and not to be skipped."*

Mechanics:
- Renders are produced from **measured courtyard sizes** of the real footprints (not guessed rectangles) wherever the footprint already exists in-repo; datasheet dimensions for new parts (E28).
- The placement is checked programmatically (overlap-free, in-bounds, wing-seat clearance) **and** reviewed visually before it is shown.
- **Routing work started before gate sign-off is a defect**, not initiative. If routing is found to have begun on an ungated placement, the routing is discarded and the gate re-run.
- Gate verdicts are recorded (date, operator, outcome) in the v10 build log.

### R4 — Visual-first reporting

Every substantive board claim made to the operator ships **with a rendered image in the same message** (3D view, copper/silk plot, or annotated crop, delivered in Signal). Operator's words: *"No more talking about something on the circuit board without showing me what you're talking about."*

Text-only board reports are a **process violation**. The image-freshness pre-commit hook (PR #250) enforces that committed renders match the board on disk.

## Enforcement summary

| Rule | Enforced by |
|---|---|
| R1 both sides | v10 placement generator + gate renders show both sides |
| R2 minimal outline | outline size printed on every gate render; v9 sizes rejected by the generator |
| R3 placement gate | no-routing-before-signoff checked in review; gate verdicts logged |
| R4 visual-first | Signal delivery habit + image-freshness pre-commit hook |

## Reproduce

```
python3 /tmp/v10_render2.py   # gate render generator (to be moved into tracker/hardware/ with the real build)
```
