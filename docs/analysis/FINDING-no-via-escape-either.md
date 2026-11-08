# Trapped pads: no via escape either — the land radius, not the track width, is the limit

**2026-11-07, board `e00b98e7`, 15 opens. Extends `FINDING-escape-measurements.md`.**

## The question this answers

The escape probe showed a 0.200 mm **track** cannot leave the four trapped pads in any of 12
directions. That leaves one rules-compliant option untested: a **normal 0.600/0.300 via** placed in
the clear space next to the pad, reached by a short 0.200 mm stub, continuing on the other layer. No
drill-in-pad, nothing added inside the pad, fully within S1.

The constraints differ:

| | needs from centreline/centre |
|---|---|
| 0.200 mm track | 0.100 half-width + 0.200 clearance = **0.300 mm** |
| 0.600 mm via land | 0.300 land radius + 0.200 clearance = **0.500 mm** |

So a pad that cannot leak a track might still hand off to a via. It cannot.

## Result

```
/EN       pad U1.3 (11.050, 36.430)  scanning 3.0 mm
   NO reachable via site within 3.0 mm
/SPI2_SCK pad U1.4 (11.050, 37.700)  scanning 3.0 mm
   NO reachable via site within 3.0 mm
```

## Independent check of the widest direction

`/EN` had its widest track-clear run at 210° (1.40 mm). Testing whether a via fits along that exact
bearing:

```
210deg 0.60 mm -> (10.530, 36.130)  blocked by pad U1.2
210deg 0.80 mm -> (10.357, 36.030)  blocked by pad U1.2
210deg 1.00 mm -> (10.184, 35.930)  blocked by pad U1.2
210deg 1.20 mm -> (10.011, 35.830)  blocked by trk +3V3, /SPI2_MOSI, pad U1.2
```

**Pad U1.2 blocks every candidate.** The 1.40 mm of clear *track* corridor does not contain enough
clear *via* space, because the land needs 0.500 mm of clearance radius where the track needed 0.300.

## A bug in the first version of this probe, and its correction

The first run reported **95 reachable sites** for `/EN` and 31 for `/SPI2_SCK`, nearest 0.354 mm. All
of them were **inside the pad copper**:

```
U1.3 centre (11.050, 36.430), pad 1.500 x 0.900 mm -> half-extents 0.750 x 0.450
  reported site (10.700, 36.380), offset (-0.350, -0.050)  ->  INSIDE THE PAD
```

The probe used a fixed **0.35 mm minimum distance from the pad centre**, which is smaller than the
pad's own **0.750 mm** half-extent. Those "sites" were drill-in-pad proposals — the one thing this
probe existed to avoid, and not authorised. The fix requires the **0.300 mm drill circle** to be
geometrically clear of the pad's copper (`Collide`), which is the actual constraint, rather than a
guessed number.

Worth recording: the wrong version produced a **95-strong list of confident, plausible sites**, which
is exactly the kind of output that gets adopted without checking. The tell was that the nearest site
was closer to the pad centre than the pad's own half-width.

## Consequence

All four trapped pads (`/VSCAP`, `/F33_VSENSE`, `/SPI2_SCK`, `/EN`) are enclosed for **both** a
0.200 mm track and a normal 0.600/0.300 via at S1. There is no rules-compliant escape left that does
not involve one of:

1. accepting the open,
2. a local clearance reduction below S1,
3. moving an enclosing track or pad, or
4. drill-in-pad / via-in-pad (explicit authorisation, fab capability check).

## Reproduce

```
VIA_TARGETS="/EN:U1:3,/SPI2_SCK:U1:4" /usr/bin/python3 -B docs/analysis/via_escape.py
```
