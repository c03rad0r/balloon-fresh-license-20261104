# Geometry continuation milestone (2026-11-02)

Analysis-only; source copper is unchanged. Not a stitch or fabrication approval.

## Decisions and measured evidence

- Salvaged the interrupted native polygon conversion and five real-pcbnew regression tests, rather than restarting. Native shape tessellation replaces arc chords, filled-circle surrogates and bounding-box pad fallbacks. Drill voids are subtracted, including slotted pad drills.
- Refuse unsupported Edge.Cuts curves instead of treating their bounding boxes as edges. Rectangles now use their geometric centerline, not their stroke-expanded bounding box. The pinned board has 17 supported edge shapes.
- Include net-bearing footprint copper graphics in the conductive graph. Only plated pads and vias bridge layers; unsupported nonplated multilayer items fail closed.
- Six native filled contours have self-retraced rings. Normalize with make_valid only if exactly one polygon remains and area differs by at most 1e-8 mm²; refuse splits/area loss instead of unrestricted buffer(0). This remains a geometric normalization, not native component membership.
- Preserve outline identities by rejecting empty/degenerate outlines instead of silently skipping them.
- Require the complete zero-contact partition to equal the 0.004 mm partition before classification. Real pinned-board execution: 1149 items, 139 components; both tolerances give 86 missing connections across 22 nets and identical full membership partitions. Existing endpoint proof retains pinned original main membership, complete after-partition comparison and no-via control.

## Verification

`/usr/bin/python3 -m unittest discover -s docs/analysis/hub-zone-islands-v2-20261030 -p 'test_*.py'`: **34 passed**.

Measured unit-only branch-enabled coverage (coverage.py 7.17.0):

| Module | Statements | Missed | Branches | Combined coverage |
| --- | ---: | ---: | ---: | ---: |
| inventory | 452 | 361 | 222 | 16% |
| native stitch experiments | 70 | 56 | 16 | 17% |
| endpoint proof | 134 | 76 | 52 | 42% |
| Total | 656 | 493 | 290 | 22% |

This is **not whole-pipeline coverage** and not proof completeness. `pipeline_coverage.py` now stages a fresh isolated repository and measures actual inventory → native stitch experiments → endpoint proof → tests. Long-running execution is pending; no completed whole-pipeline result is claimed. Scratch run `pr380-pipeline-corrected` predates only the inventory's explicit zero-contact gate (the equivalent real-board full partition comparison was run separately).

## Review and limitations

Bounded cold reviews requested via the project's localhost:9099 router. Served models were `deepseek-v4.1-flash` and `kimi-k2.7-code`; both returned truncated analysis without a final verdict within their response budgets. **No completed independent review or approval is claimed.** Their concrete outline-index concern was addressed by rejecting skipped outlines. Their annulus-vs-disk candidate-landing concern remains: candidate predictions are not approvals; real after-refill partition proof is still required.

Other limitations: fixed four-layer scope; unsupported curved Edge.Cuts fail closed; 1 nm inscribed tessellation is not exact analytic copper; same-net footprint graphics are conservatively included in candidate obstacles; candidate search is sampled, not exhaustive. Native per-polygon membership remains unavailable. No ADR-136 unused-pad exception is inferred to authorize isolation. Prior 22 conservative joins are historical evidence, not a newly revalidated count under this geometry revision.

Pinned PCB SHA256: `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.
