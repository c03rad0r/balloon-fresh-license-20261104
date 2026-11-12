# ADR-148 — One ADS1115 resolves `OPEN-25` and the `/SCAP_ADC` orphan, with zero new MCU pins

**Status:** ACCEPTED · 2026-11-10 · closes `OPEN-25` (cut-sense pin) and the `/SCAP_ADC` dead end

## Context

Two separate problems, both stuck for the same underlying reason.

**`OPEN-25` — the cut-sense pin.** Open since ADR-068. Four cut channels each need a current/continuity
sense input. ADR-108's F33 pin plan consumed the GPIO budget and records that four dedicated GPIOs are
no longer available.

**`/SCAP_ADC` — the storage rail cannot be read.** Measured on v10: the net contains exactly two pads,
`R_DIV1.2` and `R_DIV2.1`. A 2:1 divider from `/VSCAP` to GND whose midpoint goes **nowhere**. Firmware
cannot read the rail. And there is **no divider at all** on the solar inputs — `/W1_SOLAR_P` touches
only `D1`, `D_BP1` and `J_W1`.

## The measured constraint that makes this hard

Free and *usable* pads on `U1` (ESP32-S3-WROOM-1U), measured:

| pad | GPIO | capability |
|---|---|---|
| 15 | GPIO3 | **ADC1_CH2** — the only ADC-capable free pin |
| 16 | GPIO46 | input only, **no ADC** |
| 26 | GPIO45 | strapping, **no ADC** |
| 28/29/30 | GPIO35/36/37 | **dead** — N8R8 octal PSRAM occupies GPIO33–37 |
| 35 | GPIO42 | **no ADC** |

So the total analog budget is **one channel**. The cut sense wants four, `/SCAP_ADC` wants one, and
three solar dividers would want three more: **eight analog inputs and one pin.**

Any solution that consumes that pin on one function makes every other function impossible, and any
solution using GPIO3 must accept that it is a **strapping pin** (JTAG source select) that must be at the
right level at boot.

## Decision

**Fit two `ADS1115IDGSR` (`C37593`, VSSOP-10, 16-bit, 4-channel, I²C, $1.4015) on the existing
`/I2C_SCL` / `/I2C_SDA` bus.**

| device | address | channels |
|---|---|---|
| `U_ADC1` | `0x48` (ADDR→GND) | `AIN0..AIN3` = cut current, wings 1–4 |
| `U_ADC2` | `0x49` (ADDR→VDD) | `AIN0` = `VSCAP`, `AIN1..3` = W1/W2/W3 solar |

**New MCU pins required: zero.** `/I2C_SCL` (16 tracks) and `/I2C_SDA` (26 tracks) are already routed.
This is the same leverage ADR-145 identified for the MCP23017 — an I²C expander costs no new pin
because the bus exists.

**GPIO3 (pad 15) is freed.** It does not need to be the ADC. Whether to use it for anything is a separate
question, and the strapping-pin risk is avoided entirely.

## Why the cut sense is a SHUNT, not a divider

My earlier note proposed a 100k/100k voltage divider on the sense pin. **That was wrong**, and the
measurement is what shows it.

A divider measures the **voltage at the wing pad**, which during a fire is essentially the rail (~5.4 V)
regardless of whether the wire is intact. It cannot distinguish:

- wire intact → 2.49 A flowing, pad pulled *down* by the wire's own drop
- wire severed → no current, pad sits at the full rail

The signal that carries the information is **current**, so the sense element must be a **series shunt**.

**`R_SENSE = 10 mΩ`, in series with the nichrome, on the low side.**

Measured consequences:

| quantity | value |
|---|---|
| voltage across shunt at cut | **24.9 mV** |
| shunt dissipation during the 193 ms pulse | **0.062 W** |
| current through the wire, with the shunt added | **2.477 A** (was 2.49 A) |
| pulse energy impact | **0.19 %** — pulse time 194 ms vs 193 ms |

**The shunt does not disturb the cut.** 10 mΩ against 2.17 Ω of wire is 0.46 %.

## Why it can actually detect the cut — the published Ct table, not a guessed tempco

My first pass used a linear 150 ppm/K tempco. **That was wrong**, and the real datasheet is more
interesting. Nichrome 80's published *temperature factor of resistivity*, `Ct`
(niwire.com Nichrome 80 datasheet), is a table, not a coefficient:

| T (°C) | 20 | 100 | 200 | 300 | 400 | 500 | 600 | 700 |
|---|---|---|---|---|---|---|---|---|
| **Ct** | 1.000 | 1.006 | 1.012 | 1.018 | 1.025 | 1.026 | 1.018 | 1.010 |

Recomputed with `R_wire = 2.17 × Ct` and the 10 mΩ shunt in series:

