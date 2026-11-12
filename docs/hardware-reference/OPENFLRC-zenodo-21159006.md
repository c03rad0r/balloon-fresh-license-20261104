# OpenFLRC v1.0 (Zenodo 21159006) — what it is, whether to fork it, and what we can use

**Assessment date 2026-11-08.** External dataset, CC BY 4.0.

| | |
|---|---|
| Title | *OpenFLRC v1.0: Open-source SX1280 2.4 GHz FLRC Transceiver hardware design files, validation datasets, and benchmarks* |
| DOI | **10.5281/zenodo.21159006** |
| URL | https://zenodo.org/records/21159006 |
| Published | 2026-07-03 |
| Type | Dataset |
| **Licence** | **CC BY 4.0** — usable and modifiable commercially, **attribution required** |
| Authors | Arenas Mamani, Franco Alessandro; carlos choquepuma, kent jojan; apaza rodriguez, karla erika; Hilario Tacuri, Alexander Beremiz |
| Contents | 267 files, 4.94 GB: EasyEDA schematic + 2-layer PCB, gerbers, PlatformIO firmware, NanoVNA/TinySA measurements, 4 videos |

## Verdict in one line

**Useful, and worth reading — but do not fork it as a board.** Its value to us is the
**firmware library, an independent throughput ceiling that corroborates ours, and a pin-level
cross-check**, not the PCB. Our
board is a 4-layer hub; theirs is a 2-layer single-radio node with an ESP32-S3 devkit footprint. And
its headline claim does not survive its own data (below).

## What it actually is

A point-to-point 2.4 GHz link built from:

```
YD-ESP32-S3 devkit  +  E28-2G4M27SX module (SX1280)  +  NeoPixel
```

Only **10 library parts** in the schematic — a devkit, an E28 module, two 7343 tantalums, 0603
passives, and a header. It is a **devkit carrier**, not a flight board. The E28 module carries its own
PA (`+15 dBm` per the header comment) and its own RF network, which is exactly why the RF problem is
solved by construction.

## The finding that matters: their headline number is self-contradicting

The library defaults to `OPENFLRC_DEFAULT_BITRATE 1300` kbps "raw air rate (1.3 Mbps)". Their
`measurements/phase1_dynamic_load/FLRC_2.4GHz/sx1280_throughput_data_v6.csv` is 2900 rows, one payload
size (117 B), 29 interval settings, 100 packets each. Computed from the raw data:

```
interval (us)   air kbps   DELIVERED kbps
       10000        93.6              94.6
        1000       936.0             884.3
         800      1170.0             885.6
         600      1560.0             886.1
         400      2340.0             886.1
         200      4680.0             886.1
         100      9360.0             885.6
```

**Throughput saturates at ~886 kbps and does not move again** — it is flat from 1 ms down to 100 µs
while the commanded air rate goes to 9.4 Mbps. The link delivers **68 % of the 1.3 Mbps air rate** and
**~9 % of a 9.4 Mbps commanded rate**.

Packet delivery ratio is **100 % in all 29 configurations** at RSSI ≈ −21 dBm. So this is not loss —
it is a **per-packet processing ceiling**, the sender cannot feed packets faster than ~886 kbps worth.

### Why that is directly relevant to us

Our project already measured the same shape of limit from the other direction:

- `docs/rp2040/rp2040-wiring-guide.md`: the LR2021 air rate is **2600 kbps**, ESP32-C3 RX pipeline caps
  at **~838.8 kbps** — "CPU/RTOS overhead per packet".
- `docs/rp2040/mcu-assessment-rp2040-vs-esp32.md`: RP2040 at **69 % of PHY max**.

**Their independent 886 kbps on an ESP32-S3 sits within 6 % of our 838.8 kbps on an ESP32-C3**, on
different silicon, different radio (SX1280 vs LR2021), and different firmware. Two independent
measurements agreeing that a single-core ESP32 tops out around 840–890 kbps regardless of air rate is
much stronger evidence than either alone.

**Conclusion for us, unchanged but now better supported:** the bottleneck is the MCU's per-packet
pipeline, not the radio, and **no air-rate increase buys throughput**. That is exactly why ADR-026's
dual-MCU (RP2040 owns the radio SPI) is the right call, and why chasing 2600 kbps on ESP32 alone is
not.

## Should we fork it?

**No — not the repository.** Reasons, in order:

1. **Wrong board class.** 2-layer devkit carrier vs our 4-layer hub with four wings, two inner planes,
   an F33 site, and 49 footprints. Nothing of its layout transfers.
2. **EasyEDA, not KiCad.** `Schematic.json` / `Layout.json` are EasyEDA Standard format. Importing to
   KiCad 9 is lossy and the value is in the schematic topology, which we already have.
3. **We already made its one good architectural decision.** See the next section.
4. **Its claim is weaker than ours.** Forking a design whose published throughput we cannot reproduce
   at its stated rate would import a problem, not solve one.

**What to take instead** (all CC BY 4.0, attribute in the file header):

