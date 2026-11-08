# The cut drivers are not "part TBD" — they are electrically incomplete

**2026-11-08, board `322ade1e`, schematic `v10_flight.kicad_sch`, 53 nets.**

This supersedes the framing in `FINDING-bom-not-order-ready.md` §2, which said the five rows have
"no part chosen". Choosing a part would not fix them. **The circuits are not wired.**

## What the board actually shows

Every `U_CUT1..4` is an SOT-23-6 with **three of six pads connected** and three floating:

```
U_CUT1  pad 1  /VSCAP          pad 4  (no net)
        pad 2  GND             pad 5  (no net)
        pad 3  /CUT_SENSE_W1   pad 6  (no net)
```

Identical pattern on `U_CUT2`, `U_CUT3`, `U_CUT4` (nets `/CUT_SENSE_W2/W3/W4`).

`U_HUB_CVT` is worse: a VQFN-16 with **3 of 16 pads + no exposed pad** connected:

```
pad 1  /HUB_PV_P      pad 4-9, 10-16  (no net)
pad 2  GND            pad 17 (EP, 1.10x1.10)  (no net)
pad 3  /HUB_PV_N
```

## And the schematic has no nets to connect them to

All 53 nets on the board, filtered:

```
CUT-related : /CUT_SENSE_W1, /CUT_SENSE_W2, /CUT_SENSE_W3, /CUT_SENSE_W4
HUB-related : /HUB_PV_MID1, /HUB_PV_N, /HUB_PV_P
```

**There is no cut-drive net, no nichrome output net, no arming net, no gate-drive net** — for any
channel. `U_HUB_CVT` has no switching node, no inductor connection, no feedback divider.

## Why this is not a BOM problem

ADR-051 §2.5 specifies the cut channel in detail:

- one channel per wing, **nichrome wire**, MOSFET (IRLML2502 named), ~0.5 g per channel
- powered from **VSCAP** (raw supercap node, post-BAT54, pre-LDO) so a cut works with the
  converter dead — **this is the only one of the four requirements that is wired**
- drive must be a **latched one-shot**: firmware NVS "fired" flag per channel plus a hardware
  series gate requiring an explicit arming sequence
- fires must not overlap; ~2.59 J per cut; max on-time ≈193 ms; bank-voltage precondition

Against that specification the board has:

| ADR-051 §2.5 requirement | on the board |
|---|---|
| VSCAP power | **present** (pad 1) |
| ground | **present** (pad 2) |
| nichrome drive output | **absent** — pads 4/5/6 unused, no output net exists |
| gate drive from MCU | **absent** — no drive net exists |
| hardware arming gate | **absent** — no net |
| cut-sense feedback | **present** (pad 3, `/CUT_SENSE_Wn`) |

So the footprint carries power, ground and sense — **the sense half of the channel** — and nothing
that could actually fire a cutter. The part cannot be chosen because its pins have destinations
that do not exist.

This matches ADR-051's own status note (line 202): *"No cut/release hardware exists anywhere in
`tracker/` — no MOSFET, nichrome, actuator or cut-down part. The cut channel is a paper design."*
The paper design reached the schematic as a footprint and three nets, not as a circuit.

## Consequence for the flight

The four wing cuts **cannot be commanded** by this board as designed. That is a functional gap on a
safety-critical path, not a procurement gap. It is also, by itself, the reason the assembly BOM
cannot be completed: `U_CUT1..4` and `U_HUB_CVT` are `TODO(unverified)` because there was never a
circuit to specify.

## What I did NOT do

I did not design the cut channel. It is a latched, irreversible, energy-budgeted firing circuit on
a flight vehicle: the ADR leaves the trigger mode (ground-commanded vs automatic) **explicitly
undecided** (§2.5 item 7), the 2–5 J energy band is marked `TODO(unverified)`, and the failure
modes include firing a channel twice and cutting the vehicle's own power. AGENTS.md does not give
me authority to make that call, and a plausible-looking guessed circuit would be worse than none.

## What is worth doing next, in order

1. **Decide bare board vs assembled.** If bare board, none of this blocks the order and the
   remaining question is only the 5 REAL opens. This is the decision that unblocks shipping today.
2. **If assembled: the cut channel needs a design pass** — part, drive net, arming gate, output
   net, and the trigger-mode decision — before any BOM line for `U_CUT1..4` can be real.
3. `U_HUB_CVT` is a smaller, separate design: one switching converter with its inductor and
   feedback network.

## Reproduce

    /usr/bin/python3 -B docs/analysis/cut_channel_pins.py
