# Five part candidates researched: one RESOLVED with a verified LCSC number

**2026-11-08, board `0602c7c8`.** Research only — except `U7`, which is now *identified*, not chosen:
the project's own ADR says what it is, and the footprint proves it.

## U7 — RESOLVED: TI TPS7A0233PDBVR, LCSC **C2887324**

This was recorded as "value is literally `U7`, no part identity". It is not undecided — the identity
was never read out of the ADR.

**ADR-047 §2.2** documents it in the power tree:

```
VSCAP (raw supercap node, post-BAT54, pre-LDO)
   ├── U7  TPS7A02 3.3 V LDO  →  +3V3  (the logic rail, and the bare LoRa2021's VCC)
   └── J_VCC pin-1 SELECTOR
```

**The footprint confirms it pin for pin** against the TI datasheet (DBV package, SOT-23-5):

| pad | datasheet | board net | verdict |
|---|---|---|---|
| 1 | IN | `/VSCAP` | ✓ input from the supercap rail |
| 2 | GND | `GND` | ✓ |
| 3 | EN | `/VSCAP` | ✓ tied to IN = always enabled, correct for a 25 nA Iq part |
| 4 | NC | *(no net)* | ✓ NC correctly unconnected |
| 5 | OUT | `+3V3` | ✓ the logic rail |

Five of five. This is not an inference from the net names — it is a match against the published
pinout.

**LCSC part number: `C2887324`**, MPN `TPS7A0233PDBVR`, SOT-23-5, 200 mA, 25 nA Iq, 3.3 V fixed,
−40…+125 °C, RoHS3. Verified on LCSC's product page, and the MPN is confirmed in TI's own
ordering table.

### One thing to note about it, not a blocker

`VSCAP` max is **5.4 V** (2 × 2.7 V supercaps in series). TPS7A02's absolute maximum input is
**6.0 V**, so the margin is 0.6 V = 11 %. That is fine for a regulated solar input but thin against a
transient. ADR-047 already records the separate trap (the F33's PA must never be fed through this
LDO), and decision D6 leaves the F33 off the board, so the trap is inert in this build.

Also note D4 leaves `C_CAP1`/`C_CAP2` unfitted, so `VSCAP` will not be a supercap rail in this
build at all — the LDO still works from the solar node, but the 5.4 V figure does not apply. Worth
re-checking this margin when the supercaps are eventually fitted.

## The other four — still open, and honestly so

### `U_CUT1..4` — cut drivers

Covered in `RESEARCH-cut-channel-parts.md`. Four dual-N-channel SOT-23-6 candidates
(FDC6561AN, PJM6800DNSG, PJM6804DNSG, PJM8205DNSG), none recommended. Two open engineering
questions remain and neither can be closed without the operator's trigger-mode decision:

- **Vds margin**: 20 V class parts sit against a 9.58 V cold Voc (2×), 30 V parts against 3×.
- **SOA pulse**: 0.90 W for 193 ms ≈ 0.17 J in a SOT-23-6. The 700–960 mW *steady* rating is the
  wrong limit; the datasheet SOA curve must be read.

These are moot for this build: D1 leaves all four unfitted, and the circuits are electrically
incomplete (3 of 6 pads wired).

### `U_HUB_CVT` — hub array converter, VQFN-16 3×3 P0.5

**3 of 18 pads connected** — `/HUB_PV_P`, `GND`, `/HUB_PV_N`. That is an input pair and a ground; no
switching node, no inductor, no feedback, no output. There is no converter to specify. This is a
*schematic* gap, not a part-selection task: ADR-051 requires an independent hub-array converter
input, and the schematic carries the pads but not the circuit.

Selecting a part without the topology would produce a part number for a circuit that does not exist.
Also D1 leaves it unfitted.

### `U5` — MAX-M10S GPS

**Not a research gap.** Decision D3 says DNP rows plus **4 loose units, hand-soldered**. There is a
part in `bom/BOM.md` (~15–20 EUR, DigiKey/Mouser, u-blox MAX-M10S, UART, ~0.6 g). The board position
stays empty by design.

### `U6` — MS5611 baro

**Also not a research gap, but for a different reason.** D3 leaves it DNP because cabin-pressurised
thermal cycling makes its value low. But decision **D5** in the same document says the NTC sense chain
is the flight's thermal instrument, and that risk acceptance is *void* if it is unpopulated. Those two
are consistent: the baro is out, the NTC chain is in. Worth stating because "DNP the sensor" and
"measure the cold" sound contradictory and are not.

## What this changes

| part | before | now |
|---|---|---|
| `U7` | "no part identity" | **TPS7A0233PDBVR / C2887324 — resolved** |
| `U_CUT1..4` | part TBD | 4 candidates, 2 open questions, awaiting trigger mode |
| `U_HUB_CVT` | part TBD | **no circuit to specify** — schematic gap |
| `U5` | part TBD | not a gap: DNP + 4 loose |
| `U6` | part TBD | not a gap: DNP by decision |

**One line of the assembly BOM is now fillable**: `U7` → `C2887324`. The other 12 JLC-placeable lines
still need numbers.
