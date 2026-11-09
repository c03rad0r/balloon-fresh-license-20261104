# Which parts are on the back, and is that intentional?

**2026-11-09.** Answers: *are `D_BP1` and `U_CUT` supposed to be on the back?*

Measured from `work.kicad_pcb` with `tracker/hardware/tmp_probes/which_side2.py` and `dbp_check.py`.
`IsFlipped()` is the authority — not a coordinate guess.

## 11 of 49 footprints are bottom-side

| ref | value | x | y | status |
|---|---|---|---|---|
| `D_BP1` | SS24 | 4.00 | 33.00 | **JLC-placed** |
| `D_BP2` | SS24 | 29.00 | 76.00 | **JLC-placed** |
| `D_BP3` | SS24 | 68.00 | 33.00 | **JLC-placed** |
| `D_BP4` | SS24 | 29.00 | 4.00 | **JLC-placed** |
| `U3` | LoRa2021 | 20.90 | 16.70 | hand-fit |
| `U_C` | LoRa2021 | 43.70 | 16.70 | DNP |
| `J_VCC` | VCC select jumper | 18.00 | 5.00 | DNP |
| `U_CUT1` | SOT-23-6 | 7.50 | 47.00 | DNP |
| `U_CUT2` | SOT-23-6 | 36.00 | 70.50 | DNP |
| `U_CUT3` | SOT-23-6 | 62.50 | 40.00 | DNP |
| `U_CUT4` | SOT-23-6 | 43.00 | 2.00 | DNP |

**Yes — bottom placement is by design, not an accident.** ADR-118 states: *"Two-sided population is
now the default"* and *"`U_C` — NEW bare LoRa2021 LP — Site C (the missing third slot; **may sit on
the back side**)."*

## Why the diodes are on the back — they are at the corners

`D_BP1..D_BP4` sit 4.00 mm from the left edge, 76.00 mm up, 68.00 mm across, 4.00 mm down. Those are
the **four wing entry points** (`J_W1` x=0, `J_W2` y=80, `J_W3` x=72, `J_W4` y=0, all at 40 mm).

The bypass chain physically lives at the wing seams, and the back is the only place with room once
the four wing sockets occupy the top perimeter. ADR-046 §2.1 and ADR-054 §2.2 require these to be
**hub-side**, not wing-side: a cut jettisons the wing, so a diode on the external panel is destroyed
with the wing it was meant to protect.

## All four are correctly wired — the series chain is intact

| part | pad 1 | pad 2 |
|---|---|---|
| `D_BP1` | `/W1_SOLAR_P` (21 tracks, 1 via) | `/W1_SOLAR_N` (55 tracks, 2 vias) |
| `D_BP2` | `/W1_SOLAR_N` | `/W2_SOLAR_N` (477 tracks, 7 vias) |
| `D_BP3` | `/W2_SOLAR_N` | `/W3_SOLAR_N` (322 tracks, 2 vias) |
| `D_BP4` | `/W3_SOLAR_N` | `GND` (39 tracks, 48 vias, **zone**) |

Every pad is on `B.Cu` with real copper. This is the per-cell bypass topology of ADR-046 §2.1: a
shaded or dead wing gets bypassed instead of dragging the whole series string down.

## Why `U_CUT1..4` are on the back — they are F33 socket clones

`U_CUT1..4` are `SOT-23-6` and their value reads *"latched cut driver + cut-s…"* — the `SN74LVC1G373`
latch. They are **cut-down copies of the F33 PA socket** (which is `U2`, 39.65 × 26.03 mm, top side).
There is no top-side room for four more driver sites, so they went to the back.

**All four are DNP.** They are not on the order at all, so their side is currently academic — but it
matters if they are ever fitted: they must be fitted from the bottom.

## The one that matters: `U3` is on the back

`U3` is the **LoRa2021 that carries the 2.4 GHz link** — the part the operator kept as *"good
enough"* in place of `U_C`. It is a **bottom-side** part.

It is hand-fit, so it does **not** affect the top-only order: JLC never touches it either way. But
it does affect how you assemble:

- The four `D_BP` diodes (bottom) and `U3` (bottom) are on the **same side**
- Solder the diodes **first** — they are reflow-safe and small
- Then `U3` and `U_LORA1280` last, since the LoRa2021 is castellated and needs hand alignment
- Work the bottom face in one session rather than flipping the board repeatedly

## Does this change the top-only decision?

**No, and the reason is worth stating precisely.** The top-only variant moves only `D_BP1..D_BP4`
from the JLC CPL to the hand-fit list. `U3`, `U_C`, `J_VCC` and `U_CUT1..4` were *already* outside the
CPL, so they are unaffected.

The consequence to accept: **you hand-solder five bottom-side parts, not four.** Four SS24 diodes
plus `U3`. That was already true before the top-only variant existed — the diodes are simply the
only bottom parts JLC used to place.

## Could the diodes be moved to the top?

Not without rework: the four wing sockets occupy the top perimeter at the same coordinates, and the
bypass chain has to reach the wing seams. Moving them would be a placement change requiring a fresh
ADR-120 R3 human placement gate, on a board that is otherwise ready to order. Not worth it for four
easy 2-pad SMA parts.
