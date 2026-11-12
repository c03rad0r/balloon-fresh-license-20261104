# Unconnected classification — what the remaining 86 actually are

Board: repaired candidate `94038dd0…` (silk 0, thermals 0, 86 unconnected,
38 violations). Read-only; native DRC on a refilled copy.

## The split

| class | records | verdict |
|---|---:|---|
| **J_W pad ↔ diode pin (real solar-chain gap)** | **9** | **REAL electrical gap** |
| J_W pad F.Cu ↔ B.Cu, same pad, same XY | 10 | **by design** (edge-card land, tab bridges it) |
| J_W pad ↔ track (CUT_SENSE_W1) | 1 | needs review |
| other pads / tracks | 66 | mixed, mostly zone-island |

By net: GND 27, +3V3 15, /VSCAP 5, /W1..W3_SOLAR_N 5 each, /F33_VSENSE 3,
/HUB_PV_* 2 each, /SPI1_* 2 each, plus ten singletons.

## The by-design subset is now PROVEN, not assumed

`jw_geometry.py` measured every J_W pad stack: **all 16 pads are two copper
faces at IDENTICAL XY on the same net** —

```
J_W1 pad 1: 2 copper faces, net=['/W1_SOLAR_P'] -> SAME XY -> mechanically bridged
J_W1 pad 2: 2 copper faces, net=['GND']         -> SAME XY -> mechanically bridged
...
J_W4 pad 4: 2 copper faces, net=['GND']         -> SAME XY -> mechanically bridged
```

One physical land per pad number, present on F.Cu and B.Cu. The inserted wing tab
bridges the two faces mechanically, so board copper must not join them — this is
the edge-card socket-land case the fab doctrine says KiCad flags forever. **These
10 records are not defects.** I am not deleting them from DRC; they are recorded
as waived-by-measurement, with the geometry above as the evidence.

## The 9 real gaps — solar is affected

Each pairs a **J_W pad with a diode pin**, both on the same net, i.e. an
interrupted solar return path:

```
Pad 4 [/W1_SOLAR_N] of J_W1 on B.Cu  || Pad 1 [/W1_SOLAR_N] of D_BP2 on B.Cu
Pad 2 [/W1_SOLAR_N] of D_BP1 on B.Cu || Pad 4 [/W1_SOLAR_N] of J_W1 on B.Cu
Pad 1 [/W1_SOLAR_N] of D_BP2 on B.Cu || Pad 1 [/W1_SOLAR_N] of J_W2 on F.Cu
Pad 2 [/W2_SOLAR_N] of D_BP2 on B.Cu || Pad 4 [/W2_SOLAR_N] of J_W2 on B.Cu
Pad 4 [/W2_SOLAR_N] of J_W2 on B.Cu  || Pad 1 [/W2_SOLAR_N] of J_W3 on B.Cu
Pad 1 [/W2_SOLAR_N] of J_W3 on B.Cu  || Pad 1 [/W2_SOLAR_N] of D_BP3 on B.Cu
Pad 1 [/W3_SOLAR_N] of J_W4 on F.Cu  || Pad 1 [/W3_SOLAR_N] of D_BP4 on B.Cu
Pad 4 [/W3_SOLAR_N] of J_W3 on F.Cu  || Pad 2 [/W3_SOLAR_N] of D_BP3 on B.Cu
Pad 2 [/W3_SOLAR_N] of D_BP3 on B.Cu || Pad 1 [/W3_SOLAR_N] of J_W4 on F.Cu
```

`/W1_SOLAR_N`, `/W2_SOLAR_N`, `/W3_SOLAR_N` are **bypass-diode solar return
paths** — the strings that keep the array alive when a cell is shaded. These are
flight-functional, not cosmetic. They are the highest-value next repair target
and they are **track-level gaps between two named pads**, so unlike the zone
islands they can be closed with a short routed segment.

## Visual

`docs/analysis/hub-stitch-20261102/evidence/unconnected_markers.json` backs the
rendered overlays (`~/reports/hub-current-visuals/unconnected/*_marked.png`):
172 marker instances, **0 outside the board bbox** (checked numerically after a
visual consultant flagged one apparent overflow — the first overlay version had
an assumed margin and genuinely did draw off-board; it was rebuilt to calibrate
from an Edge.Cuts-only render).

## Limits

- A vision consult ran on the corrected overlay and reported only one ambiguous
  corner marker. Vision is advisory here; the numeric bbox check is what
  established the placement is correct.
- **The consultant serving these checks is `kimi-k3`.** `gpt-6-astra` is not
  present on this router — a request for it was served by `kimi-k3.1-pro`. Any
  earlier "Astra review" claim in this thread was therefore not Astra.
- The 66 "other" records are not yet individually classified; do not quote a
  single cause for them.
