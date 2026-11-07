# BOM/CPL generated, but the BOM has 8 mismatched references — not order-ready

**2026-11-07, `latest.kicad_pcb` `ec2a7af8` / schematic `v10_flight.kicad_sch`.**

## What was produced

```
kicad-cli pcb export pos  ->  board-cpl.csv   48 placement rows (38 top, 10 bottom)
kicad-cli sch export bom  ->  board-bom.csv   41 BOM lines
```

Both generate. But the exporter printed:

```
Warning: schematic has annotation errors, please use the schematic editor to fix them
```

and the BOM is **not usable for ordering as generated**.

## The defect

Eight BOM entries carry a literal `?` in the reference, so they do not match their CPL rows:

```
BOM has:   C_BULK?  C_HF?  C_MON?  J_HUB_PV?  J_PROG?  J_VCC?  U_C?  U_HUB_CVT?
CPL has:   C_BULK   C_HF   C_MON   J_HUB_PV   J_PROG   J_VCC   U_C   U_HUB_CVT
```

An order built from this BOM would either drop those eight parts or order them as a separate
unmatched line, while the CPL would still carry the correct references. That is exactly how a
board gets assembled with eight components missing.

## What it is NOT

The design is fine. Measured:

- **0** `Reference "…?…"` properties in the schematic file
- **114** instance reference entries, **all distinct**, **none unannotated**
- all eight affected refs **exist correctly on the board**:
  `C_BULK`, `C_HF`, `C_MON`, `U_C`, `U_HUB_CVT`, `J_PROG`, `J_HUB_PV`, `J_VCC` — all present in
  the 49 board footprints

So the `?` is introduced by the **BOM exporter**, falling back to a library/default reference
for those symbols, not by a mis-annotated schematic. The exporter's own warning is about
annotation state it cannot resolve from the instance data it reads.

## What this means

**Bare-board order: unaffected.** Gerbers and drill are complete and correct
(`FINDING-fab-package-verified.md`), and a bare-board order needs neither BOM nor CPL.

**Assembly order: blocked** until the BOM references are correct. Options, none of which I
should take unilaterally:

1. Open the schematic in KiCad and re-run annotation, then re-export. This is the exporter's own
   suggested fix and likely resolves it, since the instances are already correctly named.
2. Generate the BOM from a different exporter (`kicad-cli sch export bom` variants, or the
   project's own `scripts/gen_v9_bom.py` style tooling) and join against the CPL by UUID.
3. Post-process: strip the trailing `?` and verify the join. Fast, but it is papering over a
   tool disagreement and should be recorded as such.

I recommend (1) first and (3) only as a documented stopgap.

## Reproduce

```
kicad-cli pcb export pos --format csv --units mm --output cpl.csv <board>.kicad_pcb
kicad-cli sch export bom --output bom.csv tracker/hardware/schematics/flight_board/v10_flight.kicad_sch
```
Then diff the reference sets: the eight `?` entries will appear in the BOM only.
