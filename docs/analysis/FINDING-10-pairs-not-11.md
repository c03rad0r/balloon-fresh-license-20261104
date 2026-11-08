# FINDING: the board has 10 open PAIRS, not 11, and only 4 are routing work

Measured 2026-11-08 on board `322ade1e` (live `latest.kicad_pcb`).

## The count I had been quoting was wrong

`kicad-cli pcb drc` prints **11 `unconnected_items` records**, and I reported "11 opens" all
campaign. Normalising each record to its unordered pair of items gives **10 distinct pairs**:
the F.Cu↔In1 GND pair is reported twice, once from each side.

This is the same class of error as the Excellon tool-count false alarm: the raw record count
is not the number of distinct defects. Count PAIRS.

## Classification of the 10

| # | pair | category | closable by routing? |
|---|------|----------|----------------------|
| 1 | U1.4 `/SPI2_SCK` ↔ U2.12 | pad-local trap, 112-cell pocket | no at S1 |
| 2 | U1.21 `/F33_VSENSE` ↔ B.Cu track | pad-local trap, 138-cell pocket | no at S1 |
| 3 | `VSCAP_BCu` zone ↔ C_CAP1.1 (PTH) | zone fill does not reach a through-hole | **YES** |
| 4 | `/VSCAP` F.Cu track ↔ R_BAL1.1 | pad-local trap, 38-cell pocket | no at S1 |
| 5 | `/W2_SOLAR_N` B.Cu 0.1414 ↔ F.Cu | net severed into 4 components | **possibly** — see below |
| 6 | J_W4 pad 1 F.Cu ↔ B.Cu | two-face wing pad | **no, by design** |
| 7 | J_W3 pad 4 F.Cu ↔ B.Cu | two-face wing pad | **no, by design** |
| 8 | `GND_FCu` ↔ `GND_In1` | zone bookkeeping | **not a defect** — see below |
| 9 | `GND_BCu` ↔ `GND_In1` | zone bookkeeping | **not a defect** |
| 10 | `GND_In1` ↔ `GND_FCu` (dup of 8) | zone bookkeeping | **not a defect** |
| 11 | U1.3 `/EN` ↔ J_PROG.3 | pad-local trap, 166-cell pocket | no at S1 |

Item 3 detail: `C_CAP1` pad 1 is a **PTH through-hole** — 1.000 mm drill, copper on all four
layers, `attr=0` (PTH). The `VSCAP_BCu` zone is filled, but `ZONE.HitTestFilledArea` at the pad
centre `(36.0, 37.5)` returns **False**, and there are **no `/VSCAP` tracks anywhere near** the
pad. So the zone genuinely does not reach a through-hole that is on B.Cu — a real gap that a
via or an extended fill can close.

## Items 6 and 7 are not closable on the board

`J_W4` pad 1 and `J_W3` pad 4 each resolve to **two separate physical pad objects with the
same pad number**, one whose copper is on F.Cu and one on B.Cu, both `PAD_ATTRIB_SMD`:

```
J_W4 pad 1 : 2 physical pad object(s)
    net=/W3_SOLAR_N   layers=['F.Cu']  attr=1
    net=/W3_SOLAR_N   layers=['B.Cu']  attr=1
```

DRC reads this as "Pad 1 of J_W4 on F.Cu" missing from "Pad 1 of J_W4 on B.Cu". These are the
two-face wing interface: separate copper faces joined mechanically by the assembly tab
(ADR-120 R1, AGENTS.md §13a). A track across the socket cavity is forbidden, so **no board
copper can ever join them.** These two records will persist on every future DRC of a correct
board. They should be excluded from the open count, or the count should state them separately.

## Items 8, 9, 10 are not defects

48 GND stitching vias exist and each layer has a GND zone (`GND_FCu` F.Cu, `GND_BCu` B.Cu,
`GND_In1` In1.Cu). Testing every via with `ZONE.HitTestFilledArea` — the correct instrument,
which tests FILLED copper rather than outline containment:

