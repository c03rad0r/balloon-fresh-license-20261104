# Flight-readiness tooling — 2026-11-02

Read-only measurement tools for the v10 flight hub. They exist because three claims made during the
2026-11-02 readiness audit could not be checked with any tool already in the repo, and each of the
three turned out to be load-bearing:

| tool | the claim it settles |
|---|---|
| `electrical_mechanical_audit.py` | "the design rules in force are the frozen fabrication rules" — measured **not** true here (35 of 41 vias below the frozen 0.60 mm diameter, min copper-to-edge 0.4375 mm) |
| `compare_copper.py` | "this repair changed nothing electrical" — distinguishes copper OBJECTS from zone FILL AREA, which a refill legitimately moves |
| `repair_scoped_thermal.py` | "the starved-thermal fix only touched the pads the DRC named" — the pre-existing `clear_starved_thermal.py` sets **every** pad of an offending footprint |
| `verify_visual_claims.py` | "the consultant said X about the plot" — turns a stated claim into a number (silk pair gaps, reference-to-part distance, ink coverage) |

None of them writes to a board except `repair_scoped_thermal.py`, which writes only to the `out` path
it is given. Nothing here is wired into a hook: they are measurement, and the existing gates
(`check_drc.py`, `check_silk.py`, `check_schematic_parity.py`, `registry.py check`) remain the
authority.

## Non-obvious behaviour, each measured the hard way

- **`pcbnew` lives in the distro interpreter.** Run these with
  `PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3 …` or the kicad venv. Importing it
  under a mismatched interpreter can segfault.
- **A zone refill changes bytes and filled areas, never copper objects.** `compare_copper.py`
  reports both separately on purpose: refill noise has already been mistaken for a routing change
  in this project, and the reverse mistake (a real copper edit hidden inside a "cosmetic" refill)
  is the more dangerous one.
- **`GetWidth()` on a via needs a layer** (`v.GetWidth(pcbnew.F_Cu)`); the no-argument form raises an
  assertion in KiCad 9 and, in one measured case, aborted a comparison run.
- **A duplicated `Pad` number is normal.** `U1` exposes twelve pads numbered `41` (the exposed pad's
  stitching), so a hole-to-hole scan must drop same-centre pairs or it reports a 0 mm violation that
  is really one pad counted twice.
- **Silk text can be detached and still pass every gate.** 7 references sit 15.6–34.2 mm from the
  footprint they name — `fix_silk.py`'s margin fallback parks stubborn labels in the free margins.
  No DRC rule reports it; `verify_visual_claims.py` does.
- **The repo's `svg_layout_guard.py` is calibrated in pixels.** Handing it a KiCad SVG (mm user
  units, `width="102.3112mm"`) raises `ValueError`; after stripping the unit it runs, but its poison
  test does not fire on that family — so its "0 problems" on a KiCad plot is **not** evidence. The
  generator that produced the audit card used its own panel-fit check instead, and that check did
  refuse a colliding layout.

## Tests

`tests/test_flight_readiness_tools.py` — 6 tests, each with a negative half (a dropped track must
compare as changed; a label moved *away* from its part must raise the gap). They loud-skip when
`pcbnew` is unavailable, naming the interpreter, the same way `test_v10_hole_clearance.py` does.

## Reproduce

```bash
export PYTHONPATH=/usr/lib/python3/dist-packages
B=tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb
/usr/bin/python3 tools/flight_readiness/electrical_mechanical_audit.py $B
/usr/bin/python3 tools/flight_readiness/verify_visual_claims.py $B
/usr/bin/python3 tools/flight_readiness/compare_copper.py $B $B          # 0, identical
/usr/bin/python3 tools/flight_readiness/repair_scoped_thermal.py \
    in.kicad_pcb out.kicad_pcb U_LORA1280.14 J_PROG.1                    # DRC-graded, gate in output
python3 -m pytest tests/test_flight_readiness_tools.py -q
```
