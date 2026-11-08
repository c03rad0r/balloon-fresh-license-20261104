# Cut channel — part research (NO PART CHOSEN, NO DECISIONS TAKEN)

Scope: groundwork only. Two things are *not* done here and deliberately so — the part is not
chosen, and the trigger mode is not chosen. ADR-051 §2.5 item 7 leaves trigger mode
(ground-commanded vs automatic) explicitly open, and that decision changes the circuit.

## The electrical requirement, derived

From `docs/analysis/wing-jettison.md` and ADR-051 §2.5, at VSCAP (5.4 V):

```
wire            nichrome NiCr 80/20, 0.127 mm (36 AWG), 2.17 Ω
current         2.49 A           I = 5.4 / 2.17
power           13.4 W           P = V^2 / R
on-time         193 ms           t = 2.59 J / 13.4 W
energy          2.59 J per cut
```

At the 3.3 V logic floor it needs 1.52 A / 516 ms — **2.5× longer**, and 193 ms is already the
ADR-050 §3.10 limit (≤3.33 J = ≤10 % of usable bank). So the channel must fire from VSCAP, not from
logic: this is why ADR-051 specifies VSCAP.

## What the footprint can physically accept

SOT-23-6, 6 pads. Current board assignment:

```
pad 1  /VSCAP          power — matches ADR-051 (works with converter dead)
pad 2  GND             return
pad 3  /CUT_SENSE_Wn   wire continuity / fired feedback
pad 4  (no net)
pad 5  (no net)
pad 6  (no net)
```

**The three free pins are exactly the number needed** for a latched channel, if the device is a
*dual* MOSFET:

```
FET A   the cut drive    source->GND, drain->nichrome return, gate<-CUT_DRV_Wn
FET B   the series gate  in series with FET A, gate<-CUT_ARM_Wn   (the ADR-051 "hardware series
                         gate that requires an explicit arming sequence")
```

That means the **three nets that do not exist are the three the circuit needs**:

```
NIC_W1        nichrome return, wire -> FET A drain
CUT_DRV_W1    gate drive from MCU
CUT_ARM_W1    arming gate from MCU
```

This is consistent with the pin count and is the reason a dual SOT-23-6 is the natural fit rather
than a single 3-pin MOSFET in a 6-pin land.

## Candidate parts that fit the package (research, not a recommendation)

All are **dual N-channel, logic-level, SOT-23-6**, sorted by nothing in particular — these are for
evaluation against the 2.49 A / 13.4 W requirement:

| Part | Vds | Id | Rds(on) | Notes |
|---|---|---|---|---|
| **FDC6561AN** (onsemi) | 30 V | 2.5 A | 95 mΩ @10 V, 145 mΩ @4.5 V | PowerTrench dual; the same vendor family as the IRLML2502 ADR-051 names. Gate threshold 0.4–1.5 V, so 3.3 V logic drives it fully |
| **PJM6800DNSG** | 30 V | 5.8 A | 21 mΩ @10 V, 23 mΩ @4.5 V | much lower Rds(on), more headroom |
| **PJM6804DNSG** | 30 V | 5 A | 24 mΩ @10 V, 30 mΩ @4.5 V | similar |
| **PJM8205DNSG** | 20 V | 6 A | 21 mΩ @10 V, 28 mΩ @4.5 V | 20 V Vds — check against the 9.58 V cold Voc string, see below |

### The one electrical trap worth flagging now

`PJM8205` class parts are **20 V Vds**. `docs/adr/051` line 512 notes the wing string's cold Voc is
**≈9.58 V at −60 °C**, and that is the string the cut is *in*. 20 V leaves ~2× margin; 30 V leaves
~3×. Not a blocker either way, but it is the parameter that decides between the cheap and the safe
option, and it should be a deliberate choice, not an accident of availability.

### Thermal check that must be done before choosing

At 2.49 A through 145 mΩ (FDC6561AN at 4.5 V drive):
```
conduction loss   I^2 R = 2.49^2 x 0.145 = 0.90 W
duration          193 ms
energy            ~0.17 J dissipated in the package, once per cut
```
0.17 J in a SOT-23-6 in 193 ms is a transient — the package's 700–960 mW steady rating is not the
right limit for a single 193 ms pulse, but **the pulse rating must be checked from the datasheet's
SOA curve**, not assumed. This is the one calculation I have not done and would do before any part
is committed.

## What still has to be decided before a circuit can exist

1. **Trigger mode** — ground-commanded vs automatic (ADR-051 §2.5 item 7). Changes whether there is
   an uplink-gated input, a timer, or both. **Operator decision.**
2. **Is the arming gate one FET or a separate latch IC?** A dual MOSFET gives a series gate, but the
   "persistent fired flag" in ADR-051 is firmware (NVS) plus this gate; a hardware latch (e.g. a
   small DFF or a fuse) would be a different topology and a different package.
3. **Does CUT_SENSE share the wire node or measure separately?** ADR-051 says cut-sense feedback
   exists; the board routes `/CUT_SENSE_Wn` to pad 3, so the topology is fixed there already —
   worth confirming it measures the wire rather than the FET drain.
4. **Energy budget** — the 2–5 J band is `TODO(unverified)` in ADR-051. 2.59 J is a calculation on
   unverified thermophysical constants. A wrong wire length or gauge changes both the current and
   the on-time.

## What I did not do

- **Did not choose a part.** Four candidates are listed; the SOA pulse calculation and the 20 V vs
  30 V Vds question are unresolved.
- **Did not draw a circuit.** Two of the four inputs above are operator decisions and one
  (`CUT_SENSE` topology) needs confirmation against the schematic intent.
- **Did not touch the board.** `U_CUT1..4` remain as they are: power, ground and sense wired, drive
  and output absent.

## Next step that needs no decision

The SOA pulse calculation for each candidate, and a check of whether the 9.58 V cold-Voc figure
appears on the node the FET actually switches. Both are measurement, not design.
