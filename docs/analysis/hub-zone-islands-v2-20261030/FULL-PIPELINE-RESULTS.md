# Full-pipeline coverage and endpoint proof — measured

Supersedes the "coverage pending" caveat carried in the earlier report revision.

## Command that produced these numbers

```sh
/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/pr380-coverage-venv/bin/python \
  pipeline_coverage.py --out <workdir>
```

Every stage returned **exit 0**, on `repo` = current `master` and the source board
at SHA256 `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`
(re-asserted inside `islands.json`: `source_unchanged: true`,
`refill_byte_noop: true`).

| stage | rc |
|---|---|
| inventory | 0 |
| stitch | 0 |
| endpoint | 0 |
| tests | 0 |

## Coverage: 88% total — the ≥80% gate is met

| module | stmts | miss | branch | brpart | cover |
|---|---:|---:|---:|---:|---:|
| `endpoint_proof.py` | 134 | 12 | 52 | 12 | **87%** |
| `run_island_inventory.py` | 447 | 39 | 220 | 31 | **88%** |
| `validate_stitching.py` | 70 | 4 | 16 | 4 | **91%** |
| **TOTAL** | **651** | **55** | **288** | **47** | **88%** |

Statements 92%, branches 80%. Raw JSON: `full_pipeline_coverage.json`.
This replaces the earlier unit-only figure (22%) that was quoted when only the
handful of pure-unit tests were measured.

## Endpoint proof: 22 of 29 arms proven, 7 not

From `endpoint_validation.json` (all arms re-derived from hash-verified candidate
boards; `native_per_island_proven: false` — see limitation below).

| geometric endpoint → pinned main | no new native violation identities | arms |
|---|---|---:|
| true | true | **22** |
| true | false | 1 |
| false | true | 3 |
| false | false | 3 |

`verdict` field: **22 × `GEOMETRIC_MAIN_JOIN_NATIVE_LEGAL_SAMPLE`**,
**7 × `SAMPLED_CANDIDATE_NOT_PROVEN`**.

Per-arm checks that had to hold together for the 22: the exact target island
reaches the **pinned original** main-component member set, the complete
after-refill partition equals the before-partition with exactly those two
components joined, and a control graph of the after-refill copper **excluding the
new via** reproduces the original partition (ruling out reassignment caused by
refill alone).

## The limitation that remains, stated plainly

`native_per_island_proven` is **false for every arm**:

> Installed pcbnew SWIG bindings do not expose usable per-filled-polygon
> component membership; native crosscheck is aggregate only, not endpoint proof.

So the 22 are **geometric** proofs cross-checked against native aggregate counts —
not native per-island membership. They are not a fabrication approval and they are
not a batch approval: 22 independently-passing single-via sites do not prove a
combined layout. `connectivity_proven` is false on all 29 arms, deliberately.

## Aggregate crosscheck (still holds)

35 filled islands · 29 provisionally isolated · Σ(components−1) = **86** over
**22** affected nets · native unconnected = **86**.
