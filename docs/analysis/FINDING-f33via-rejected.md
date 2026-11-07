# F33VIA rejected: two legal vias, zero connectivity gain

**2026-11-07, board `e00b98e7`, 15 opens.**

## What was measured first

`/F33_VSENSE` has **4 fragments**. My probe `why_blocked.py` reported two pairs at *identical*
coordinates on different layers with **no foreign copper within 0.6 mm**:

```
frag1 (14.950, 6.650) B.Cu  ==  frag3 (14.950, 6.650) F.Cu
frag1 (21.850, 8.350) B.Cu  ==  frag2 (21.850, 8.350) F.Cu
```

That looked like the minimal repair: two vias joining copper that already exists on both faces at
the same point, instead of routing 40 mm.

## What was built and verified

`f33_via.py` placed **two 0.600/0.300 vias**. Both passed every guard:

```
site (14.950, 6.650):  F.Cu='/F33_VSENSE'  B.Cu='/F33_VSENSE'
site (21.850, 8.350):  F.Cu='/F33_VSENSE'  B.Cu='/F33_VSENSE'
both layers carry the net, land is clear of foreign copper at S1 + guard
DRC: 0 errors
```

## Why it was rejected anyway

**Opens did not move: 15 -> 15.** The batch added two vias and closed nothing.

The reason is in the remaining record:

```
Pad 21 [/F33_VSENSE] of U1 on F.Cu
Track [/F33_VSENSE] on B.Cu, length 3.8000 mm      (18.75, 10.25)
```

The real open is **Pad 21 of U1 on F.Cu against a B.Cu track 3.8 mm elsewhere** — a pad-to-track
gap that needs an actual route from the pad, not a layer change at some other point. The two vias
joined fragments that were already connected to each other by other paths; they did not touch the
gap that DRC reports.

Adopting would have added two vias, changed the copper, and left the board exactly as connected as
it was. **Rejected: zero benefit for added geometry.** The S1 rule from the campaign brief is that a
batch must reduce opens, and this one does not.

## What I got wrong in the diagnosis

`why_blocked.py` found the *closest* fragment pairs and stopped there. The closest pair was not the
*broken* pair. A net can have fragments 0.000 mm apart on different layers that are already joined
through the rest of the net, while the genuinely disconnected piece is a pad 3.8 mm away.

The correct first question for a multi-fragment net is **"which fragment contains the pad or track
that DRC names"**, not "which two fragments are nearest".

## Tool defects fixed getting here

- `why_blocked.py` multiplied stored fragment points by 1e6 again. The points are **raw
  nanometres** (`key()` rounds the pcbnew ints directly), so the extra multiply overflowed SWIG's
  int32. Third units bug of this session.
- `closest_gap.py` accepted a **1-point path** as ROUTABLE. A 1-point "path" is the search
  returning its start cell unchanged and joins nothing. Added a contract: `len(path) >= 2`.

## State

Board unchanged at **15 opens** (`e00b98e7`). Nothing adopted from this attempt.

## Next for /F33_VSENSE

Route from **Pad 21 of U1 at (20.435, 51.65)** to the B.Cu track at **(18.75, 10.25)** — a real
pad-to-track run, not a layer change. That is the gap DRC actually reports, and it is the class
`batch.sh` handles (`U1.21` to the track's far end).
