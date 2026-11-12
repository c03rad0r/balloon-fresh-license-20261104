# /F33_VSENSE: Pad 21 of U1 is genuinely trapped at S1 — measured in all 12 directions

**2026-11-07, board `e00b98e7`, 15 opens.**

## The net's actual geometry

The B.Cu copper is a **closed loop** touching no pad:

```
(21.850, 8.350) -> (18.750, 8.350)   3.100 mm
(18.750, 8.350) -> (18.750, 10.250)  1.900 mm
(18.750, 10.250) -> (14.950, 10.250) 3.800 mm
(14.950, 10.250) -> (14.950,  6.650) 3.600 mm
```

Pad 21 of U1 sits at **(20.435, 51.650)**, F.Cu only, 1.500 x 0.900 mm, **41.434 mm** from the
nearest loop point. So the open is a genuine 41 mm pad fanout — the loop is self-connected, the pad
is isolated.

## Corridor test

Pointed the S1 Collide router at all four loop corners with a 12 mm margin and a 90 s budget:

```
-> (18.750,10.250)  NO PATH  search exhausted 138 steps
-> (21.850, 8.350)  NO PATH  search exhausted 137 steps
-> (14.950,10.250)  NO PATH  search exhausted 138 steps
-> (18.750, 8.350)  NO PATH  search exhausted 138 steps
```

**138 steps for every target, 41 mm away.** A search that dies after 138 steps has not explored the
corridor — it never left the pad. The bottleneck is the pad's own escape, not the distance.

## Why: every escape direction is blocked

Probed 12 directions from the pad centre in 0.100 mm steps with the S1 guard band:

| direction | clear run | then blocked by |
|---|---|---|
| 0–30° | 0.4–0.5 mm | **pad U1.22** |
| 60–120° | 0.6–0.7 mm | **track /U3_CS_N** |
| 150–210° | 0.4–0.5 mm | **pad U1.20** |
| 240–330° | 0.8–0.9 mm | **track /SPI1_SCK** |

The pad is 1.500 x 0.900 mm and sits between U1.20 and U1.22 in the pin row, with /U3_CS_N above
and /SPI1_SCK below. The **widest** clear run in any direction is 0.9 mm, and it terminates on
copper. A 0.200 mm track needs 0.100 mm half-width plus 0.200 mm clearance from foreign copper, so
a legal escape needs more room than exists in any of the twelve directions.

**This is a real geometric trap at the frozen S1 rules, not a router limitation.** The earlier
"enclosed pocket" verdict on this net was correct; what was missing was the measurement showing
*which* neighbours enclose it and by how much.

## What this does NOT say

- It does not say the net cannot be connected. It says it cannot be connected **at 0.200/0.200
  from this pad without moving something**.
- It does not say the pad is unreachable in assembly or from another layer: the pad is F.Cu SMD
  with no drill, so a via-in-pad or a microvia is not available without an explicit decision.
- The four loop corners were the only targets tried. A route to a mid-segment point would face the
  same escape problem, because the escape is blocked at the pad end.

## Options, none of which are mine to take

1. **Accept the open.** One pad of a 21-pin IC, on a net that reaches the rest of the board.
2. **Authorise a local rule reduction** for this one escape (e.g. 0.150 mm clearance) — the brief
   says hard rules unchanged, so this needs explicit sign-off.
3. **Move a neighbour.** `/SPI1_SCK` and `/U3_CS_N` are routed tracks; nudging either would open an
   escape. Placement is frozen in the C10 sense only, so this is allowed but is a design change.
4. **Drill-in-pad / via-in-pad** to escape downward — requires explicit authorisation and a fab
   capability check (JLCPCB supports it at extra cost and with drill rules).

## Tool defects fixed getting here

- `why_blocked.py`: stored fragment points are **raw nanometres**, not mm; the extra `* UM`
  overflowed SWIG int32. Third units bug this session.
- `closest_gap.py`: accepted a **1-point path** as ROUTABLE. A 1-point path joins nothing; added
  `len(path) >= 2`.
- F33VIA (two vias at coincident cross-layer points) was **built, verified clean, and rejected**:
  opens stayed 15 -> 15. The vias joined fragments already connected through the rest of the net
  while the real gap was the isolated pad.