```
   46 via(s) on filled copper: ['B.Cu', 'F.Cu', 'In1.Cu']
    2 via(s) on filled copper: ['B.Cu', 'In1.Cu']      <- near the W4 socket, F.Cu fill absent
```

**46 of 48 vias land on filled GND copper on all three layers.** The zones are stitched. The
three records are KiCad's zone-to-zone connectivity bookkeeping for separate ZONE objects
sharing a net, reported once per pair and once again reversed. They are not severed copper.

## Two instruments that lied while looking authoritative

Both are recorded because each produced a plausible number that was wrong:

1. **`SHAPE_POLY_SET.Collide(probe)` on a zone's filled polys includes containment.** It
   answers "is this point inside the board outline", so it reported 46/48 vias inside all
   three zones — the same answer as the correct method, *by coincidence*, not by reasoning.
   The number was right and the method could not have detected the opposite case.
2. **`CONNECTIVITY_DATA.GetConnectedItems`** needs a `std::vector<KICAD_T>`, and pcbnew's SWIG
   bindings expose no `KICAD_T_VECTOR` at all. Every call raised TypeError. The KiCad engine
   that DRC itself uses is therefore not reachable from Python here; `HitTestFilledArea` is
   the workable substitute.

## /W2_SOLAR_N (item 5) is NOT a missing via

I attempted one via plus two stubs at (39.200, 73.550), chosen by a measured gap search
(0.550 mm, the only site clearing S1 + guard band in a 0.8 mm window; the meeting points
measured 0.100 / 0.150 / 0.200 mm against `/E28_CS_N`). The net stayed open, 0 opens closed,
and one `hole_to_hole` violation was added.

Root cause of the failed attempt: I read the DRC's B.Cu segment endpoints from a layer-less
dump and assumed they were at the (38.8, 73.95) meeting point. They are at
**(48.150, 65.500)–(48.250, 65.400)** — 10 mm away. **Print the layer and the coordinates
together, or the coordinates mean nothing.** Same failure shape as the `/VSCAP` "0.180 mm
centreline" error.

A proper union-find over the net's 490 items (snapping endpoints within a half track width,
honouring layers) shows `/W2_SOLAR_N` is in **4 components**:

```
  comp 447  453 items  vias 2  layers B.Cu, F.Cu, In1, In2     <- the main run
  comp 485   26 items  vias 5  layers ...                       <- the W1/W2 wing cluster
  comp 487   10 items  vias 0  layers B.Cu                      <- B.Cu chain ending 1.700 mm
                                                                  short of J_W3 pad 1
  comp 486    1 item           F.Cu pad                         <- J_W3 pad 1, F.Cu face
```

`J_W3` pad 1 has **7 B.Cu tracks and 0 F.Cu tracks** touching it: the F.Cu face is the
floating one, again the two-face pattern. The B.Cu chain stopping 1.700 mm short of a pad
that IS on B.Cu looks like a genuine, closable gap — but the wing-pad structure means it must
be checked against the socket-cavity rule before any track is drawn there.

## What this changes

Of 10 distinct pairs: **3 records are not defects** (GND zone bookkeeping — one pair counted
twice), **2 are not closable by design** (two-face wing pads), leaving **6 genuine**:

- four pad-local traps at S1 — `/EN`, `/SPI2_SCK`, `/F33_VSENSE`, `/VSCAP`(R_BAL1 side)
- `VSCAP_BCu` zone not reaching the `C_CAP1` through-hole — **closable**
- `/W2_SOLAR_N` severed into 4 components — **possibly closable**

Note the duplicate: the GND pair appears twice in the raw list, so "not defects" is 3 distinct
pairs from 4 records. An earlier draft of this file said 5 genuine and 4 not-defects; that
miscounted the duplicate as a fifth non-defect. `open_count_honest.py` now prints raw records,
distinct pairs, and genuine work separately so neither number can be quoted alone.

That is a materially smaller real blocker than "11 opens". The four pad-local traps still need
the decision already raised: a 0.150 mm scoped clearance rule for those pads, or moving the
enclosing copper.

## Reproduce

    /usr/bin/python3 -B docs/analysis/open_count_honest.py

