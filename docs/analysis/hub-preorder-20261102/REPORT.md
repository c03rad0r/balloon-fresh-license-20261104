# Hub pre-order prerequisite milestone — 2026-11-02

**NOT ORDERABLE. Milestone: recovered same-board blocker ledger and measured model inventory.**
No source copper, footprint, library or project file changed. No order, upload to a fabrication service, routing, refill or PR380 pipeline restart was performed.

## Source binding and reproduction

Fetched `origin/master` at `4ade5900`. Its canonical board matches the PR380 source exactly:
`tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`, SHA256
`732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.
Project SHA256: `01063b32bcba962ba2ee89fa5acbd55a96b006d78567a3037403b05965a75b02`.

```
/usr/bin/python3 docs/analysis/hub-preorder-20261102/measure.py \
  --out docs/analysis/hub-preorder-20261102/evidence.json
```

Exit **0**, source hashes before/after identical. `evidence.json` includes every saved non-connectivity violation, its descriptions/positions, per-footprint model declarations and existing model hashes. DRC counts are **recovered from the saved same-board audit**, not a fresh DRC run. That audit's copy-refill preserved the source hash and DRC exited **5**, not clean. See `../hub-endpoint-audit-20261030/{manifest.json,commands.json,drc.json,readiness-audit.md}`.
The script refuses a different PCB hash. Existing model paths use this host's KiCad9 installation; model file existence is not geometry, origin, orientation, licensing or visual correctness approval.

## Highest-value next prerequisite: solve the wing socket's own edge geometry

All **16** edge violations in the saved same-board report are **J_W1–J_W4**, pads **2 and 3**, each on **F.Cu and B.Cu**, against **a Segment of the same footprint on Edge.Cuts**. Each reports **0.0500 mm actual against 0.5000 mm required**.

This corrects the older task premise that J_HUB_PV/J_PROG share these 16 errors. They do not appear in this class. It also changes the proposed repair: **moving the entire wing connector inward, including its footprint-owned Edge.Cuts, cannot change its pad-to-own-edge distance**. Both objects translate together. The deficit is **0.45 mm**, but that is not a validated footprint displacement or a signed movement vector.

Next repair prerequisite: review the four socket land patterns and mating counterpart dimensions together. Determine whether the approved inward move means pads/body only against a fixed cut, or whether the routed notch/contact geometry must change. Preserve insertion reach/contact overlap; measure route/courtyard impact on an isolated candidate. A pad shrink is not automatically acceptable: it changes the electrical contact land. No blanket edge exception, part movement or waiver is justified by this milestone.

Acceptance: same-rule copy-only DRC with these 16 records eliminated, no new violations, component partition no worse, protected U1↔LoRa1280 paths preserved, and measured mating contact geometry approved. Only then apply a reviewed source revision. This prerequisite is independent of completing island attribution.

## Exact action ledger

| Priority | Blocker | Recovered evidence | Next action / acceptance | Copper/hash effect |
|---|---|---|---|---|
| P0 | Connectivity | 86 minimum joins across 22 nets in prior endpoint partition; 86 saved DRC records | Finish existing PR380 corrected partition/stitch evidence; review intentional/external connections by endpoints, then route real component joins. Never compare DRC list indexes. | Later repairs change copper/hash; no claim of 22 freshly proven stitches |
| P0 | Socket edge geometry | 16 records, four sockets, own footprint cuts, 0.05 vs 0.50 mm | Resolve pad/cut/mating construction as above before route work around connectors | Physical change; re-freeze required |
| P1 | Thermal U_LORA1280.14 and J_PROG.1 | F.Cu GND, one spoke each vs minimum two | Measure clearance-constrained spoke/track/via candidates, copy-refill and DRC; preserve protected operator paths | Copper changes; existing measurements do not prove an acceptable site |
| P1 | Eight unresolved library identities | tracker_mechanical: J_W1–4; NiceRF: U_LORA1280; balloon_flight_v10: U2/U_C/U3 | Recover/parse authoritative .kicad_mod; add exact project nicknames only after provenance review; rerun library comparison | Table-only fix can preserve board bytes, changes audit environment |
| P1 | Eleven library mismatches | H1–4/HW1–4 (8), C_CAP1/2 (2), J_VCC (1) | Compare embedded versus authoritative land patterns; classify intended customisation. Do not Update All Footprints | Library-only adjudication may preserve board; replacements may alter copper |
| P2 | Three silk collisions | U_LORA1280: two graphic segments, one footprint reference text | Move reference deterministically; move offending graphic strokes to Fab per project policy, not trim. Copy-check against mask | Non-copper PCB edits change PCB hash; **not all three are text-only** |
| P1 | Model/body coverage | 49 footprints; 34 with declarations, 29 with at least one existing file | Resolve missing populated IC/module bodies and validate transforms before mechanical sign-off; classify intentional no-body footprints | Render/package dependency; no electrical repair |
| P1 | Package provenance | No same-hash current-board reference found in docs/fab in this checkout | After final source revision, generate Gerber/drill and optional PCBA BOM/CPL with source/rule/library hashes; verify layer/drill contents and population parity | Release cannot reuse historical v9 package by name |

The connectivity ledger has no approved intentional waivers. The ADR-136 versus fabrication-order-readiness interpretation of wing/cut-sense gaps must be resolved explicitly before any waived join. Nine U1↔U_LORA1280 signal paths were proven in the prior endpoint audit; that is not whole-board readiness. Do not reroute a proven path merely because its shared net has another disconnected branch.

## Recovered task state (not assumed running)

Prior session had dispatched a DRC repair plan and an edge relocation study. Local recovery found:
- `~/worktrees/hub-drc-plan-97918`: detached at baseline, only untracked probe scripts and `footprints/nicerf.pretty/`; no committed repair-plan report. These are **unreviewed partial work**, not accepted fixes. The probe's home-global-library aggregation and simplified pad equivalence are not authoritative KiCad parity.
- `~/worktrees/edge-reloc-study`: clean at baseline, no relocation study artifact found by filename search; no completed measured displacement or mating proof recovered.
- No corresponding repair-plan/connector-study PR was found among the latest 20 repository PRs. This bounded search does not establish that none exists elsewhere.

Therefore neither is represented here as a live worker or completed prerequisite. Salvage the existing scripts only after review; do not wait for those historical jobs.
PR380 corrected pipeline belongs to the parent session; its scratch files were only inventoried, never modified or restarted. Its final verdict is intentionally **not** inferred from partial files.

## Model inventory and package limits

Fresh board load: **49 footprints**, **34 with model declarations**, **29 with at least one resolvable model file on this host**. This is file coverage, not 29 verified bodies.

- Declared but unresolved: **U1, U3, U5, U_C, U_HUB_CVT**.
- No model declaration: **U2, U_LORA1280, J_VCC, J_W1–4, H1–4, HW1–4**. Holes and contact-only footprints may legitimately need no solid body; do not inflate these into 15 defective components.
- Existing `~/reports/hub-current-visuals/732bfe889020/` pictures are useful views, not complete mechanical certification. No new visual verdict is claimed here.

The `docs/fab` search found no reference to this current canonical filename or its pinned hash. This is a **provenance gap**, not proof that no package exists elsewhere. Existing v9 handoff files are not certified for this board. No fabrication packet was generated now because copper remains blocked and it would immediately become stale.

After copper/edge/thermal review and fixes: freeze the exact board/project/libraries → refill-copy/direct DRC and component partition → library parity/silk → stackup, drill/via process and RF review → schematic/netlist and population checks → generate/hash Gerber/drill/BOM/CPL → verify models and mechanical assembly → human final visual sign-off. Bare-board fabrication and assembled PCBA remain different deliverables. No current price or stock availability is claimed.
