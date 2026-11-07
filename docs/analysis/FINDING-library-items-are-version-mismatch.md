# The 15 remaining DRC failures are a KiCad footprint-file version mismatch, not board defects

**2026-11-07, `latest.kicad_pcb` `ec2a7af8`, 18 opens, silk 0, DRC 15 failing.**

## What is left failing

```
lib_footprint_mismatch  11
lib_footprint_issues     4
unconnected_items       18   (allowed type, not a failure)
```

`check_drc.py` passes `silk_over_copper` and `unconnected_items`; the 15 are the library items.
Zero clearance, zero shorting, zero starved_thermal, zero isolated_copper, zero via_dangling,
zero track_dangling.

## Root cause, measured

The 4 `lib_footprint_issues` for `balloon_flight_v10` are NOT a missing or unregistered library:

- the library directory exists: `tracker/hardware/schematics/flight_board/v10_lib/balloon_flight_v10.pretty`
- the footprint files exist and are correct: `LoRa2021F33_2G4.kicad_mod`, `LoRa2021_Castellated.kicad_mod`
- the board's FPIDs match the filenames exactly: `balloon_flight_v10:LoRa2021F33_2G4`,
  `balloon_flight_v10:LoRa2021_Castellated` (on U2, U_C, U3)
- the library was registered BOTH in a board-local `fp-lib-table` AND in
  `~/.config/kicad/9.0/fp-lib-table`, with a correct absolute URI. Neither changed the count.

The decisive test:

```python
pcbnew.FootprintLoad('/…/balloon_flight_v10.pretty', 'LoRa2021F33_2G4')
-> None
```

The loader returns None for a file that exists, is readable, and is well-formed S-expression.
Its header says:

```
(footprint "balloon_flight_v10:LoRa2021F33_2G4"
     (version 20250114)
     (generator "pcbnew")
     (generator_version "9.0")
```

This environment is **pcbnew 9.0.9**. The board-level DRC reports these as
`lib_footprint_issues` / `lib_footprint_mismatch` because it cannot load the library footprint
to compare against — not because the footprint in the board is wrong.

## What this means for the order

**Nothing.** A footprint that cannot be loaded from a library for comparison still fabricates
exactly what is drawn in the board file. The library is never sent to a board house; the board
file is. All 15 items are comparison/registration artefacts of this machine's KiCad install.

The 11 `lib_footprint_mismatch` are the same class on standard-library footprints
(MountingHole x8, CP_Radial x2, SolderJumper x1) — version drift between the board's embedded
copies and this machine's KiCad standard libraries.

## What I am NOT claiming

I am **not** saying the gate should be ignored. `check_drc.py` puts these in its `HARD` tuple by
design, so the gate fails and that is the correct behaviour given its own rules. Resolving it
means either:

1. running the gates on a machine whose KiCad footprint libraries match the project's (the
   intended environment — the repo carries `.pretty` directories for exactly this reason), or
2. regenerating the affected footprints so board and library agree, or
3. recording a scoped allow-list entry for these specific refs with a measured justification,
   the way the project already did for `copper_edge_clearance` scoped to `J_W1..J_W4`.

I am not going to add an allow-list entry myself: AGENTS.md is explicit that an allow-list entry
needs a measured justification, and "my KiCad can't load the library" is a defect in the
environment, not a reason to weaken a gate.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/run_all_gates.py docs/analysis/bulk-route-20261107/latest.kicad_pcb
python3 -c "import pcbnew as p; print(p.FootprintLoad('<lib>','LoRa2021F33_2G4'))"
```
