# The reachability gate gives a FALSE LOST on an AFTER board

**Measured on `batches/SPI1PAIR2`, 2026-11-07.**

## Contradiction

After routing `/SPI1_MISO` and `/SPI1_MOSI`:

| tool | result for `/SPI1_MISO U3.3 <-> U_C.3` |
|---|---|
| `independent_reach_check.py` | **LOST** (341 cells) |
| native `kicad-cli` DRC | connected (29 -> 26 unconnected) |
| `proof.py` | `connected_after: true` |
| `connectivity_check.py` | **CONNECTED** — same-net B.Cu track touches BOTH pads |

The gate was wrong. The other three agree.

## Why

The flood answers **"can a NEW 0.20 mm track be drawn between these two pads"**. That is
the correct pre-batch question: it predicts whether a route is possible.

On an **after** board it is the wrong question. The corridor is now occupied by the
track we just laid, so room for *another* parallel track can legitimately fail while the
net is fully connected. A pad whose only access is a single 0.20 mm track has ~341
free cells around it, not 869 511 — which is exactly the number observed.

So the gate cannot distinguish:

- **regression**: net was connectable, new copper cut it off
- **completion**: net is now connected BY the new copper

Both look like "the flood shrank".

## Correction to how the gate is used

- On a **BEFORE** board: flood is the right instrument (is a route possible?).
- On an **AFTER** board: use **connectivity**, not free space —
  `connectivity_check.py`: does same-net copper touch each terminal?
- The reachability *gate* itself remains valid for its actual purpose: it refused
  `SPI1SCK_UC` and `SCKFIX` where a pair went from connected to NOT connected, which
  DRC and proof also showed. Its use as a post-batch pass/fail on an already-routed
  net is what is invalid.

## Do not "fix" this by loosening the flood

Raising the cell threshold would have hidden a real regression just as easily. The
distinction is the *question*, not the tolerance.

## Reproduce

```
cd docs/analysis
BATCH_DIR=batches/SPI1PAIR2 /usr/bin/python3 -B independent_reach_check.py   # says LOST
/usr/bin/python3 -B connectivity_check.py                                     # says CONNECTED
```
