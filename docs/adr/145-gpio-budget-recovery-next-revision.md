# ADR-145 — GPIO budget recovery: three pin-saving measures, deferred to the next board revision

**Status:** ACCEPTED (roadmap) — not implemented on v10
**Date:** 2026-11-09
**Supersedes nothing.** Constrains the next revision's pin plan (ADR-108 successor).
**Owner of the next action:** the v11 pin-plan revision.

---

## 1. Context — why the budget is spent

`U1` is an ESP32-S3-WROOM-1U-**N8R8**. Measured on the board of record (`latest.kicad_pcb`,
`b90bf629`): **34 of its 41 signal pads carry a net.** There is no free GPIO of any consequence.

Measured per-device control cost on the shared `SPI1` bus (`SCK`/`MOSI`/`MISO` reach all four
devices — the bus is *not* the scarce resource):

| device | control lines | nets |
|---|---|---|
| `U_LORA1280` | 6 | `CS_N`, `RESET_N`, `BUSY`, `DIO1`, `DIO2`, `DIO3` |
| `U3` (LoRa2021) | 4 | `CS_N`, `RESET_N`, `BUSY`, `IRQ` |
| `U2` (F33 PA) | 4 | `CS_N`, `RESET_N`, `BUSY`, `IRQ` |
| `U_C` (LoRa2021 #2) | 4 | `CS_N`, `RESET_N`, `BUSY`, `IRQ` — **all four single-pad, no MCU end** |

`U_C` therefore cannot be commanded on v10. Free `U1` pads are 15, 16, 26, 28, 29, 30, 35; of
these **16 and 26 are input-only** and **28/29/30 are GPIO35–37, consumed by octal PSRAM** on this
N8R8 module. Usable: **15 (IO3) and 35 (IO42) — two pins for four signals.**

## 2. Decision

**Three measures are adopted for the NEXT revision. None is applied to v10.**

`U_C` ships **DNP** on the current order. `U3` is a complete, fitted, routed LoRa2021 on the same
bus and provides the radio function; `U_C` would have provided redundancy only.

### M1 — Share `RESET_N` and `BUSY` across all SPIRIT/LR-class radios

`RESET_N` and `BUSY` are not address-critical: all radios may be reset together, and `BUSY` may be
polled one device at a time via its own `CS_N`. Only `CS_N` (and `IRQ`, where used) must be
per-device.

* Saves **2 GPIOs per additional radio.**
* Cost: a shared reset means a bus-wide reset event; firmware must re-initialise every radio after
  it. Acceptable — the alternative is no second radio at all.
* Risk: a shorted `BUSY` line takes down polling for every radio on it. Mitigate with a series
  resistor per device (0402, 100 Ω) so one fault cannot hold the shared line.

### M2 — Put chip-selects on a 3-to-8 decoder

A **74HC138** converts **3 GPIOs into 8 active-low chip-selects**. Verified LCSC parts:

| LCSC | MPN | package | note |
|---|---|---|---|
| `C52145496` | CJ74HC138AEN | SOP-16 | 3/8 decoder, **$0.162 @ qty 5**, in stock |
| `C22439339` | HANSCHIP 74HC138DRG | SOP-16 | 3/8 decoder, alternative |

* Saves `N_devices − 3` GPIOs for `N_devices > 3`; with 4–6 devices that is **1–3 pins**.
* Cost: one SOP-16, one 100 nF decoupling cap, and the 3 select lines must be routed.
* **The decoder does NOT relieve the escape problem.** `U_C`'s control pads sit on the module
  edge with the same 1.50 mm-pad-on-1.27 mm-pitch geometry that sealed `/EN` (ADR-140 context,
  `FINDING-en-unroutable-flash-blocked.md`). Placement must give the decoder a clear escape lane
  *before* the module is placed, not after.

### M3 — I2C GPIO expander for non-critical, slow signals

**MCP23017** (`C506653`, MCP23017-E/SS, SSOP-28, 16-bit I²C expander, 8 devices per bus) or the SPI
variant **MCP23S17**.

* **16 I/O for 2 pins** (the existing `/I2C_SCL` and `/I2C_SDA`, which already reach `U6.7`/`U6.8`
  and are routed — 26 and 16 tracks).
* 100 kHz–1.7 MHz I²C; **not** suitable for anything timing-critical (no interrupt-to-GPIO latency
  guarantee, and a 1.7 MHz bus still costs ~microseconds per register access).
* Appropriate for: cut-channel arming/enable lines, sensor power gating, LED/status, jumper
  readback, supercap balance enables.
* **Not appropriate for:** radio `IRQ` (latency), SPI `CS` (throughput-critical per transaction),
  or anything sampled in a tight loop.

## 3. Where these should actually be spent on the respin

`M1`–`M3` free pins, and the highest-value use of freed pins is **not** the spare radio. It is the
**cut channel**, which is currently four unwired `U_CUT1..4` footprints with no cut-drive,
nichrome-output, arming or gate-drive net. ADR-051 §2.6 already records that four dedicated
`sense` GPIOs are impossible, so a mux/ladder is the only remaining shape there.

Recommended allocation for v11, in priority order:

1. **Cut channel** — 4 channel enables + 1 shared sense (M3 expander is a natural fit for the
   enables; the sense needs the mux/ladder of ADR-051).
2. **`/EN` and `/IO0` fan-out out of the module shadow** — so the programming header reaches the
   straps without bodge wires. This is a *layout* fix, not a pin-count fix, and it is mandatory for
   a production board.
3. **`EN` reset RC** — 10 kΩ + 1 µF per Espressif ESP32-S3-WROOM-1/1U datasheet v1.8 §9. Named by
   ADR-108 R1, **absent from the v10 netlist and the v10 board.**
4. **`U_C` control lines** — only after 1–3, and only if the escape geometry is solved.

## 4. Alternatives rejected

* **Sacrifice an existing function to give `U_C` four pins on v10.** Rejected: every used pin is a
  radio control line, a supercap sense, or a strap. Nothing is spare; taking one breaks something
  that works.
* **MCP23S17 (SPI expander) instead of MCP23017 (I2C).** Rejected for this design: it consumes a
  `CS` line, which is the scarce resource, and the I²C bus already exists with a routed device on
  it.
* **Resistor-ladder single-pin chip-select.** Rejected: `N_devices` selects need log₂(N) pins, so
  for 4 devices it saves **zero** pins versus individual `CS_N` — only one pin versus four. It also
  makes every `CS` transition a DAC settling problem.
* **Doing any of this on v10.** Rejected: it is a layout change requiring placement, fan-out and
  re-route on a board whose pin budget is already spent, and `U_C` provides redundancy, not
  capability.

## 5. What would change this answer

* If a v11 placement gives `U_C` (or its replacement) a clear escape lane to the board interior,
  M2 becomes cheap and worth doing.
* If the cut channel is dropped from the product, the freed priority-1 budget makes M1+M2
  sufficient for radios alone.
* If firmware cannot tolerate a bus-wide reset, M1 is rejected and `RESET_N` stays per-device,
  costing 1 more pin per radio.

---

## Reproduce

```
# per-device control cost and free pads
/usr/bin/python3 - <<'PY'
import re
from collections import defaultdict
src=open('docs/analysis/bulk-route-20261107/latest.kicad_pcb',errors='replace').read()
pads=defaultdict(list)
for b in re.split(r'\n\t\(footprint ', src)[1:]:
    r=re.search(r'\(fp_text reference "([^"]+)"',b)
    r=r.group(1) if r else '?'
    for pm in re.finditer(r'\(pad "([^"]*)"(.*?)\n\t\t\)', b, re.S):
        nm=re.search(r'\(net \d+ "([^"]*)"\)', pm.group(2))
        if nm: pads[nm.group(1)].append(f"{r}.{pm.group(1)}")
free=[p.GetNumber() for fp in __import__('pcbnew').LoadBoard('docs/analysis/bulk-route-20261107/latest.kicad_pcb').GetFootprints()
      if fp.GetReference()=='U1' for p in fp.Pads() if not p.GetNetname() and p.GetNumber()]
print('free U1 pads:', free)
PY
```
