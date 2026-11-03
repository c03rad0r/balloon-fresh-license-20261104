# GND stitching + 3V3 plane: 86 → 54 unconnected, and three DFM defects found by review

**Unconnected 86 → 54. Frozen-rule DRC 22 violations, 0 errors.** Not orderable yet; see the end.

## What the 18 shortfalls actually were

DRC said "80 unconnected". Splitting by net made the cause obvious — it was never 80 separate
routing gaps:

| net | items | cause |
|---|---|---|
| GND | 50 | **zero stitching vias.** Four-layer board, three GND planes (F.Cu, In1.Cu, B.Cu), nothing joining them. Three isolated islands. |
| +3V3 | 30 | **never routed at all.** 0 tracks, 0 vias, and one 4.32 mm² zone that DRC reported as *disconnected from itself*. |
| /VSCAP etc. | — | separate, untouched |

## +3V3 contradicts its own ADR

ADR-107 line 97: stackup is `F.Cu / In1.Cu=GND / In2.Cu=3V3 / B.Cu`. Measured on the board:

- In1.Cu: GND plane, 5517 mm² — **as specified**
- In2.Cu: **no zone at all**; 5 signal tracks instead
- the only 3V3 copper: a 4.32 mm² B.Cu fragment

`add_3v3_plane.py` builds the In2 plane (5477 mm²) and `tap_3v3.py` taps the pads down to it;
`stitch_gnd_planes.py --offset` joins the GND planes.

## Three DFM defects, each caught by review and reproduced numerically

**1. Via-in-pad.** 43 GND vias landed at SMD pad centres, on pads as small as **0.54 × 0.64 mm —
narrower than the 0.60 mm via**. JLCPCB does not fill or cap vias by default, so an uncapped barrel
inside a pad wicks solder during reflow. **kicad-cli DRC does not check this**; the check had to be
written. Astra flagged it from the render twice ("several white vias sit directly on gold pads")
before the numbers agreed.

**2. Vias on the J_W cavity slots.** `edge_shapes` was built from `board.GetDrawings()` only, so the
four 6.0 × 0.5 mm cavity slots inside each `J_W` footprint were not keep-outs. Offset vias landed on
them → 4 `copper_edge_clearance`. Same blind spot as B48.

**3. Duplicate vias.** Each `J_W` tab carries every pad number **twice** — same XY and net, once per
face, because the tab is soldered from both sides. Iterating pads visited each site twice and dropped
two vias on it → 5 `holes_co_located`.

Each was found the same way: DRC or the spatial consultant named a symptom, and the tool was wrong —
not the board.

## The iteration, with what each stage cost

| stage | centre taps | offset taps | unresolvable | DRC errors | unconnected |
|---|---|---|---|---|---|
| v2 fit test `>= VIA_D+0.10` | 29 | 13 | 9 | 0 | 49 |
| v3 `>= VIA_D+0.20` | 21 | 21 | 9 | 0 | 49 |
| v4 ring starts outside pad | 21 | 20 | 9 | 0 | 49 |
| v5 offset-only, no edge fix | 0 | 45 | 9 | **4** | 51 |
| **v6 + footprint Edge.Cuts + dedupe** | **0** | **37** | 15 | **0** | **54** |

v6 trades 5 unconnected for removing 38 via-in-pad sites, 4 edge violations and 5 duplicate drills.
That is the right trade for a board that gets assembled.

## Final state (frozen DRU loaded)

```
22 violations   0 errors   54 unconnected
  8 lib_footprint_issues (warning)
 11 lib_footprint_mismatch (warning)
  3 silk_over_copper (warning)
GND zones: F.Cu 4490 / B.Cu 86 / In1.Cu 5517 mm2, 37 stitching vias
+3V3 zone: In2.Cu 5477 mm2, 12 tap vias
```

Board sha256 `2d2498d31be4ee85487abc75fff585be1a8f3c5d6a1902d0274bd8f3703009bc`

