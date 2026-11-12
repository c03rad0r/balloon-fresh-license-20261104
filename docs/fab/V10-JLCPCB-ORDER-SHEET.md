# JLCPCB order sheet — balloon hub v10, bare board + partial assembly

**2026-11-08. Every value below is read from `latest.kicad_pcb` unless marked CHOICE.**
Reproduce with `python3 docs/analysis/bulk-route-20261107/order_params.py`.

Nothing here has been sent to JLCPCB. This is the copy-paste sheet.

---

## 1. Board

| field | value | source |
|---|---|---|
| Dimensions | **72.00 × 80.00 mm** | Edge.Cuts extent, `x 0.00..72.00  y 0.00..80.00` |
| Layers | **4** | F.Cu, In1.Cu, In2.Cu, B.Cu |
| Board thickness | **1.6 mm** | `(general (thickness 1.6))` |
| Outline | closed, single contour | gerbv render, independently produced |
| Quantity | **5** (first article) | CHOICE |

**Order 5, not 50.** Validate the four-layer stack, the 0.300 mm vias and the wing-socket
cavity edges on real boards before a larger run. That is ~$2 each at qty 5 versus a respin.

## 2. Stackup — NOT recorded on the board

The board file has **no `stackup` block**. KiCad falls back to its default for a 4-layer
board, and JLCPCB's default 4-layer stack is:

```
F.Cu      1 oz
Prepreg
In1.Cu    0.5 oz
Core
In2.Cu    0.5 oz
Prepreg
B.Cu      1 oz
```

**CHOICE — accept JLCPCB's default 4-layer stack.** Reasons:
- The board carries no impedance-controlled nets (no USB, no differential pairs, no RF
  transmission lines on the PCB — the radios are modules with U.FL connectors).
- Nothing in the design references a dielectric thickness or Dk.
- Choosing a custom stackup costs extra and buys nothing measurable here.

**If a controlled-impedance requirement appears later, this choice must be revisited** —
the default stack cannot be assumed to hit a target impedance.

## 3. Drill table — verified against the shipped file

`fab-11opens/board.drl`, 196 holes, **all four sizes are stock JLCPCB tools**:

| size | qty | function |
|---|---|---|
| 0.200 mm | 12 | PTH component |
| **0.300 mm** | **161** | **PTH via** |
| 1.000 mm | 15 | PTH component |
| 2.500 mm | 8 | NPTH mounting |

**No non-stock drill anywhere.** The 0.360 mm vias that FR3NETS added exist only on the
**rejected** `batches/FR3NETS/routed.kicad_pcb` and never reached the live board.

Annulus check, all PTH pads (27) and all vias (161): **minimum 0.150 mm**, which is exactly
JLCPCB's multilayer floor and **not above it**. Not a blocker, but it is the one number on
this board with zero headroom — do not specify a finish or copper weight that tightens it.

## 4. Copper / geometry minimums

| field | value | JLCPCB 4-layer ability |
|---|---|---|
| Min track width | **0.200 mm** | 0.09 mm → **2.2× margin** |
| Min clearance | **0.200 mm** | 0.09 mm → **2.2× margin** |
| Min via drill | 0.300 mm | 0.15 mm → 2× margin |
| Min via diameter | 0.600 mm | 0.25 mm |
| Min via annulus | 0.150 mm | 0.15 mm → **at floor** |
| Smallest SMD pad | 0.775 × 0.250 mm | 0.25 × 0.25 mm → ok |

Everything clears by a wide margin except the via annulus, which sits exactly on the floor.

## 5. Order-form fields — CHOICE, with the reason

| field | value | why |
|---|---|---|
| **Surface finish** | **ENIG** | The 0.150 mm via annulus is at the floor and the smallest pad is 0.25 mm on one axis. HASL's thicker, less uniform coating is the wrong choice on both. ENIG costs ~$8 more at qty 5. |
| **Solder mask** | Green (default) | No optical requirement; green is cheapest and has the best resolution. |
| **Silkscreen** | White (default) | Designators are 0.80 mm tall / 0.15 mm line — the JLCPCB minimum, already enforced by `check_silk.py`. |
| **Copper weight** | **1 oz outer** (default) | 2 oz would shrink the minimum trace/space to 0.16 mm and **forfeit the 2.2× margin** for no benefit at these currents. |
| **Inner copper** | 0.5 oz (default) | Matches the assumed stackup. |
| **Edge plating** | **No** | The wing sockets are castellations *into* the edge, not plated edge rails. Plated edges would need a separate process and alter the cavity geometry. |
| **Castellated / plated half-holes** | **YES — this is the one to flag** | `J_W1…J_W4` are edge-launched with pads sitting on `Edge.Cuts` by design (ADR-046/048, ADR-142). JLCPCB charges extra for castellated edges and **requires ≥10 × 10 mm** — 72×80 clears that. |
| **Gold fingers** | No | — |
| **Impedance control** | No | Nothing to control (see §2). |
| **Test coupon** | No | First article, not production. |
| **Panelisation** | Let JLCPCB decide | 5 units of 72×80 is above their panel threshold; their tooling will panel it. |

## 6. Assembly — partial, per `V10-PARTIAL-ASSEMBLY-PLAN.md`

**JLCPCB places (single PCBA variant):** all 0402/1206 passives, D1, D_BP1–4, D_HUB1–2,
U1 (ESP32-S3), U7 (LDO), ANT1–4 (U.FL), U_LORA1280, D_SOD-123.

**DNP — pads present, not fitted:**
- `U5` MAX-M10S (GPS) — you hand-solder on **4 of the units** (LCSC C4153167, verify first)
- `U6` MS5611 (barometer) — cabin pressurisation makes it low-value; dead I2C part kills the hub
- `C_CAP1/2` 3.3 F supercaps — charged handling hazard, cold-start untested
- `U2` LoRa2021F33 — +33 dBm is not licence-free legal in Germany

**Not orderable yet:** `U_CUT1–4` (SOT-23-6) and `U_HUB_CVT` (VQFN-16) are both literally
`part TODO(unverified)`. No device chosen.

**If you order assembly anyway:** leave those five as DNP. The board builds and flies; the
pyro cut channel simply does nothing, which is its entire function — so this is only
acceptable as a bench/hand-solder-later arrangement.

## 7. What blocks an assembly order today

1. **Five devices unchosen** (`U_CUT1–4`, `U_HUB_CVT`). A design decision, not tooling.
2. **No LCSC column in the v10 BOM export.** The v9 pipeline (`build_jlc_bom.py` reading
   `jlc-pcba-work/*.csv`) does not exist for v10 and is hardcoded to v9 paths.
3. **Eight refs export with `?`** — the board has no schematic links at all (49/49 empty
   path). Project-wide convention; not damage from this campaign.

**None of the three affects a bare-board order.**

## 8. First-article checklist on arrival

- [ ] Board thickness measures 1.6 mm ±10 %
- [ ] 4 copper layers visible on the edge cross-section
- [ ] Wing-socket cavities present on `J_W1…J_W4`, 6.0 × 0.5 mm
- [ ] Via drill 0.300 mm — check one under magnification, annulus must not be broken
- [ ] Outline 72.00 × 80.00 mm, closed, no nick at the castellations
- [ ] Designators legible at 0.80 mm

**Reproduce every number above:**
```
python3 docs/analysis/bulk-route-20261107/order_params.py
python3 docs/analysis/bulk-route-20261107/drill_audit.py
```
