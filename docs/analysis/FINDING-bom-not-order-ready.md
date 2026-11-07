# The BOM is not order-ready: no part numbers, and 5 rows have no selected part

**2026-11-07, `latest.kicad_pcb` `ec2a7af8`, schematic `v10_flight.kicad_sch`.**

This supersedes the narrower `FINDING-bom-reference-mismatch.md`. The `?` references are one
symptom of a larger fact: **the BOM cannot be used to order an assembled board at all.**

## What the exported BOM actually contains

```
Refs,Value,Footprint,Qty,DNP
```

41 lines, 41 parts, 0 DNP rows.

### 1. There is no part-number column

No `LCSC`, no `MPN`, no `Part`. JLCPCB PCBA needs an LCSC part number (or a matched MPN) for
every line before it will quote or assemble. Without that column there is nothing to match on.

### 2. Five rows have no selected part

```
U_CUT1     latched cut driver + cut-sense (part TODO(unverified))   SOT-23-6
U_CUT2     latched cut driver + cut-sense (part TODO(unverified))   SOT-23-6
U_CUT3     latched cut driver + cut-sense (part TODO(unverified))   SOT-23-6
U_CUT4     latched cut driver + cut-sense (part TODO(unverified))   SOT-23-6
U_HUB_CVT  HUB_PV input (part TODO(unverified))                     VQFN-16 3x3 P0.5
```

The value field literally says `part TODO(unverified)`. These are not parts with a missing
number — **no part has been chosen**. The footprint is fixed (SOT-23-6, VQFN-16) but the device
is undecided.

`U_CUT1..4` are the four pyro cut drivers. `U_HUB_CVT` is the PV input converter.

### 3. Eight references carry a `?`

```
C_BULK?  C_HF?  C_MON?  J_HUB_PV?  J_PROG?  J_VCC?  U_C?  U_HUB_CVT?
```

These would be ordered as unmatched lines while the CPL places the correctly-named parts.

## Why the `?` happens — measured

Not a mis-annotated schematic:

- schematic `Reference` properties are correct: `C_BULK`, `U_C`, `J_PROG` all present and right
- 114 instance references, all distinct, none unannotated

The cause is that **the board has no schematic links at all**:

```
footprints with EMPTY path (no schematic link): 49 of 49
```

The exporter cannot match a symbol to a footprint, so it falls back to a library default
reference for the eight it cannot resolve by another route.

**This is a project-wide convention, not damage from this campaign.** Every other project board
is the same:

```
tracker/hardware/fg_in_filled.kicad_pcb     39 footprints, 0 with path
tracker/hardware/hub_board_f33.kicad_pcb    14 footprints, 0 with path
tracker/hardware/hub_board_v1.kicad_pcb     30 footprints, 0 with path
```

## What this means for the order

**Bare board: unaffected.** Gerbers and drill are complete and independently verified. A bare
PCB order needs no BOM.

**Assembled board: blocked, twice over** — before you even get to the `?` problem:

1. **Five parts are undecided.** `U_CUT1..4` and `U_HUB_CVT` need a device chosen. This is a
   design decision, not a tooling fix. Nobody can order them, and no amount of re-annotation
   will produce a part number for a part that has not been chosen.
2. **No LCSC numbers anywhere.** The BOM pipeline this project uses for v9
   (`build_jlc_bom.py` reads a hand-maintained `jlc-pcba-work/*.csv`) is how numbers normally
   get attached. That file does not exist for v10 as far as I have found, and `build_jlc_bom.py`
   is hardcoded to the v9 paths.

The `?` fix (re-annotation, or joining by UUID) is the smallest of the three problems and does
not unblock the order on its own.

## What I recommend, in order

1. **Decide the five parts.** `U_CUT1..4` (pyro cut driver, SOT-23-6) and `U_HUB_CVT`
   (PV input, VQFN-16). Nothing else about the BOM matters until these are real devices.
2. **Decide bare-board vs assembly.** If bare board, the BOM/CPL work is not on the critical
   path at all and the 18 opens are the only remaining question.
3. Then re-annotate and attach LCSC numbers.

## What I did not do

I did not choose parts for `U_CUT1..4` or `U_HUB_CVT`. Selecting a pyro driver or a PV converter
is an engineering decision with safety consequences on a flight board, and AGENTS.md does not
give me that authority.
