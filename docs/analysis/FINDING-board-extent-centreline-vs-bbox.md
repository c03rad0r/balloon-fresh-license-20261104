# Board extent: 72.00 × 80.00 mm (centreline), not 72.10 × 80.10

**2026-11-09.** Resolves a duplicate-value conflict that has been recorded as a defect twice in this
campaign. **Both numbers are correct. They measure different things, and the difference is exactly
one Edge.Cuts stroke width.**

## Measured

The board has **one** `Edge.Cuts` object: a single `PCB_SHAPE` (`SHAPE_T_RECT`) with stroke width
**0.100 mm**.

| measurement | value | what it is |
|---|---|---|
| **Centreline extent** | **x 0.000..72.000, y 0.000..80.000 = 72.000 × 80.000 mm** | where the fab cuts |
| Bounding box (stroke inflated by w/2 each side) | 72.100 × 80.100 mm, origin (−0.050, −0.050) | what a bbox or renderer reports |

`72.000 + 0.100 = 72.100` and `80.000 + 0.100 = 80.100`. Exact, not approximate.

## Which one to order

**72.00 × 80.00 mm — the centreline.** A fab quotes outline tolerance against the drawn path, not
against a stroke envelope. The stroke is a drawing property; the cut follows its centreline.

The two numbers were never in conflict. `docs/FINDING-gerber-independent-render.md` describes the
bbox correctly (it even names the `SHAPE_T_RECT` spanning `(−0.05, −0.05)` to `(72.05, 80.05)`), and
`FINDING-cpl-coordinate-transform.md` describes the centreline correctly. A record that quotes
`72.10 × 80.10` as "the board size" is quoting a stroke envelope, which is fine as long as it says
so.

## Consequence for the CPL transform

`H = 80.000`, not `H = 80.100`, and `X0 = Y0 = 0.000`, not `−0.050`.

Using `80.100` produces a **uniform +0.100 mm Y offset on every row** — which is exactly the
systematic error found and corrected in the CPL. That is the practical reason this matters: the
wrong H does not produce a scattered error, it produces a clean constant offset that survives any
mean-based sanity check.

## Reproduce

```
/usr/bin/python3 tracker/hardware/tmp_probes/outline_extent.py
```

Prints stroke widths present, centreline extent, the inflated bbox, and the bbox origin.
`pcbnew` lives in the **distro** python, not the project venv.

## What would change this

If the outline were ever re-drawn as four separate line segments of a different width, the bbox
would still be `centreline + w`, but a bbox that includes arcs or circles would not decompose that
cleanly — re-run the probe rather than assuming.
