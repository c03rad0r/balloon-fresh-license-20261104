# Zone-pair records resolved: 3 informational, 1 thermal-relief artefact

**Measured 2026-11-07 on `latest.kicad_pcb` (18 opens / 19 library-drift violations / 0 electrical).**

## The four zone records and what they actually are

| # | record | verdict |
|---|---|---|
| 14 | `GND_FCu` F.Cu ↔ `GND_In1` In1.Cu | **informational** |
| 15 | `GND_BCu` B.Cu ↔ `GND_In1` In1.Cu | **informational** |
| 16 | `GND_In1` In1.Cu ↔ `GND_FCu` F.Cu | **informational** |
| 4 | `VSCAP_BCu` B.Cu ↔ PTH pad 1 of C_CAP1 | **thermal-relief artefact** |

## GND: electrically joined, three times over

61 stitching objects join at least two layer fills of GND:

```
F.Cu    filled 4141.67 mm2 (18 islands)  joined to B.Cu, F.Cu, In1.Cu
B.Cu    filled   79.13 mm2 (49 islands)  joined to B.Cu, F.Cu, In1.Cu
In1.Cu  filled 5350.30 mm2 ( 1 island)   joined to B.Cu, F.Cu, In1.Cu
```

Every layer's fill shares at least one via or through-hole pad with another layer's fill. The
pours are electrically continuous. These three records are KiCad reporting zone-to-zone
relationships that have no direct copper adjacency, not disconnections. **Nothing to fix.**

## /VSCAP: a thermal-relief pad, not a broken connection

`/VSCAP` has **zero** vias joining its B.Cu pour to any other layer, which initially reads as a
real disconnection. It is not:

- `C_CAP1.1` is a **PTH pad on all four layers**, 2.00 x 2.00 mm, 1.00 mm drill, at
  (36.000, 37.500) — a through-hole part that *can* join layers.
- The B.Cu `/VSCAP` zone declares **pad connection = thermal relief**, `thermal_gap = 0.500 mm`,
  `thermal_bridge = 0.300 mm`.
- Measured: the pad's centre is **outside** the pour, the pad *shape* overlaps the fill, and the
  nearest main-fill point is **0.501 mm** away — i.e. exactly the thermal gap.

So the pad is connected to the pour by thermal spokes at the declared 0.500 mm gap. DRC's
`unconnected_items` check does not treat a thermal spoke join as a pour connection, so it
reports the pair as unconnected. This is a **reporting artefact of thermal relief**, not a
defect, and it is the same class as the three GND records.

## What this means for the order

**None of the four zone-pair records is an electrical defect.** The board's electrical open
count of 18 includes 4 records that are not copper gaps at all, so the number of *real*
unrouted connections is **14**.

That does not mean 18 is wrong to report — DRC says what DRC says, and I should not
reinterpret the count on my own authority. But the distinction matters for an order decision:
4 of the 18 are pour-relationship/thermal artefacts with continuous copper behind them.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/zone_pair_verify.py
```
