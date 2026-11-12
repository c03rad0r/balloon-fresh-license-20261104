# Frozen-rule clearance work — 2026-11-03

**Result: 81 frozen-rule violations → 22, all warnings. Zero errors. Unconnected 86 → 80.**

## The finding that changed everything

Every DRC number earlier in this effort — the "40 violations / 86 unconnected" baseline — was
measured against the project's **global** rules (via 0.50, drill 0.20), **not** the frozen JLCPCB S1
rules (`jlcpcb-s1-frozen.kicad_dru`: via **0.60**, drill **0.30**). Nothing loaded the frozen DRU
because no same-stem `.kicad_dru` existed next to the board.

Loading it tells a different story:

| rules loaded | violations |
|---|---|
| global (no DRU) | 40 — incl. 16 `copper_edge_clearance` |
| **frozen S1 DRU** | **81** — 16 `copper_edge_clearance` **vanish**, 35 `via_diameter` + 22 `drill_out_of_range` appear |

The 16 edge violations were an artefact of the wrong rule set. The pad-scoped edge exemption in the
frozen DRU is doing its job; there was never a copper-to-edge defect. The real blocker was that
**41 of 41 vias were below spec** — invisible until the right rules were loaded.

## Sequence

1. `upsize_vias.py` — every via to ≥ 0.30 mm drill / ≥ 0.60 mm pad, refill, DRC.
   81 → 13 violations. 35 `via_diameter` and 22 `drill_out_of_range` both reach **zero**.
   Cost: 4 `clearance` at exactly 0.150 mm vs the 0.200 mm rule — the 0.05 mm of extra radius.
   Unconnected 82 → 80.
2. `nudge_vias.py` — move only the vias that are actually tight, dragging connected track ends.
   3 vias moved (0.08, 0.36, 0.08 mm). 4 `clearance` → 0.
   **First version moved 7 vias for 4 violations** because it keyed on net name; two of those sat at
   1.55 mm and needed nothing. Fixed to skip anything already ≥ the rule.
3. `repair_scoped_thermal.py U_LORA1280.14 J_PROG.1` — 2 `starved_thermal` → 0, scoped to the two
   named pads rather than all 16.

## Final state

`FINAL.kicad_pcb` sha256 `8f5ede4eccd9e8cc1cabd6f0a28a356365d11681601ae60b346404b575b46449`
`FINAL.kicad_dru` sha256 `b8b321bb182b0f63515a80186e3f92127ac1dbe3aa4ddf9b797168a2af9b39a7`
Source board `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`

```
22 violations   (8 lib_footprint_issues, 11 lib_footprint_mismatch, 3 silk_over_copper — all warnings)
0 errors
80 unconnected
```

## What this is NOT

Not fab-approved, not frozen-rule-approved as a *build*, still not orderable. Remaining:

- **80 unconnected.** The dominant blocker now that vias and edges are clean.
- **19 library warnings** (`lib_footprint_issues` 8, `lib_footprint_mismatch` 11) — footprint-vs-library
  drift. Real for fabrication: the fab etches what the library says, not what the board caches.
- **3 `silk_over_copper`** — legibility, my earlier silk repair is on a different candidate and has
  not been folded into this one.
- **5 vias with a single track end and no zone** (`/GNSS_PPS` ×2, `/E28_RESET_N`, `/SPI1_SCK` ×2).
  Pre-existing, not introduced here, and DRC does not flag them — but a via fed by one track and
  landing in no plane is a candidate stub. Needs a net-by-net look before it is called harmless.
  Note `/E28_RESET_N` is a **legacy E28-era net name** on a board now carrying `U_LORA1280`.

## Reproduce

```
cd tracker/hardware && cp ../../reports/.../apply/solar-candidate.kicad_pcb /tmp/x.kicad_pcb
python3 docs/analysis/solar-8land-verify/upsize_vias.py /tmp/x.kicad_pcb /tmp/u.kicad_pcb \
    --dru tracker/hardware/jlcpcb-s1-frozen.kicad_dru
python3 docs/analysis/solar-8land-verify/nudge_vias.py /tmp/u.kicad_pcb /tmp/n.kicad_pcb \
    --dru tracker/hardware/jlcpcb-s1-frozen.kicad_dru
```