## Known remaining, stated plainly

- **54 unconnected.** GND and +3V3 taps are done; the rest is signal routing.
- **7 vias still overlap a pad edge.** All 7 have `at_centre=False` — adjacent, not in-pad, and DRC
  is silent on every one. Reported rather than hidden because "adjacent" is a judgement call at this
  pitch: 2 of the 7 are on 0.55 mm-tall pads.
- **9 real dead ends** (single segment, no pad, no via): `/GNSS_PPS` ×2, `/USB_DN` ×2, `/E28_BUSY` ×2,
  `/E28_RESET_N`, `/SPI1_SCK` ×2. All 9 nets DO connect real pads elsewhere, so these are stub
  fragments mid-route, not orphaned nets. `E28_BUSY`/`E28_RESET_N` are legacy E28-era net names on a
  board carrying `U_LORA1280` — worth renaming for the next revision.
- **15 GND pads unresolvable** by offset placement (no legal site within 4 mm).
- **19 library warnings** — footprint-vs-library drift; the fab etches the library, not the cache.

## Reproduce

```
R=~/reports/flight-readiness-20261102
python3 tracker/hardware/stitch_gnd_planes.py $R/via-upsize/FINAL.kicad_pcb /tmp/s.kicad_pcb --offset
python3 docs/analysis/solar-8land-verify/add_3v3_plane.py /tmp/s.kicad_pcb /tmp/p.kicad_pcb \
  --dru tracker/hardware/jlcpcb-s1-frozen.kicad_dru
python3 docs/analysis/solar-8land-verify/tap_3v3.py /tmp/p.kicad_pcb /tmp/f.kicad_pcb \
  --dru tracker/hardware/jlcpcb-s1-frozen.kicad_dru
```

Astra's review of this state: `review/lanes/astra-v6.txt` — served `gpt-6-astra`. Its "tracks end in
empty space" finding is **correct and matches the 9 measured dead ends**. Its "vias on pads" finding
is a render artefact at this point: pads are drawn translucent and adjacent vias composite over them;
0 vias are at a pad centre.

---

# Follow-on: GND pour islands bridged (54 → 46)

After stitching, DRC still reported 22 items whose BOTH ends were GND **zones** — the three GND
pours are separate pieces of copper and a via at a pad does not necessarily land in each piece.

`bridge_gnd_islands.py` adds one GND via inside each pour outline that contains none. **10 vias
added, 3 islands had no legal site. Unconnected 54 → 46, 0 errors, no new violation classes.**

Board sha256 `bb65226fbfd923ddf1c4b4e08155bc48d5372f4cb1b18d751b568dabf2f526a5`

## Three bugs in that script, each caught by DRC

1. **`fp.Contains(pt)` is not a per-island test.** It returns True if the point is in ANY island of
   the filled polygon set, so every island looked bridged and the first run added **0 vias** while
   the 22 opens stayed. The per-island test is `fp.COutline(i).PointInside(pt)`.
2. **Hole-to-hole measured from the wrong reference.** The check compared the via centre against the
   pad *rectangle*, which is not a drill distance. Fixed to pad centre + its own drill radius.
3. **Own-net PTH pads were excluded as obstacles.** A through-hole pad on our own net still occupies
   a drilled hole; skipping it placed a via on `J_PROG.1`'s barrel — `hole_to_hole`, actual
   **0.0000 mm**. Own-net PTH pads now contribute their drill (but not their copper).

## Remaining by net

```
12 /VSCAP    8 /W3_SOLAR_N   8 /W2_SOLAR_N   6 GND
 6 /F33_VSENSE   6 +3V3       4 /W1_SOLAR_N   4 /SPI1_SCK ...
```

`/VSCAP` is next: one 4469 mm² B.Cu zone whose own DRC entry says the zone is disconnected **from
itself**, which is the same signature the 3V3 zone had before the In2 plane was built.
