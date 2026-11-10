# Two-sided pressure board — measured, and the reason NOT to adopt it

**DESIGN CANDIDATE · NOT ROUTED · NOT FAB READY · PENDING OPERATOR SIGN-OFF**

Built to answer the operator's brief: *"can the parts be placed more densely? are we using
both sides… lets not waste space"*, and to satisfy `AGENTS.md` §1b, which requires the smallest
outline to be **measured** both single-sided and two-sided before either is claimed.

Base: master `04219c23`. Generator: `twosided_qualified.py`, deterministic
(`sha256 902e4ea4…cea67b87`, verified by full rebuild + `cmp`).

## Measured outline comparison

Every denominator is stated; courtyard area is clipped to the outline.

| metric | 80×60 (historical) | **65×50 single-sided** | 52×46 two-sided |
|---|---|---|---|
| board area mm² | 4800 | **3250** | **2392** (−50.2 % vs 80×60, −26.4 % vs 65×50) |
| parts top / bottom | 26 / 0 | **26 / 0** | **19 / 7** |
| courtyard clipped T / B mm² | 785.0 / 0 | 785.0 / 0 | 673.0 / 112.1 |
| occupancy T / B % | 16.35 / 0 | 24.15 / 0 | 28.13 / 4.68 |

The 65×50 figures were independently reproduced (785.010 mm², 24.15 %, 197.6 mm² free outside
the motor reservation) — the two studies agree.

So the two-sided direction **is** real: 26 % smaller, past the 10 % threshold in §1b.

## Why it still must not be adopted: the module vendor forbids it

ESP32-S3 Hardware Design Guidelines, PCB Layout Design, **two-layer** case, verbatim:

> **Layer 2 (BOTTOM): Do not place any components on this layer and keep traces to a minimum.
> Please make sure there is a complete GND plane for the chip, RF, and crystal.**

This board is **2-layer**. The candidate places 7 components on B.Cu, and B.Cu copper coverage
over the module body drops from **97.2 % to 17.6 %** — there is no GND plane under the chip.
A 26 % area saving does not buy back a broken RF/thermal ground reference.

The four-layer case is different: there the guideline says only *"not recommended to place any
components"* on the bottom, which is an advisory rather than a prohibition.

## Concerns raised against the earlier probe, tested rather than asserted

| concern | result |
|---|---|
| (a) Antenna keepout to "restore" | **None existed to restore.** Master and the compact board each carry exactly one rule area — the motor reservation. This candidate adds a second, `module-under-body` (19.50 × 41.20 mm on B.Cu at 18.25, −21.00), which enforces the vendor's bottom-layer instruction over the module. p8 is its negative control. |
| (a) Parts inside U1's courtyard | Bounding-box artifact. U1's courtyard is **T-shaped, 1401.9 mm²**, not the 1977.6 mm² rectangle (+29 %). The 21 mm antenna bar is 1008 mm², of which **1006.8 mm² (99.9 %) is off-board**; only **1.2 mm²** of board exists under it. **Zero parts** intersect the courtyard polygon on either side. |
| (a) Parts in the RF clearance band | 0 parts, 0 foreign pads, 0 tracks — derived from HDG Fig. 26 printed dims (Min 15 / Max 2 / Max 1 / 6). |
| (b) Buck loop integrity | Preserved with **0.000 mm** internal-metric deltas; the cell is translated rigidly. Widths 0.300 mm at 1 oz / 10 °C rise (IPC-2221 advisory); tightest different-net pad gap 0.758 mm, so it fits. |
| (c) PTH land clearance | 18 plated through-hole lands on J1/U1/U2, all present on both faces, worst margin **1.223 mm** against 0.20 mm required. |
| (d) Enclosure clearance | **Still unquantified** — footprints carry no 3D heights. L1 XAL6030 is ~3.1 mm per distributor listings, which is *not* a datasheet citation. |

The probe's genuine defect was **`C4`** — the only part overlapping U1's courtyard (9.89 mm²) and
the only one in the antenna band. This candidate moves it out; the class of defect the probe was
accused of does not exist here.

## Assembly consequences (published fees, checked directly)

| | Economic | Standard |
|---|---|---|
| Sides | **single-sided only** | two-sided supported |
| Minimum single PCB | — | 70×70 mm, **but JLC adds 5 mm rails automatically — not a rejection** |
| Setup | — | **$51.12** two-sided vs $25.56 single-sided |
| Stencil | — | **$16.42** vs $8.21 |
| Fixtures | — | $16.42 + |

## Recommendation

**Do not adopt. Retain 65 × 50 single-sided.**

Two-sided is mechanically clean on every concern tested, but on a 2-layer stackup it contradicts
the module vendor's explicit bottom-layer instruction and removes the GND plane under the chip.
§1b requires this number to be *computed and reported*; it does not require it to be adopted when
a constraint outside the area metric forbids it.

**If the operator wants 52 × 46, the correct path is a 4-layer stackup**, where the vendor
guideline downgrades to "not recommended" — at roughly double the assembly setup cost. That is a
cost decision for the operator, not a measurement I can make for them.

## Negative controls

9/9 pass: 8 poisons each rejected by their *intended* rule, plus a positive control proving the
clean board still passes. Two harness bugs found and fixed — poisons that flipped parts tripped
the side check first (a false pass via substring match), and `board.Remove()` invalidated SWIG
handles (fixed with per-control subprocesses).

## Still open

- Renders must be regenerated from the final board hash so report hashes match.
- `compare_outlines.py` reads the 65×50 board from a scratch path and embeds absolute paths — both
  must be pinned before the table is reviewer-reproducible.
- Enclosure clearance needs a datasheet height, not a distributor listing.
