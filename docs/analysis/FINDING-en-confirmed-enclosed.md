# /EN retried at five seed radii: genuinely enclosed, and the parameter is provably live

**2026-11-07, board `e00b98e7`, 15 opens.**

## Why retry /EN

Two reasons to doubt the earlier `NO PATH at 164 steps`:

1. The verdict was from a **25-open board**; five batches have changed copper since.
2. `seed_radius` defaulted to 2 — a **0.2 mm** lattice radius, smaller than the pad's own
   1.500 x 0.900 mm copper. `collide_router.route()`'s own docstring warns that every seed can then
   land inside the pad's clearance pocket while the real mouth of the terminal is a step further out.

`/EN` also measured the **most room** of the four trapped pads (widest clear run **1.40 mm**), so it
was the one most worth retrying hardest.

## Result

```
/EN  U1.3 (11.050,36.430) -> J_PROG.3 (31.000,59.780)  30.71 mm apart
  seed_radius=2   NO PATH  search exhausted 164 steps
  seed_radius=4   NO PATH  search exhausted 164 steps
  seed_radius=6   NO PATH  search exhausted 164 steps
  seed_radius=8   NO PATH  search exhausted 164 steps
  seed_radius=10  NO PATH  search exhausted 164 steps
```

**Identical step count at every radius.** That is the signature of an inert parameter, so before
believing it I checked the source. `seed_radius` is genuinely wired: `R = seed_radius` drives the
`range(-R, R+1)` loops that build `starts` and `goals`, and the function returns
`no free terminal cell` when either set is empty. It is **not** a dead parameter.

So the interpretation is: at every radius from 0.2 mm to 1.0 mm, free seed cells exist on both
terminals, the search starts from all of them, and it still exhausts after 164 expansions. The
explored pocket is the same size regardless of where it is seeded from — which is what an enclosure
looks like, not what a bad seed looks like.

## Confirms the enclosure measurement

The radial escape probe found `/EN` blocked in **all 12 directions**, widest clear run 1.40 mm, by
`/SPI2_MISO`, `/SPI2_MOSI`, and pads `U1.2` / `U1.4`. The router and the probe now agree from two
independent directions:

- straight-line: every direction blocked by named foreign copper within 1.4 mm
- search: 164 expansions and stop, invariant to seed radius

## All four real gaps are now settled

| net | escape (widest clear, free dirs) | router | conclusion |
|---|---|---|---|
| /VSCAP | 0.40 mm, 0/12 | 186 steps | enclosed (C10 pinch) |
| /F33_VSENSE | 0.90 mm, 0/12 | 138 steps x4 targets | enclosed |
| /SPI2_SCK | 1.00 mm, 0/12 | 118 steps | enclosed |
| /EN | 1.40 mm, 0/12 | 164 steps, invariant to seed 2..10 | enclosed |

No further routing at 0.200/0.200 will close these. Each needs a decision, not another attempt.

## Reproduce

```
/usr/bin/python3 -B docs/analysis/en_wide_seed.py
ESCAPE_TARGETS="/EN:U1:3" /usr/bin/python3 -B docs/analysis/escape_probe.py
```
