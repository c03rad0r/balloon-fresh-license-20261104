# Dead ends: 7 real, and a pixel claim confirmed against one

## The finding

The spatial reviewer flagged "a track ends in empty space, about (235, 950) px" on **three separate
renders** of different candidates. Three repeats of the same claim is either a real object or a
rendering artefact, and those have different fixes — so it was worth pinning to an object.

`find_dead_ends.py` reports every strict dead end in **board millimetres** and the pixel each lands
at, given the render's own scale (1200 px for 72.1 mm + 40 px margin = **16.09 px/mm**).

```
/GNSS_PPS    F.Cu  mm=(12.40, 57.20)  px=(220, 940)   <-- the flagged one
/GNSS_PPS    F.Cu  mm=(22.00, 50.50)  px=(374, 833)
/USB_DN      B.Cu  mm=(22.45, 49.75)  px=(381, 820)
/USB_DN      B.Cu  mm=(23.65, 51.25)  px=(401, 845)
/E28_BUSY    B.Cu  mm=(32.75, 63.15)  px=(547, 1036)
/E28_BUSY    B.Cu  mm=(32.77, 63.15)  px=(547, 1036)   <-- duplicate, 0.02 mm apart
/SPI1_SCK    B.Cu  mm=(43.75, 70.30)  px=(724, 1151)
```

**The reviewer's (235, 950) maps to `(220, 940)`** — 16 px off, inside its own "approximately". So the
claim is a real dead end at **mm (12.40, 57.20)** on `/GNSS_PPS`, not an artefact. Confirmed by
measurement, not by agreeing with it.

An earlier looser check reported **750** dead ends because it counted every track-to-track joint as a
terminal. The definition here is strict and that is the whole point of the tool:

> an endpoint that is not shared with another track on the same layer+net, **and** not within 0.05 mm
> of a pad on that net, **and** not within 0.05 mm of a via on that net.

## Two things these are not

- **Not orphaned nets.** All 7 nets connect real pads elsewhere, so these are stub fragments in the
  middle of a route, not nets with nowhere to go.
- **Not DRC-visible.** kicad-cli reports 0 errors on this board; a dead-end stub on a connected net
  is not an unconnected item. Only a spatial read or this tool catches it.

`/E28_BUSY` and `/E28_RESET_N` are also **legacy E28-era net names** on a board carrying
`U_LORA1280` (ADR-139). Worth renaming at the next revision regardless of routing.

## FreeRouting second opinion — armed, not yet answered

`freerouting_second_opinion.py` exports DSN, routes with the 2.2.4 jar, imports the `.ses`, and
reports the DRC delta. It **refuses to treat a lower unconnected count as a win**, because
FreeRouting may re-route every net and that would discard 6 verified solar routes, 37 GND stitches,
12 3V3 taps, the In2 plane and the /VSCAP taps.

**Measured risk that must be checked before any merge:** the DSN declares `In1.Cu` and `In2.Cu` as
`(type signal)`, so FreeRouting is permitted to route traces **through the GND and 3V3 planes**. The
input already carries 4 such pre-existing segments (`/F33_BUSY`, `/GNSS_PPS`). Any output must be
checked for *new* inner-layer copper before it is considered at all.

Status: the run has exceeded 11 minutes without producing a `.ses` on 20 passes. Not yet a result,
and not yet a failure.