- **`OpenFLRC.cpp` / `OpenFLRC.h`** — a working RadioLib `SX1280` subclass with DMA/burst SPI:
  `rawWriteBuffer`, `rawSetTx`, `rawSetRx`, `rawClearIrqStatus`, `rawReadBuffer`, `rawGetRSSI`,
  `rawSetAutoFS`. This is real, compilable prior art for the *fast path* our own RX work needs.
- **A pin-level cross-check of our SX1280 module wiring** (next section) — cheap to apply, and it
  agrees with us.
- **The measurement CSVs** as an external comparison point for our own throughput work.
- **Their SWR/insertion-loss Touchstone files** if we ever need a conducted-loss reference.

## What is directly usable on our board today

Our `U_LORA1280` is a **G-NiceRF LoRa1280** (per ADR-139), not the E28-2G4M27SX OpenFLRC uses. The
net names on our board still read `/E28_*` because the *net* names were inherited from the E28
footprint's naming, not because the part is an E28. Correcting that distinction matters: the two
modules share the SX1280 die and the same 16-pad footprint style, but they are different products
with different RF chains.

**Verified against the footprint, not the net names** — `tracker/hardware/footprints/lora1280/LoRa1280.kicad_mod`
carries pin functions, and they match NiceRF's published table for the LoRa1280 exactly:

```
1 DIO2  2 DIO3  3 VCC  4 GND  5 MISO  6 MOSI  7 SCK  8 NSS
9 ANT   10/11/12 GND  13 NRESET  14 GND  15 BUSY  16 DIO1
```

OpenFLRC's signal pinout is therefore a usable cross-check:

| OpenFLRC pin | their ESP32-S3 GPIO | our net | match |
|---|---|---|---|
| SCK | 18 | `/SPI1_SCK` | ✓ |
| MISO | 17 | `/SPI1_MISO` | ✓ |
| MOSI | 16 | `/SPI1_MOSI` | ✓ |
| NSS | 15 | `/E28_CS_N` | ✓ |
| RESET | 8 | `/E28_RESET_N` | ✓ |
| BUSY | 7 | `/E28_BUSY` | ✓ |
| DIO1 | 9 | `/E28_DIO1` | ✓ |
| DIO2 / DIO3 | — | `/E28_DIO2`, `/E28_DIO3` | we wire more than they do |

**Every signal they use, we already carry** — and we route DIO2/DIO3 which they leave unused. Their
pinout confirms our module wiring is the conventional one. That is a useful independent check, not a
change.

**One thing they have that we deliberately do not.** OpenFLRC drives `RX_EN` (LNA) and `TX_EN` (PA)
as separate GPIOs because the E28-2G4M27SX carries a 27 dBm PA + LNA. Our LoRa1280 has **no PA at
all** — ADR-139 accepted this on 2026-10-26 for three measured reasons:

```
                        E28-2G4M27SX (27 dBm PA+LNA)   LoRa1280 (12.5 dBm, no PA)
lawful ceiling (DE)     10 dBm EIRP -> PA throttled     10 dBm EIRP -> ~at the ceiling
ranging                 NO                              YES
TX current              580 mA peak                     26-30 mA
enables                 TX_EN + RX_EN -> 2 GPIOs         none
```

So **the absent TX_EN/RX_EN is a design decision, not a gap.** Adding them would mean paying for a PA
that German regulation caps at 10 mW EIRP, a 580 mA burst on a solar harvester, and the loss of the
ranging feature. **The paper produces no actionable change here** — it produces an independent
illustration of the option we rejected.

Related, and worth noting since pad 9 is the only unconnected pin on `U_LORA1280`: **pad 9 is `ANT`**
and it carries no net. The other two modules (`U3`, `U_C`) each leave four pads unconnected, one of
which is also `ANT`. That is consistent across all three and is a *design* question (how these
radios get an antenna — U.FL pigtail vs module antenna), not a fault. It is outside this paper's
scope and I have not changed anything.

## The "don't do what we did" lesson

`docs/fab/SX1280-MODULE-DECISION.md` records that our earlier bare-SX1280 QFN layout was **"FATAL as
laid out — not a tuning problem"**: the vendor reference network was placed *by value* but scattered
across **≈220 mm of 2.4 GHz track**, with a 52 pF-series shunt 52 mm from the RF pin. OpenFLRC's answer
to the same problem is the same one we arrived at independently — **use the module, let it carry its
own RF network**.

That is an independent confirmation of a decision we already took (bare `U4` is now absent from the
board; `U_LORA1280` replaced it). It is worth citing when anyone asks why there is no discrete RF
matching on this board.

## Attribution, if code is reused

CC BY 4.0 requires attribution. Any copied code must carry:

```
/* SX1280 DMA/fast-path routines derived from OpenFLRC v1.0
 * (Arenas Mamani et al., 2026), DOI 10.5281/zenodo.21159006, CC BY 4.0.
 * Modified for <our use>. */
```

A `NOTICE` or `THIRD-PARTY-LICENCES.md` entry is also worth adding if this is ever merged.
