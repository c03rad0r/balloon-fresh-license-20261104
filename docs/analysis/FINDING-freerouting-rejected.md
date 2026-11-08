# Freerouting: 15 -> 10 opens, but the 5 "wins" are bought with clearance violations

**2026-11-08, board `e00b98e7`, freerouting v2.5.0 (JAR build), S1 forced in the DSN.**

## Result

```
live        15 opens, 16 violations
freerouted  10 opens, 63 violations
```

Gate-by-gate:

```
gate 1  opens decrease            15 -> 10          PASS
gate 3  electrical errors          1 -> 82          FAIL
            clearance               0 -> 30
            hole_clearance          0 -> 10
            track_width             0 -> 6
gate 4  inner plane area          unchanged         PASS
```

The planes survived: In1 5345.51 mm2 and In2 5122.21 mm2, both byte-identical before and after. So
freerouting did not cut the ground reference.

## The 5 closed opens are not real closures

Nets freerouting "closed": `/CUT_SENSE_W1`, `/W1_SOLAR_N`, `/W1_SOLAR_P`, `/W3_SOLAR_N`, and it
newly OPENED `/F33_VCC` as a regression.

Attributing every clearance / hole_clearance / track_width violation to nets:

```
/CUT_SENSE_W1    4 violation(s)  INVOLVED
/W1_SOLAR_N     13 violation(s)  INVOLVED
/W1_SOLAR_P      4 violation(s)  INVOLVED
/W3_SOLAR_N     17 violation(s)  INVOLVED
```

**Every single net it closed carries violations.** These are not four clean escapes found by a better
router; they are four connections made by routing closer than the S1 rule. Outcome (B) from the
pre-registered possibilities, not (A). The count went down because the rule was broken, not because
the board got better.

So my own router's NO PATH verdicts on those nets stand unchallenged. A more capable router did not
find a legal path either -- it found an illegal one.

## What freerouting did that my router did NOT do, and that the DRC confirms is wrong

It routed through the inner planes. Example from the DRC:

```
Clearance violation (rule 'S1 frozen JLCPCB clearance' 0.2000 mm; actual 0.0000 mm)
  Track [/SCAP_MID] on In1.Cu, length 6.8000 mm
  Zone 'GND_In1' [GND] on In1.Cu, priority 0
```

A signal track laid on In1.Cu at 0.000 mm from the GND pour. In1 is a solid GND plane; putting a
signal on it shorts the plane. Freerouting also logged, on loading:

```
Layer 'F.Cu' contains a power plane ... configured for plane routing
Layer 'In1.Cu' ... 'In2.Cu' ... 'B.Cu' ... configured for plane routing
```

It interpreted all four layers as planes and then routed signal into them. That is a structural
misreading of this board, and it is the origin of most of the 20 hole_clearance and 6 track_width
violations too.

## Verdict

**REJECTED.** Not adopted, and the live board is untouched at `e00b98e7` / 15 opens.

The experiment was still worth running and settles a question the campaign had been circling:

- **A mature push-and-shove router was tried on the real board at forced S1, with 8 threads, 100
  passes, and 14 minutes of compute. It closed 5 opens by violating clearance and opened 1 net.
  Its own final unrouted list names the same nets my router does: `/EN` U1-3, `/VSCAP`, `/SPI2_SCK`,
  `/F33_VSENSE`, and the `J_W3` assembly lands.**

Two independent routers, different algorithms, different failure modes, same conclusion about which
geometry is closable at S1. That is much stronger evidence than either router alone.

## Operational notes for reuse

- The **native-image CLI build crashes**: `UnsupportedFeatureError: SerializationConstructorAccessor
  class not found for app.freerouting.board.model.items.ComponentOutline`. It cannot serialise the
  board for its own hashing during the autoroute loop. **Use the JAR**, which runs on the JVM:
  `java -Djava.awt.headless=true -jar fr.jar ... --gui.enabled=false --analytics.enabled=false`
- KiCad's DSN export writes `(clearance 50 (type smd_smd))` even though the Default netclass is
  exactly 0.200/0.200/0.600/0.300. That is an export artefact and freerouting would honour it, so it
  must be rewritten to 200 before routing. See `fr_prepare.py`.
- Freerouting needs `.kicad_dru` **and** `fp-lib-table` beside the candidate, same as every other
  batch in this campaign.
- Its "82 pre-existing violations" warning on load was accurate, and is the tell that it intends to
  route through the plane pours.

## Files

- `docs/analysis/fr_export.py` -- DSN export + rule/layer inventory
- `docs/analysis/fr_prepare.py` -- force S1, count carried wiring
- `docs/analysis/fr_import.py` -- SES import + 4 gates
- `docs/analysis/fr_diff.py` -- which opens closed / opened
- `docs/analysis/fr_attribute.py` -- attribute violations to nets
- `docs/analysis/bulk-route-20261107/freerouting/` -- board.dsn, board-s1.dsn, board.ses, fr-jar.log
- `docs/analysis/bulk-route-20261107/batches/FREEROUTING/routed.kicad_pcb` -- rejected candidate
