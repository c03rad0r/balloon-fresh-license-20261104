# v10 partial-assembly plan — what JLCPCB places, what you hand-solder

> **SUPERSEDED IN PART (2026-11-08).** The population decision below is still correct and was applied
> to the board as DNP attributes — see `docs/fab/ASSEMBLY-PARTIAL.md` and
> `docs/fab/BOM-ORDER-READY.md`. Three things in THIS document were wrong and are corrected there:
>
> 1. **`U_LORA1280` "needs LCSC"** — it is a NiceRF LoRa1280 castellated module, not an LCSC part.
>    It is hand-fit, and no LCSC number exists to find. Same for `U3`/`U_C`.
> 2. **`C10` "needs LCSC"** — `C10` and `C4` are both 10 µF 0402 (measured on the board), so the
>    existing `C15525` covers both. No separate number is needed.
> 3. **`U7` LCSC `C5142805` is CORRECT** — it is TPS7A0233**DBVR**. `C2887324` is the
>    TPS7A0233**PDBVR** active-discharge variant and is a different part. Verified on LCSC.
>
> Also: Group E lists `J_HUB_PV` and `J_PROG` as "never placed", but both are ordinary 2.54 mm pin
> headers that JLC does place — `C492404` (1x5) and `C492405` (1x6), both verified in stock. All 14
> JLC lines now carry a sourced LCSC number.
>
> The DNP reasoning (barometer, supercaps, F33) and Groups B/C/D are unchanged and still stand.

**2026-11-08, board `latest.kicad_pcb` (`322ade1e`), 49 footprints, 11 REAL opens.**

Derived from the v9 locked split (`b8e1b7d6` — *"order BOMs for confirmed split — 10 boards,
no barometer, single PCBA variant"*) and `docs/fab/RECOMMENDATIONS-ON-OPEN-DECISIONS.md`
(D3/D4/D6), re-mapped onto the v10 board. **This is a plan, not an order.** Nothing here has
been sent to JLCPCB.

## The principle behind the split

Three rules, all from measured v9 reasoning, applied in order:

1. **DNP anything whose value is low and whose failure mode is worse.** The barometer: cabin
   pressurisation makes its reading nearly useless, and a failed part on the I2C bus takes the
   whole hub down. Kept as pads, not fitted.
2. **DNP anything that is a charged thermal/handling hazard and untested.** The supercaps:
   the risk register is *written assuming they are not fitted*, and cold-start behaviour
   (E-CS1…6) is planned, not measured.
3. **Place everything else at JLCPCB — including the expensive RF parts — because hand-soldering
   a QFN or a castellated module is where a build goes wrong.** Hand-solder only what is
   physically easy and where a variant is wanted (GPS on 4 units).

## Group A — JLCPCB places these (single PCBA variant)

Standard SMD, all with LCSC numbers from the v9 order BOM where the part carried over.

| ref | value | footprint | LCSC |
|---|---|---|---|
| C4 | 10 µF | 0402 | C15525 |
| C_BULK | 100 µF | 1206 | C15008 |
| C_HF | 100 nF | 0402 | C1525 |
| C_MON | 10 nF | 0402 | C15195 |
| D1 | BAT54W | SOD-123 | C699107 |
| D_BP1…4, D_HUB1…2 | SS24 | SMA | C50645 |
| R_BAL1, R_BAL2 | 10 k | 0402 | C25744 |
| R_DIV1, R_DIV2 | 1 M | 0402 | C26083 |
| R_F1 | 100 R | 0402 | C25076 |
| R_MON1, R_MON2 | 4.7 M | 0402 | C11906 |
| U1 | ESP32-S3-WROOM-1U-N8R8 | module | C2980300 |
| U7 | TPS7A0233DBVR | SOT-23-5 | C5142805 |
| ANT1…4 | U.FL | Molex MCRF | C434808 |
| U_LORA1280 | LoRa1280 | castellated | *(needs LCSC)* |
| C10 | — | 0402 | *(needs LCSC)* |
| C_CAP1, C_CAP2 | supercap 3.3 F | CP_Radial D10 | **DNP — see Group C** |

## Group B — DNP at JLCPCB, you hand-solder

| ref | value | footprint | LCSC | qty |
|---|---|---|---|---|
| **U5** | MAX-M10S-00B (GPS) | ublox_MAX | **C4153167** | 4 units only |

**Why hand-solder:** GPS is wanted on 4 of the units, not all of them. Placing it at the fab
would force every board to carry a ~$54 part that 6 of them don't need. The pads stay, so any
unit can be upgraded later without a respin.

**Note:** C4153167 is the number recorded in the v9 GPS add-on BOM
(`hub_v9_bom_flight_gps_addon.csv`, `Qty_for_hand_solder = 4`). **Verify it before buying** —
the v9 notes flag several LCSC numbers as `(check)`.

## Group C — DNP, deliberately not fitted

| ref | value | reason |
|---|---|---|
| **U6** | MS5611 barometer | Cabin-pressurised flight makes the reading low-value; a failed I2C part is a whole-hub failure. `DNP` in the v9 locked split. |
| **C_CAP1, C_CAP2** | 3.3 F supercap | Charged thermal/handling hazard; cold-start behaviour **untested** (E-CS1…6 planned). The risk register is written assuming DNP. |
| **U2** | LoRa2021F33_2G4 (2 W) | +33 dBm is **not licence-free legal in Germany** (10 mW ERP, Vfg. 91/2025). Site kept for optionality. |

**Why keep the pads:** DNP costs nothing and preserves a later build without a respin. This is
the same reasoning accepted for the F33 site.

## Group D — no part chosen yet (blocks the order)

| ref | footprint | status |
|---|---|---|
| **U_CUT1…4** | SOT-23-6 | `part TODO(unverified)` — the four pyro cut drivers |
| **U_HUB_CVT** | VQFN-16 3x3 P0.5 | `part TODO(unverified)` — PV input converter |

**These cannot be ordered, and no BOM tooling fixes that.** A device has to be chosen first.
If they are left as DNP sites, the board can still be assembled — but the cut channel then does
nothing, which is the whole function of `U_CUT*`.

## Group E — mechanical, never placed

H1–H4 mounting holes, HW1–HW4 wing tabs, J_W1…J_W4, J_PROG, J_VCC, J_HUB_PV. Connectors are
hand-soldered or are board features, not PCBA parts.

## What is still blocked before an assembly order

1. **Five undecided parts** (Group D). Not a tooling problem — a design decision.
2. **No LCSC column in the exported BOM.** The v9 pipeline (`build_jlc_bom.py` reading
   `jlc-pcba-work/*.csv`) does not exist for v10 and the script is hardcoded to v9 paths.
3. **Eight references export with `?`** (`C_BULK?`, `U_C?`, `J_PROG?`, …) because the board has
   **no schematic links** (49 of 49 footprints have an empty path). Project-wide convention, not
   damage from this campaign.

**Bare board is unaffected by all three.** Gerbers and drill are complete and verified
(196/196 holes, all stock sizes).

## Reproduce

```
python3 docs/analysis/bulk-route-20261107/list_parts.py docs/analysis/bulk-route-20261107/latest.kicad_pcb
git show b8e1b7d6:docs/fab/hub-v9/hub_v9_bom_order_platform.csv
```
