# Escape measurement for the remaining real gaps — with the probe's limits stated

**2026-11-07, board `e00b98e7`, 15 opens. S1 rules (0.200 track / 0.200 clearance + guard).**

## What was measured

`escape_probe.py` steps outward from each pad centre in 12 directions at 0.100 mm and reports the
first foreign object that blocks a 0.200 mm track. It answers "what encloses this pad" with a name
and a distance, rather than a router verdict.

| net | pad | widest clear run | free directions | first blockers |
|---|---|---|---|---|
| /SPI2_SCK | U1.4 (11.050, 37.700) | **1.00 mm** | 0 of 12 | /SPI2_MOSI, /SPI2_MISO, pad U1.3 |
| /EN | U1.3 (11.050, 36.430) | **1.40 mm** | 0 of 12 | /SPI2_MISO, /SPI2_MOSI, pad U1.2, pad U1.4 |
| /VSCAP | R_BAL1.1 (40.490, 43.500) | **0.40 mm** | 0 of 12 | /SCAP_MID, R_DIV2.1, R_BAL2.2 |
| /F33_VSENSE | U1.21 (20.435, 51.650) | **0.90 mm** | 0 of 12 | pad U1.22, pad U1.20, /U3_CS_N, /SPI1_SCK |

Every pad is surrounded on all twelve radial directions, and every one terminates on foreign
copper — mostly **the neighbouring pads of the same IC pin row** and the tracks already routed
between them.

## What this establishes, and what it does not

**Establishes:** no straight-line escape of 5 mm exists from any of these four pads at S1. The
enclosing objects are named and measured, so the enclosure is a fact about the layout, not about
the router.

**Does NOT establish:** that no curved escape exists. The probe is **radial only**. A real route can
turn around an obstacle, and this probe cannot see that. So the probe alone cannot prove a pad is
trapped — it can only show that every straight line out is blocked.

The authority on "no route exists" therefore remains the Collide-only A* verdict, which for
`/F33_VSENSE` was **NO PATH after 138 steps to four different targets 41 mm away** — a search that
never left the pad. For `/SPI2_SCK`, `/EN` and `/VSCAP` the earlier verdicts were 118, 164 and 186
steps respectively, the same signature.

**Two independent instruments disagreeing would be a finding; here they agree** — straight-line
escape blocked everywhere, and the router exploring under 200 cells before giving up.

## Ranking by margin

`/VSCAP` is by far the tightest: widest clear run **0.40 mm** against a requirement of
0.100 (half track) + 0.200 (clearance) = **0.300 mm** plus the 0.0707 mm guard. It has almost
nothing, inside the C10-frozen R_BAL1/R_DIV2 pinch measured earlier at 0.180 mm centreline against
0.300 mm required.

`/EN` at **1.40 mm** has the most room of the four, which is consistent with its failure being a
long detour rather than a hard pinch — it is the one most likely to be closable if any of them is.

## Reproduce

```
ESCAPE_TARGETS="/SPI2_SCK:U1:4,/EN:U1:3,/VSCAP:R_BAL1:1" \
  /usr/bin/python3 -B docs/analysis/escape_probe.py
```

## Nothing adopted

No board change from this measurement. The four pads need a decision (accept, local rule
reduction, move a neighbour, or drill-in-pad) rather than another routing attempt at S1.