| T (°C) | R wire | I | V_shunt | ΔI from cold |
|---|---|---|---|---|
| 20 | 2.170 Ω | **2.48 A** | **24.77 mV** | — |
| 400 | 2.224 Ω | 2.42 A | 24.17 mV | 60 mA |
| 500 | 2.226 Ω | 2.41 A | 24.15 mV | 62 mA |
| 700 | 2.192 Ω | 2.45 A | 24.53 mV | 24 mA |

**Nichrome's Ct peaks near 500 °C and then goes *negative*.** Above 500 °C the resistance starts
falling again. That inversion is the reason the detector must **not** look for a specific ΔI: a wire at
600 °C and a wire at 300 °C produce nearly the same current.

**Correct detector logic: watch for the current to COLLAPSE.**

- wire intact → ~2.4–2.5 A through the shunt, whatever its temperature
- wire severed → current falls to the leakage of the open circuit, effectively **0**

At PGA 16 the LSB is **7.81 µV = 0.78 mA** through 10 mΩ, so going from **2.48 A to under 10 mA spans
~248 LSB**. This is not a marginal measurement. It is unambiguous, and it is immune to the Ct inversion
precisely because it does not rely on how much the current moved.

**The temperature curve is still useful for one thing:** it bounds how much the current *can* change
without a cut (~62 mA, i.e. 25 % of the 248-LSB span), so a threshold anywhere between "clearly
flowing" and "clearly not" is easy to place.

## Address collisions — checked, not assumed

| device | address | source |
|---|---|---|
| `U_ADC1` | `0x48` | ADDR→GND |
| `U_ADC2` | `0x49` | ADDR→VDD |
| MS5611 (rig) | `0x76`/`0x77` | CSB pin |
| MCP23017 (ADR-145) | `0x20`–`0x27` | A0–A2 |

No collision. ADS1115 supports four addresses (`0x48`–`0x4B`) via ADDR→GND/VDD/SDA/SCL, so there is
headroom for two more if a later revision needs them.

## Costs and consequences

| item | delta |
|---|---|
| parts | **+2** × `C37593` @ $1.4015 = **$2.80/board** |
| MCU pins | **0** |
| `OPEN-25` | **closed** |
| `/SCAP_ADC` orphan | **closed** |
| solar dividers | **now possible** (3 channels, AIN1–3 of `U_ADC2`) |
| GPIO3 (pad 15) | **freed** — strapping-pin risk avoided |
| firmware | new ADS1115 driver; the S3's ADC is no longer used for any of this |

**$2.80 is the entire cost of unblocking four analog problems and freeing a strapping pin.** At 10
boards that is $28, against a respin.

## Dividers for `U_ADC2` — sized to the ADS1115, not to the S3 ADC

Because the ADS1115 takes ±4.096 V at PGA 1, the dividers are freer than they would be on the S3's
0–3.3 V ADC:

| channel | source | divider | at max |
|---|---|---|---|
| AIN0 | `/VSCAP` (5.4 V max) | 1:1 (10 kΩ / 10 kΩ) | 2.70 V — PGA 1 |
| AIN1–3 | W1/W2/W3 solar | 1:1 (10 kΩ / 10 kΩ) | ≤ 2.7 V |

**Use 10 kΩ, not 100 kΩ**, for these: the ADS1115's input is high-impedance but 10 kΩ keeps the source
impedance well inside its specification and makes the 100 nF filter corner a sensible ~1.6 kHz.

The `VSCAP` divider now exists for the first time — `R_DIV1`/`R_DIV2` on v10 were a dead end and stay as
they are unless v11 re-uses those designators.

## What this does NOT solve

**`/F33_VSENSE`** remains a 43.7 mm missing trunk (`U1.21` isolated from a complete 51-item divider
chain). Its load is the DNP F33 PA so it reads zero harmlessly, but wiring it is a routing job, not an
ADC job. `U_ADC2` has one spare channel if a later revision wants to move it off the MCU.

**The shunt is in the cut path itself.** If a shunt ever fails open, the cut fails. Use a **1206**
(not 0402) 10 mΩ part, and consider that a cut channel that cannot fire is worse than one that fires
and is not sensed. The 0.062 W dissipation is trivial; the mechanical robustness of the part is the
reason to size it up.

## Alternatives rejected

| option | why rejected |
|---|---|
| GPIO3 (pad 15) for `/SCAP_ADC` only | uses the sole analog pin on one of eight needs; strapping-pin risk for no gain |
| 4:1 analog mux + GPIO3 | needs **two** GPIOs (mux select + ADC) and there is one; also loses simultaneous sensing |
| MCP23017 (ADR-145) for the sense inputs | digital-only — it cannot measure a 25 mV shunt |
| 100k/100k voltage divider on each sense pin | **measured wrong**: cannot distinguish intact from severed wire |
| Shared sense node with wing selection | would need a mux per channel anyway; loses the ability to sense two wings at once |
| Do nothing; accept no cut telemetry | a cut is irreversible and unobservable. You would not know whether a wing was gone. |
