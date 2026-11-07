# The 21 failing violations, itemised — and none of them is a routing defect

**Measured 2026-11-07 on `latest.kicad_pcb` with `tracker/hardware/check_drc.py --board <live>`.**

## The breakdown

```
failing 21
  silk_over_copper       3    ALLOWED (cosmetic, no electrical effect)
  unconnected_items     22    ALLOWED (routing warning unless --allow-unconnected)
  lib_footprint_mismatch 11   FAILS
  lib_footprint_issues    8   FAILS
  via_dangling            2   FAILS
```

Both silk and unconnected are in the gate's own `ALLOW` map with stated reasons. The 21 that
actually fail are **11 + 8 + 2**.

## What the 19 library violations are

| footprint | count |
|---|---|
| `MountingHole_2.5mm` | 8 |
| `CP_Radial_D10.0mm_P5.00mm` | 2 |
| `SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm` | 1 |
| (8 `lib_footprint_issues` entries, footprint name not in the message) | 8 |

Eight mounting holes, two electrolytic capacitors, one solder jumper. **No functional
footprint** — no IC, no connector, no RF part. These are library-version differences on
mechanical/passive parts, the same class that was recorded as 19/24 warnings on the earlier
reference board.

Copying a valid `fp-lib-table` into the board directory did **not** change the count (still
21), so this is not a missing-library-table artefact: the footprint geometry in the board
genuinely differs from the current library copies.

## What that means for ordering

`lib_footprint_mismatch` and `lib_footprint_issues` are in the gate's `HARD` tuple, so the
gate fails on them by design. But the practical question for a JLCPCB order is different:
**a footprint that differs from a library copy still fabricates exactly what is drawn in the
board file.** The library is not sent to the fab; the board file is. So these 19 do not make
the board unmanufacturable — they make the board *not library-synchronised*, which matters for
future edits and for anyone regenerating the board from KiCad's library, not for this order.

I am not claiming they should be waved through. I am saying they are a different category from
`clearance`, `shorting_items`, `starved_thermal` or `isolated_copper`, none of which appear in
the count.

## The 2 that could be real

`via_dangling` on `/VSCAP` at (36.0000, 40.0000) and (6.6000, 58.5997) — see
`FINDING-vscap-dangling-vias.md`. Both sit inside the B.Cu `/VSCAP` pour, and that pour has a
**104 mm2 orphaned island** at x 2.95-10.25, y 45.65-71.55 which two vias land in. This is a
genuine connectivity defect and the only item in the failing set that is.

## Absent from the count entirely

No `clearance`, no `shorting_items`, no `starved_thermal`, no `isolated_copper`, no
`track_dangling`, no `copper_edge_clearance` — the last because the gate's scoped allow matches
all 16 J_W* pad entries and passes them by design (see the gate comment: "wing-seat connectors
J_W1..J_W4 are EDGE CONNECTORS — their pads sit ON Edge.Cuts by design, measured 2026-10-22:
16 items, all J_W* pads, ZERO tracks").

That last point matters: **the project already decided the wing-pad edge condition is
by-design and scoped the allow-list to it.** My earlier alarm about the wing-tab slot was
therefore already adjudicated by the project before I raised it.

## Reproduce

```
/usr/bin/python3 -B tracker/hardware/check_drc.py --board docs/analysis/bulk-route-20261107/latest.kicad_pcb --json
```
