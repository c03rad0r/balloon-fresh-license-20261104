# ADR-143 — H/V lane discipline: direction assigned by STACK POSITION, never by layer ID

**Status:** ACCEPTED — operator decision 2026-11-07: *"Don't make it a blocking gate for this
board. Make it an ADR that we follow going forward with future lanes we route. We can make it
blocking at a later point in the road map when this board has been completed and ordered from
JLCPCB."*
**Date:** 2026-11-07
**Supersedes:** nothing.
**Board under test:** `docs/analysis/bulk-route-20261107/latest.kicad_pcb`, sha256
`669ac850ac0992af82bb0ea0d51f364b68a7bc8672904e290891db444c46ed35` (28 opens).

---

## 1. The request

The operator proposed (2026-11-07) that odd-numbered layers carry horizontal lanes and
even-numbered layers carry vertical lanes, so that lanes on one layer run mostly parallel and
cross less. He asked how to put the practice into the existing tooling rather than leaving it
as a convention.

## 2. Why the request cannot be granted as stated

**Layer NUMBER is not stack POSITION, and on this board every copper layer is even.**

Measured from the board itself:

| stack position | layer name | KiCad layer ID |
|---|---|---|
| 1 | `F.Cu` | **0** |
| 2 | `In1.Cu` | **4** |
| 3 | `In2.Cu` | **6** |
| 4 | `B.Cu` | **2** |

"Odd = horizontal, even = vertical" therefore assigns **all four layers the same direction**.
The rule as phrased is not merely imprecise — it is inert. It must be expressed as stack
position.

## 3. The measurement that decides whether it can be adopted now

`tracker/hardware/hv_lane_audit.py`, read-only, on the board above. A track counts H or V if it
lies within ±22.5° of the axis; segments shorter than 1.5 mm are excluded as escapes, because
pad exits are never H or V and a rule without that exemption flags every fanout.

Proposed assignment: **F.Cu=H, In1.Cu=V, In2.Cu=H, B.Cu=V**.

| layer | H | V | DIAG | escape | proposed | conforms |
|---|---|---|---|---|---|---|
| `F.Cu` | 89 | 72 | 13 | 468 | H | 51.1 % (89/174) |
| `In1.Cu` | 0 | 0 | 0 | 1 | V | empty |
| `In2.Cu` | 1 | 0 | 3 | 1 | H | 25.0 % (1/4) |
| `B.Cu` | 52 | 58 | 5 | 549 | V | 50.4 % (58/115) |
| **whole board** | | | | | | **50.5 % (148/293)** |

**50.5 % is indistinguishable from random with respect to direction.** Enforcing this as a
blocking gate today would declare roughly half the existing copper illegal, so no commit could
pass. The rule does not describe this board; it contradicts it.

Copper distribution by track length: `F.Cu` 1173.0 mm, `B.Cu` 777.2 mm, `In1.Cu` **1.2 mm**,
`In2.Cu` **15.7 mm**. Two saturated outer layers and two effectively unused inner layers. That
asymmetry — not the six remaining opens — is the structural problem, and it is what makes
corridors 0.30 mm wide.

## 4. Decision

**ACCEPTED by the operator 2026-11-07.** The rule applies to **lanes we route from now on**.
It is NOT retrofitted onto this board and NOT a blocking gate until this board is complete and
ordered from JLCPCB.

1. **Adopt the discipline, expressed by stack position:** `F.Cu`=H, `In1.Cu`=V, `In2.Cu`=H,
   `B.Cu`=V. Never by layer ID. This is the standing rule for **future routing**.
2. **Do NOT enable it as a blocking gate on the current board.** It starts at 50.5 %, and the
   board is under an active reviewer (Astra, CHANGES_REQUESTED). Retrofitting direction onto
   routed copper is a rewrite, not a tidy-up.
3. **Ship the checker in report-only mode now**, wired into the existing board-gate hook, and
   record 50.5 % as the baseline so regressions are visible without blocking progress.
4. **Enable strict mode only after this board is complete and ordered from JLCPCB.** That is the
   operator's stated trigger. Until then, no commit may be refused on H/V grounds.
   When the trigger is reached, flip the hook entry to pass `--strict` (see section 5) and record
   the achieved figure as the new baseline — do not assume it will be high on this board.

## 5. Enforcement, and why it is a gate rather than prose

The operator's standing rule is that "always X" becomes a mechanical gate, not a convention.
Therefore:

- `tracker/hardware/check_hv_lanes.py` — the audit, with an exit code: 0 = pass/report-only,
  1 = strict violation.
- `scripts/git-hooks/pre-commit-board-gates.py` — invokes it on every commit touching a board.
  In report-only mode it prints the conformance figure and the worst offenders but never
  blocks. A `--strict` flag (or a per-board baseline file) turns it into a refusal.
- The exemption is part of the rule, not an escape hatch: segments **< 1.5 mm** are exempt, and
  that number is justified by measurement (1018 escape segments exist on this board; a rule
  without the exemption flags all of them).

## 6. What would change this decision

- A fresh layout routed with the discipline from the start, reaching >90 % conformity without
  the escape exemption — then strict mode is safe to enable everywhere.
- Evidence that H/V assignment *hurts* on this stackup, e.g. a 4-layer route that fits more nets
  with free direction than with H/V. The inner layers are currently empty, so this is untested.
- A second board in this project family that already conforms, which would suggest the 50.5 %
  here reflects this board's history rather than the practice.

## 7. For future sessions

- Rule: direction is a property of **stack position**, not layer number.
- **Apply it when routing NEW lanes.** This is the accepted practice from 2026-11-07 onward.
- Audit: `python3 tracker/hardware/hv_lane_audit.py` (reads `latest.kicad_pcb`, prints the
  table above).
- Reproduce the numbers: the script is self-contained and read-only; it needs only `pcbnew`.
- Current baseline on this board: **50.5 %**. The hook runs the checker WITHOUT `--strict`, so it
  prints that figure and never blocks.
- **Trigger to make it blocking:** this board complete AND ordered from JLCPCB (operator,
  2026-11-07). At that point change the `GATES` entry in
  `scripts/git-hooks/pre-commit-board-gates.py` from `("check_hv_lanes.py", [])` to
  `("check_hv_lanes.py", ["--strict", "--min", "90"])` and re-record the baseline.
  Do not flip it earlier; at 50.5 % it would refuse every commit on an in-review board.
