# ADR-146 — v11: move the four wing bypass diodes `D_BP1..D_BP4` to the top side

**Status:** PROPOSED for v11. **Not applied to v10.** Operator directive 2026-11-09: *"lets move the
diodes to the top in the next version of the board."*

## The decision this records

On v10 the four wing bypass diodes are **bottom-side only**, which forces the assembly order into
one of two bad shapes:

| option | setup fee | what it costs you |
|---|---|---|
| double-sided Standard PCBA | **2 × $25 = $50** | money |
| top-only + hand-solder the diodes | **$25** | four SMA joints |
| (chosen) top-only, diodes by hand | **$25** | four SMA joints |

v10 ships top-only with the operator hand-soldering `D_BP1..D_BP4`. That is the right call for this
order — but it exists only because the parts sit on the back. On v11 they should not.

## Why they are on the bottom today

Not a decision — an artifact. Measured on `work.kicad_pcb`:

| ref | position (mm) | rotation | copper layers |
|---|---|---|---|
| `D_BP1` | (4.0, 33.0) | 0° | B.Cu only |
| `D_BP2` | (29.0, 76.0) | −90° | B.Cu only |
| `D_BP3` | (68.0, 33.0) | 0° | B.Cu only |
| `D_BP4` | (29.0, 4.0) | −90° | B.Cu only |

All four are **SMA (SS24)**, one at each wing corner, straddling the boundary between adjacent
wing power nets: `/W1_SOLAR_P↔N`, `/W1_N↔W2_N`, `/W2_N↔W3_N`, `/W3_N↔GND`. They are bypass diodes
across the wing interconnect, so they belong electrically at the wing tabs — but there is no
requirement that they be on the reverse face.

`FINDING-cpl-coordinate-transform.md` flagged that bottom-side rotations were never verified
against JLCPCB's convention. That was checked numerically on 2026-11-09 and **passes**: applying
the CPL rotation to the footprint's pad-1 offset lands on the real pad 1 with 0.000 mm error on all
four, counter-clockwise. So the v10 bundle is correct — the problem is cost and handling, not
placement.

## Why moving them is not a v10 change

Flipping a footprint to the top is trivial. **Reconnecting it is not:** the pads are B.Cu-only, so
each diode needs two new top-side connections — eight in total — on a board whose only signal
layers are F.Cu and B.Cu and both carry full pours.

Measured clearance from where a top-side pad would go to the nearest F.Cu copper on the *same* net
the pad must join:

| part | pad | net | nearest same-net F.Cu copper |
|---|---|---|---|
| `D_BP1` | 2 | `/W1_SOLAR_N` | **10.15 mm** |
| `D_BP3` | 1 | `/W2_SOLAR_N` | **10.53 mm** |
| `D_BP2` | 1 | `/W1_SOLAR_N` | 4.99 mm |
| `D_BP1` | 1 | `/W1_SOLAR_P` | 2.26 mm |

Two of the eight connections are ~10 mm of fresh trunk across congested copper. On this board that
is the same class of run that the router has already failed on `/EN`, `/IO0` and `/F33_VSENSE`
(43.7 mm across two poured layers). The top side is also not empty at those sites: `/W3_SOLAR_N`
copper passes **0.07 mm** from `D_BP3`'s position.

So a v10 flip trades a $25 fee for eight new connections with a real chance of a half-finished
route, which is worse than either paid option.

## What v11 must do

**Place `D_BP1..D_BP4` on the top side at layout time**, and route them at layout time — not as a
retrofit.

The four sites are already clear: measured, **zero top-side footprints within 6 mm** of any of the
four positions. The corners are structurally free; the parts simply were never put there.

Consequences for v11:

- **Assembly becomes single-sided.** One setup fee instead of two, on any PCBA tier.
- `U1` and the diodes are placed together, so the Standard-vs-Economic choice stops being entangled
  with diode population.
- The wing bypass function is unchanged — the nets are the same, only the face changes.

## Corollary for the current order

v10 ships **top-only** (`docs/fab/v10-order-top-only/`, 19 placements, 19 Top / 0 Bottom).
`D_BP1..D_BP4` are listed in `hand-fit-NOT-FOR-JLC.csv` with the reason stated, so they cannot be
lost. The operator solder four SMA parts, two pads each, 4.00 mm apart, marked on the bottom
silkscreen.

## Reproduce

```
/usr/bin/python3 - <<'PY'
import pcbnew, math
b = pcbnew.LoadBoard('docs/analysis/bulk-route-20261107/work.kicad_pcb')
for ref in ('D_BP1','D_BP2','D_BP3','D_BP4'):
    fp = b.FindFootprintByReference(ref)
    q = fp.GetPosition()
    print(ref, f'({pcbnew.ToMM(q.x):.1f},{pcbnew.ToMM(q.y):.1f})',
          f'rot={fp.GetOrientationDegrees():.0f}',
          'top' if not fp.IsFlipped() else 'bottom')
PY
```

`pcbnew` lives in the **distro** python (`/usr/bin/python3`), not the project venv.

## What would change this decision

Nothing electrical. If a future revision needs the bottom face for something else — an antenna
keep-out, a battery, a stiffener — then top-side diodes are mandatory rather than merely cheaper,
and this ADR becomes a precondition rather than an optimisation.
