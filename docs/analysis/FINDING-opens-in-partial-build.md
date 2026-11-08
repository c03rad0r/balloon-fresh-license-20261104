# Two of the five REAL opens cannot matter in a partial build — and my clearance arithmetic was wrong a third time

**2026-11-08, board `0602c7c8`, 30 assembled / 19 DNP.**

## 1. The arithmetic error, third occurrence, same root cause

Testing whether a new 0.200 mm track can pass between a pad and a neighbour, I have now used three
different, all wrong, budgets:

```
claim 1 (FINDING-jlcpcb-capability-vs-S1)   0.200 clearance             -- omitted the track width
claim 2 (CORRECTION-clearance-budget)        0.200 + 0.200 track = 0.400 -- omitted ONE clearance
claim 3 (FINDING-trap-options-costed)        0.150 + 0.200 = 0.350 ...   -- still claim 2's model
```

The correct requirement, for a track running in the channel between a pad edge and a track edge:

```
G >= C (to the pad) + W (its own width) + C (to the other track)  =>  G >= 2C + W
=>  W <= G - 2C
```

At S1 (C = 0.200): `W <= G - 0.400`. At the fab minimum (C = 0.090): `W <= G - 0.180`.

**Claim 2 and claim 3 both omitted the second clearance**, so both understated the requirement by
exactly 0.200 mm — and both looked plausible. This is the third instance of the same shape: the
instrument was wrong, the board was not.

## 2. What the corrected arithmetic actually says — measured per gap

```
                nearest blocker      max width at S1   at fab
/EN     U1.3    /SPI2_MISO  0.350    -0.050            +0.170
                /SPI2_MOSI  0.562    +0.162            +0.382
                +3V3        0.720    +0.320  FITS      +0.540
                +3V3        0.802    +0.402  FITS      +0.622

/SPI2_SCK U1.4  /SPI2_MOSI  0.200    -0.200            +0.020
                /SPI2_MOSI  0.250    -0.150            +0.070

/F33_VSENSE     /U3_CS_N    0.250    -0.150            +0.070
                /SPI1_SCK   0.335    -0.065            +0.155
                /SPI1_SCK   0.415    +0.015            +0.235

/VSCAP  R_BAL1.1 /SCAP_MID   0.282    -0.118            +0.102
```

**Only `/EN` has a channel that fits at S1** — through the `+3V3` side at 0.720/0.802 mm, not toward
`/SPI2_MISO`.

A correction on `/EN`, because the geometry is not what "pad-local trap" implies: **`U1.3` is at
(11.050, 36.430) and its destination `J_PROG.3` is at (31.000, 59.780)** — 31 mm away. So `/EN` is not
a pad-to-pad pocket at all. It is a long net path whose first escape from the module is tight. A
0.720 mm channel exists on the `+3V3` side, and the router declined it anyway — which points at
`/SPI2_MISO` and the module body on the other sides, not at the `+3V3` tracks. I have not isolated
which wall the router actually hit, so I am not claiming the `+3V3` side is usable; only that the
arithmetic there is not the obstacle.

So the "four track nudges of 0.008–0.200 mm" recommendation in `FINDING-trap-options-costed.md` was
built on claim 3's budget and **does not survive the corrected arithmetic**:

- `/VSCAP` needs a 0.102 mm track at fab clearances — below S1's frozen 0.200, so it is not S1 work.
- `/SPI2_SCK` needs 0.070 mm at fab — the same.
- `/F33_VSENSE` needs 0.235 mm at fab, which is a 0.235 track but only by dropping clearance to 0.090.
- `/EN` is the only one whose *nearest measured gap* admits a 0.200 track at S1, and only on the
  `+3V3` side — but see the correction above: its geometry is a long net, not a pocket.

`reach_fast.py` says all five are **pad-local pockets** on F.Cu, which is the same conclusion from a
completely different instrument: a pocket means the pad is enclosed, and nudging one wall of an
enclosure does not open it.

## 3. The finding that matters more: two of the five opens are not defects in THIS build

The partial-assembly decision (30 fitted / 19 DNP) makes this question answerable, and it was never
asked before because the population was never applied.

| net | endpoints | status in the partial build |
|---|---|---|
| `/EN` | `U1.3` → `J_PROG.3` | **functional** — both parts fitted |
| `/SPI2_SCK` | `U1.4` → `U2.12` | **not functional** — `U2` is DNP |
| `/F33_VSENSE` | `U1.21` → B.Cu track | **functional** — `U1` fitted; the track is the F33's own sense net |
| `/VSCAP` | via → `R_BAL1.1`, zone → `C_CAP1.1` | **the C_CAP1 record is not functional** — `C_CAP1` is DNP |
| `/W2_SOLAR_N` | B.Cu track → F.Cu track | **not an open** — the gate classifies it `two-face`, excluded by proof |

`/SPI2_SCK` is the decisive one: **the net has exactly two pads**, `U1.4` and `U2.12`. With `U2` not
fitted, the net is **single-pin**. There is nothing to connect it to. The 0.200 mm gap that the
router could not thread leads to a pad that will be empty.

`/VSCAP` is the same class of thing but less stark: `/VSCAP` has eleven pads and six of them are DNP,
but `D1`, `U7`, `R_DIV1` and `R_BAL1` are fitted, so the net does need its copper. The specific DRC
record is the `VSCAP_BCu` zone not reaching `C_CAP1`'s PTH — and `C_CAP1` is a supercap that
decision D4 leaves off the board.

## 4. What this does NOT mean

- **It does not make DRC clean.** The records exist and the gate still reports REAL 5. The board has
  five genuinely unconnected copper items.
- **It does not mean the opens are ignorable for a full build.** Fit `U2` and `/SPI2_SCK` becomes a
  real single-connection defect. Fit `C_CAP1` and the zone-to-PTH record matters.
- **It does not lower the count.** Reporting "3 functional opens" would be the same class of error as
  the eleven-records-vs-ten-pairs mistake: quoting a number without saying what it counts. The gate
  number stays 5; the build-specific number is separate and both must be stated.

## 5. What I am not doing

- **Not nudging tracks.** The corrected arithmetic shows three of four need sub-S1 widths, and the
  fourth (`/EN`) is not obviously blocked by the track I proposed to move — its blocker is
  `/SPI2_MISO` at 0.350 but there is a `+3V3` channel at 0.720 that the router already declined. A
  nudge chosen on a wrong budget would be copper moved for no reason.
- **Not claiming the opens are solved.** Two are build-specific non-issues; three are real and
  unchanged.

## Reproduce

    /usr/bin/python3 -B docs/analysis/feasible_track_width.py
    /usr/bin/python3 -B tracker/hardware/check_unconnected_exclusions.py \
        docs/analysis/bulk-route-20261107/latest.kicad_pcb --drc drc.json --expect-real 5
