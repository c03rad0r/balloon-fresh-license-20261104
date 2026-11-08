# BOM is now order-ready: 14/14 lines have a verified LCSC number

**2026-11-08, board `0602c7c8`.** Assembly order can be priced and built for the JLC-placeable
subset — with one caveat at the end that is mine to state plainly.

## Where the numbers came from

Not invented, and not all from one place:

| line | LCSC | source | verified |
|---|---|---|---|
| SS24 | C50645 | v9 order BOM | LCSC: mpn `SS24`, in stock |
| BAT54 | C699107 | v9 order BOM (BAT54W sub) | LCSC: mpn `BAT54W`, in stock |
| 10uF 0402 | C15525 | v9 order BOM | LCSC: `CL05A106MQ5NUNC`, in stock |
| 100uF 1206 | C15008 | v9 order BOM | LCSC: `CL31A107MQHNNNE`, in stock |
| 100nF 0402 | C1525 | v9 order BOM | LCSC: `CL05B104KO5NNNC`, in stock |
| 10nF 0402 | C15195 | v9 order BOM | LCSC: `CL05B103KB5NNNC`, in stock |
| 10k 0402 | C25744 | v9 order BOM | LCSC: `0402WGF1002TCE`, in stock |
| 1M 0402 | C26083 | v9 order BOM | LCSC: `0402WGF1004TCE`, in stock |
| 100R 0402 | C25076 | v9 order BOM | LCSC: `0402WGF1000TCE`, in stock |
| 4.7M 0402 | C11906 | v9 order BOM | LCSC: `RTT02475JTH`, in stock |
| U1 ESP32-S3-WROOM-1U | C2980300 | v9 order BOM | LCSC: `ESP32-S3-WROOM-1U-N8R8`, in stock |
| U7 | C5142805 | v9 order BOM | LCSC: `TPS7A0233DBVR`, in stock |
| J_HUB_PV 1x05 | C492404 | **LCSC search this task** | LCSC: `PZ254V-11-05P`, 1x5P 2.54 TH, in stock |
| J_PROG 1x06 | C492405 | **LCSC search this task** | LCSC: `PZ254V-11-06P`, 1x6P 2.54 TH, in stock |

Every number was checked by fetching the LCSC product page and reading the MPN, not just by
checking the page exists. The passive part numbers also decode to the right value
(`0402WGF1002TCE` = 10 kΩ, `1004` = 1 MΩ, `1000` = 100 Ω, `CL05B104` = 100 nF, `CL05B103` = 10 nF,
`CL31A107` = 100 µF), so a wrong-value substitution would have shown up.

## A near-miss worth recording: two LCSC numbers for one MPN family

I had proposed `C2887324` for `U7` from a web search, and the v9 BOM already carried `C5142805`.
Both pages report 3.3 V LDO parts, so either would have looked correct. They are **not** the same
part:

```
C5142805 = TPS7A0233DBVR      (no active discharge)
C2887324 = TPS7A0233PDBVR     (P variant = active output discharge)
```

The project's own number is **C5142805**, and it is the one now in the BOM. I nearly replaced a
correct number with a same-family variant on the strength of a search result — exactly the class of
error an unverified part number produces in a paid order. The "P" suffix is one character.

## The hand-fit list is now 4 lines

```
WING_SOCKET_4P   J_W1..J_W4     Wing_Tab_4P            custom edge connector
LoRa2021_Castellated  U3, U_C   LoRa2021_Castellated   NiceRF module
LoRa1280         U_LORA1280     LoRa1280               NiceRF module
```

None of these is an LCSC part, so no number is possible. They are hand-fit by nature, which is the
same treatment decision D3 already gives the GPS (4 loose units).

## ⚠ One caveat I am not going to bury

**These part numbers are verified as *catalogue entries*. They are not verified as *the right part
for this circuit*.** Specifically:

- **`U1` C2980300 is `ESP32-S3-WROOM-1U-N8R8`** — the v9 BOM's part. The board's footprint is
  `ESP32-S3-WROOM-1U`, and the *N8R8* suffix means 8 MB flash / 8 MB PSRAM. If firmware needs a
  different memory variant, this is the line where that shows up. It carried over from v9
  unchanged, so it is presumably right, but it was not re-decided for v10.
- **`R_MON1`/`R_MON2` at 4.7 MΩ, 5 % (C11906 `RTT02475JTH`)** sit in the `F33_VSENSE` divider. A
  5 % part in a sense divider is a 5 % measurement; ADR-044 does not state a tolerance requirement.
  Worth a deliberate look, not an assumption.
- **Ratings ARE now checked** — this caveat is partly superseded (2026-11-08). `audit_bom_specs.py`
  read every part's LCSC page back and checked voltage rating, dielectric and tolerance against the
  rail each part actually sits on. Full result and reasoning: **`docs/fab/CAP-VOLTAGE-AUDIT.md`**.
  Summary: **no rating failures.** `VSCAP` is **bounded at 5.4 V** by construction (2 × 2.7 V cells
  in series, `RESEARCH-five-parts.md:38`), so the 6.3 V passives sit at 86 % of rating — legal.
  `C_BULK` was changed anyway to `C312983` (100 µF **10 V** X5R 1206, same footprint) because an X5R
  at 86 % of rating loses 50–70 % of its capacitance to DC bias, and that part's job is charge
  storage behind a ~1100 mA PA burst. `C10,C4` stays at 6.3 V because **10 µF at ≥10 V does not
  exist in 0402** — the alternatives are 0603/0805, i.e. board changes (v11 item).
  Still true and still worth checking: JLC will substitute in-stock equivalents *only if*
  "parts substitution" is allowed on the order, which should be left **off** for a first article.

## Files

- `docs/analysis/bulk-route-20261107/assembly-partial/asm-bom-jlc.csv` — 14 lines, 23 placements,
  all 14 with a number and a `Source` column naming where each came from
- `asm-bom-jlc-handfit.csv` — 4 lines, 7 placements
- `asm-cpl-jlc.csv` — 30 rows, verified against `pcbnew` coordinates to <0.001 mm
