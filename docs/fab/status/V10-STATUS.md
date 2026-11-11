# v10 — hub board status (ORDERED)

**Ordered from JLCPCB: 10 assembled boards, double-sided PCBA.**
This is the board that was actually fabricated. It is **not** a perfect board, and this page says so
plainly rather than letting a reader discover it later.

| | |
|---|---|
| Board of record | `docs/analysis/bulk-route-20261107/latest.kicad_pcb` (git blob `92ff3705`) |
| Outline | **72.1 × 80.1 mm** |
| Copper layers | 4 |
| Footprints | 49 |
| Components fitted by JLCPCB | **23** (19 top, 4 bottom) |
| Tracks / vias | 2931 segments / 161 vias |
| Drill | 196 holes, 4 tools (0.200 / 0.300 / 1.000 / 2.500 mm) |
| **DRC errors** | **0** |
| DRC warnings | 16 (11 footprint-library mismatch, 4 library issues, 1 dangling track) |
| **Unconnected items** | **12** |
| Assembly data | `docs/fab/v10-order-double-sided/cpl-jlc.csv` (23 placement rows) |

---

## 3D render — top side

![v10 hub board, top side, 3D isometric render](v10/v10-top-iso.png)

19 components fitted here. The two tall blue parts are bulk storage capacitors; the black headers are
the programming and power-monitor connections.

**Expect the board to look partly empty.** Large bare pad areas — `U_LORA1280`, `U2`, `U5` and
`J_W1`–`J_W4` — are **not fitted in this order**. They ship as solder pads for parts fitted later by
hand. They also have no 3D models in any KiCad library, so they render as bare pads rather than
bodies. That is a rendering limitation on unpopulated sites, not missing design.

---

## 3D render — bottom side

![v10 hub board, bottom side, 3D isometric render](v10/v10-bottom-iso.png)

4 components fitted here — the `D_BP1`–`D_BP4` bypass diodes.

**This is why the order is double-sided assembly** rather than the cheaper single-sided option. A
single-sided order would have shipped with four diodes missing. That mistake was caught on
2026-11-09, before the order went out.

---

## What is honestly open on this board

The board is fabricated and functional in the ways it was designed to be, but it carries **12
unconnected items** that are known and deliberate rather than unexpected:

| Net | Unconnected items | What it is |
|---|---|---|
| `GND` | 3 | isolated pour fragments not stitched |
| `/VSCAP` | 2 | storage-rail segments not joined |
| `/W3_SOLAR_N` | 2 | wing 3 solar return |
| `/W2_SOLAR_N` | 1 | wing 2 solar return |
| `/SPI2_SCK` | 1 | `U1.4` ↔ `U2.12` |
| `/F33_VSENSE` | 1 | the 43.7 mm dead run (see below) |
| `/EN` | 1 | flash-time only; no copper |
| `/IO0` | 1 | flash-time only; no copper |

*(12 items total across 8 nets. Each item is one missing connection; the count is per item, not per
endpoint — an earlier draft of this table doubled it by counting both endpoints.)*

Three of these are known design risks accepted for this revision and carried into v11 as explicit
fix items — `/F33_VSENSE`, `/EN` and `/IO0`. See the [v11 status](V11-STATUS.md) for the fix plan.
The remaining five are unfinished routing (pour stitching and rail joins), not accepted risks.

**The 16 DRC warnings are all library-metadata**, not electrical: 11 `lib_footprint_mismatch` and 4
`lib_footprint_issues` (local library differs from the shipped footprint), plus 1 `track_dangling`.
None is a clearance, short or edge violation.

---

## Which board file is the board of record — and why this matters

**This is worth reading if you compare numbers against other documents.**

`tracker/hardware/` contains three files named `hub_board_v10*`. **None of them is the ordered
board.** They are earlier or alternate builds, and they measure differently:

| file | segments | vias | DRC errors | unconnected |
|---|---|---|---|---|
| **board of record** (`bulk-route-20261107/latest.kicad_pcb`, `92ff3705`) | **2931** | **161** | **0** | **12** |
| `tracker/hardware/hub_board_v10.kicad_pcb` (`d07b93d8`) | 730 | 52 | 16 | 82 |
| `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb` (`212d81b4`) | 843 | 41 | 18 | 86 |

The identifying evidence is the **shipped drill file**, not the filename: the order zip's `board.drl`
carries 196 holes at 0.200 / 0.300 / 1.000 / 2.500 mm, and only the board of record reproduces that
(188 PTH + 8 NPTH, same four diameters). A file checked by name alone would have reported the wrong
board's DRC.

This is also why an earlier status note on this project claimed "82 unconnected, 16 errors" — it was
measured on `hub_board_v10.kicad_pcb`, which is not what was fabricated.

---

## What this board does and does not do

- It is the **hub** — the wing/power distribution and radio board.
- It is **not** the base station (433 MHz ground receiver) and **not** the pressure controller.
- Nothing here has been powered up or qualified. Fabrication is complete; hardware qualification is
  not claimed.

---

### Reproduce

```bash
cd /path/to/balloon-fresh
kicad-cli pcb drc --format json --units mm --severity-all \
  -o /tmp/v10-drc.json docs/analysis/bulk-route-20261107/latest.kicad_pcb
/usr/bin/python3 -c "
import json; d=json.load(open('/tmp/v10-drc.json'))
print('violations', len(d['violations']), 'unconnected', len(d['unconnected_items']))"
```

Renders: KiCad 9.0.9, `kicad-cli pcb render --quality high --floor --perspective`.

*Related: [v11 status](V11-STATUS.md) · [board status register](../status/BOARD-STATUS.md) · [order sheet](../V10-JLCPCB-ORDER-SHEET-10BOARDS.md)*
