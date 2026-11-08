# CPL coordinate transform: KiCad's Y is negative, JLCPCB needs `y + 80`

**2026-11-07, `latest.kicad_pcb` `ec2a7af8`, board 72.00 x 80.00 mm.**

## The problem

`kicad-cli pcb export pos` writes **negative Y** for nearly every part:

```
Ref,Val,Package,PosX,PosY,Rot,Side
"D_BP1","SS24","D_SMA",4.000000,-33.000000,0.000000,bottom
```

Measured ranges: **X 0.00 … 72.00, Y −80.00 … 0.00**, with 47 of 48 rows negative in Y.

JLCPCB expects origin at the **bottom-left with Y positive upward**. Submitting the raw export
would place every part mirrored about the horizontal centre line.

## The correct transform, derived not assumed

I first guessed `board_y == cpl_y + 80` and it matched only **3 of 48** rows. Measuring the
alternatives against actual board coordinates:

| hypothesis | matches |
|---|---|
| `board_y == -cpl_y` | **48 / 48** |
| `board_y == 80 - abs(cpl_y)` | 3 / 48 |
| `board_y == 80 + cpl_y` | 3 / 48 |

KiCad's internal Y points **down** from a top-left origin, and the pos exporter expresses that as
a negative value. Therefore, for a board of height `H`:

```
jlc_y = H - board_y = H - (-cpl_y) = H + cpl_y
```

with `H = 80.0 mm` here:

```
jlc_y = 80.0 + cpl_y
```

X and rotation pass through unchanged (X already 0…72, rotations already in degrees with the
side flag correct).

## Verified output

`board-cpl-jlc.csv`, 48 rows, JLCPCB column names:

```
Ref,Val,Package,MidX,MidY,Rotation,Layer
```

ranges: **X 0.00 … 72.00, Y 0.00 … 80.00, all Y non-negative**, matching the board extents exactly.

Spot checks against board coordinates:

```
D_BP1  board ( 4.00, 33.00)  ->  MidX  4.0000  MidY 47.0000
D_BP2  board (29.00, 76.00)  ->  MidX 29.0000  MidY  4.0000
D_BP4  board (29.00,  4.00)  ->  MidX 29.0000  MidY 76.0000
```

Both faces are represented: 38 top, 10 bottom, and `Layer` carries `top`/`bottom`.

## Limits

- This corrects the **coordinate convention only**. The BOM still has 8 references carrying a
  `?` that do not join to these rows (`FINDING-bom-reference-mismatch.md`), so the package is
  still not assembly-ready.
- Rotation convention was not independently verified against JLCPCB's expectations for
  bottom-side parts (bottom rotations are often mirrored in fab tools). The values pass through
  unchanged, which is the usual convention, but this deserves a visual check against the
  gerbers before an assembly order.
- No gerber-viewer cross-check was done.

## Reproduce

```
kicad-cli pcb export pos --format csv --units mm --output cpl.csv <board>.kicad_pcb
# then jlc_y = 80.0 + PosY
```
