# /VSCAP vias, resolved: two genuinely dead barrels, and the island is NOT orphaned

**Measured 2026-11-07 on `latest.kicad_pcb`. This supersedes part of
`FINDING-vscap-dangling-vias.md`, which called island 1 "orphaned".**

## The per-via truth

For each `/VSCAP` via: which B.Cu pour island it sits in, and what copper it touches on each
face (land radius 0.3 mm, Collide at 1 um).

| via | island | F.Cu copper touched | B.Cu track touched | status |
|---|---|---|---|---|
| (46.5287, 54.7197) | 0 | 1 TRACK | 0 | connected via F.Cu |
| **(36.0000, 40.0000)** | 0 | **0** | **0** | **DEAD** |
| **(6.6000, 58.5997)** | 1 | **0** | **0** | **DEAD** |
| (41.8394, 42.6522) | 0 | 1 TRACK | 0 | connected via F.Cu |
| (3.3329, 46.2611) | 1 | 1 TRACK | 0 | connected via F.Cu |
| (48.7963, 56.6197) | 0 | 1 TRACK | 0 | connected via F.Cu |

Two vias touch nothing on either face beyond the pour they sit in. **Those are exactly the
two vias DRC reports as `via_dangling`.** DRC is right, and my earlier claim that "all six sit
in the pour and are therefore connected" was too coarse: sitting in a pour is not the same as
being part of the net through that pour.

## Island 1 is NOT orphaned

Because via (3.3329, 46.2611) sits in island 1 **and** touches an F.Cu `/VSCAP` track, island 1
is connected to the net through that via. My earlier statement — "a 104 mm2 orphaned island
that reaches the main net only if something on F.Cu bridges it" — was wrong on the word
"orphaned". Something on F.Cu already bridges it. **Withdrawn.**

What remains true and useful: island 1 is a separate pour region, and it is the only reason
the two-island structure exists. It is connected, so nothing needs to be routed to it.

## So the real defects are two dead vias, and they are easy to characterise

- **(36.0000, 40.0000)** — in island 0, in the middle of the main pour, touching no copper on
  either face. A plated barrel into solid pour that carries nothing. Harmless electrically
  (the pour around it already connects) but it is a via that does no work.
- **(6.6000, 58.5997)** — in island 1, touching nothing. Island 1 is connected via the *other*
  via at (3.3329, 46.2611), so this one also carries nothing.

Neither dead via breaks connectivity. Both are vestigial: something routed through them
previously and the tracks have since moved. The clean fix is to **delete** them, which removes
both `via_dangling` warnings and touches no other copper. That is a strictly smaller change
than adding copper, and it is nowhere near C10 (x 39.5-43.5).

## Correction to my own earlier note

`FINDING-vscap-dangling-vias.md` said island 1 was orphaned and that fixing it would close
"a zone-pair open and two warnings at once". The zone-pair open is real
(`Zone 'VSCAP_BCu' on B.Cu || Zone 'VSCAP_BCu' on B.Cu`) but it is a zone-to-zone record, not
evidence of an orphaned island. **Island 1 is connected. The two warnings are dead vias.**

## Reproduce

```
/usr/bin/python3 -B docs/analysis/vscap_island_repair.py
```
(the per-via table above is produced by the same probe family; the closest approach between
islands is 6.825 mm at (0.450,39.600)->(2.950,45.950), entirely outside the frozen region)
