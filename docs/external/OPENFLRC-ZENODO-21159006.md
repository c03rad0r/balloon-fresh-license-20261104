# External reference — OpenFLRC v1.0 (Zenodo, CC-BY-4.0)

**Added 2026-11-08.** Operator supplied the record and asked: *"how can we fork this? Is any of
it useful to us in our flight board?"*

| | |
|---|---|
| **Record** | https://zenodo.org/records/21159006 |
| **DOI** | `10.5281/zenodo.21159006` |
| **Title** | OpenFLRC v1.0: Open-source SX1280 2.4 GHz FLRC Transceiver hardware design files, validation datasets, and benchmarks |
| **Creators** | Franco Alessandro Arenas Mamani; Kent Jojan Carlos Choquepuma; Karla Erika Apaza Rodriguez; Alexander Beremiz Hilario Tacuri (Universidad Nacional de San Agustín de Arequipa) |
| **Published** | 2026-07-03, v1 |
| **Licence** | **CC-BY-4.0** |
| **Code** | https://github.com/FrancoArenasM/OpenFLRC_Library (related identifier) |
| **Package** | `OpenFLRC_v1.0_Hardware_and_Data.zip`, 4.9 GB |

## What is in it

- `design_files/` — **EasyEDA** schematics, **2-layer** PCB layout, Gerbers
- `firmware/` — PlatformIO C++ projects for throughput benchmarks, conducted attenuation
  sweeps, and spectral tests
- `measurements/` — NanoVNA S-parameters, insertion-loss calibrations, TinySA spectrum
  measurements, raw CSV outputs
- `videos/` — recorded throughput console, attenuation setups, spectrum validation

Target: an **ESP32-S3 + SX1280** FLRC node for remote scientific telemetry.

**The architecture match is exact, not approximate.** Verified against the board file: our host
is `U1` ESP32-S3-WROOM-1U, our 2.4 GHz radio is `U_LORA1280` (NiceRF SX1280 module), and both
sides run **FLRC** in 2.4 GHz. Same MCU, same transceiver silicon, same mode. That is why their
numbers are directly comparable to ours rather than merely suggestive — and also why their
*hardware* is still not portable: we are KiCad 4-layer with castellation wings, they are EasyEDA
2-layer.

## Is it useful to us — measured against our own tree

| OpenFLRC | ours | verdict |
|---|---|---|
| SX1280 in **FLRC** mode | `firmware/esp32-c3-flrc`, `firmware/rp2040-flrc-max` | **same silicon, same mode** — directly comparable |
| **ESP32-S3** host | U1 is **ESP32-S3-WROOM-1U** | **the exact MCU**, not merely the family |
| 2.4 GHz | `LoRa1280` (NiceRF module) + `LoRa2021_Castellated` | same band |
| Throughput benchmarks | `tools/flrc_512b_throughput_audit.py`, `sweep-config-flrc.json`, `data/walk-tests/` | **we have our own — compare, don't adopt** |
| NanoVNA S-params, attenuation sweeps | no equivalent recorded for our 2.4 GHz path | **the genuinely new material** |
| EasyEDA, 2-layer | KiCad, **4-layer** | **not portable** |

### Useful — the measurement datasets

Their **insertion-loss calibrations and attenuation sweeps** are the part we do not have. Our
throughput numbers exist (`data/walk-tests/walk_throughput_lora_vs_flrc.png`,
`tools/flrc_512b_throughput_audit.py`) but a measured **conducted** path-loss reference is what
lets a throughput figure be attributed to the radio rather than to the RF plumbing. That is
worth comparing against.

### Found by MEASURING their data, not reading their abstract

The package's own `measurements/phase1_dynamic_load/FLRC_2.4GHz/sx1280_throughput_data_v6.csv`
(2900 rows, 117 B payload, 29 interval settings, 100 packets each) was extracted and evaluated
directly. Their library header advertises `OPENFLRC_DEFAULT_BITRATE 1300` kbps "raw air rate".
What the data shows:

```
interval (us)   commanded air kbps   DELIVERED kbps
       10000                  93.6             94.6
        1000                 936.0            884.3
         800                1170.0            885.6
         600                1560.0            886.1
         200                4680.0            886.1
         100                9360.0            885.6
```

**Delivered throughput saturates at ~886 kbps and is flat from 1 ms to 100 µs**, while the
commanded air rate climbs to 9.4 Mbps. PDR is **100 % in all 29 configurations** at RSSI ≈ −21 dBm.

So this is not loss — it is a **per-packet processing ceiling**: the host cannot feed the radio
faster than ~886 kbps worth of packets.

**Why that is the most useful thing in the package for us:** our own tree already recorded an
ESP32-C3 LR2021 RX ceiling of **~838.8 kbps** (`docs/rp2040/rp2040-wiring-guide.md`) and RP2040 at
**69 % of PHY max** (`docs/rp2040/mcu-assessment-rp2040-vs-esp32.md`). Their independent 886 kbps on
**ESP32-S3**, on a **different radio** (SX1280 vs LR2021) and **different firmware**, lands within
**6 % of our 838.8 kbps**.

Two independent measurements, different silicon and different radios, agreeing that a single-core
ESP32 tops out around 840–890 kbps *regardless of air rate*, is much stronger evidence than either
alone. It is direct support for ADR-026's dual-MCU split (RP2040 owns the radio SPI) and for the
claim that **raising the air rate buys no throughput**.

### Useful — the firmware as a cross-check

Their PlatformIO bench projects are an independent implementation of the same
SX1280-FLRC configuration on the same MCU family. If our `sweep-config-flrc.json` settings and
theirs disagree on a bitrate/packet-parameter combination, that disagreement is a finding.

### NOT useful — the hardware design

**EasyEDA, 2-layer.** Our hub is KiCad, **4-layer**, with castellation wing sockets, ADR-142
cavity rules and a DRC regime that has been through this campaign. Their layout cannot be
imported and would be a regression if it could.

## How to fork it — the practical answer

**Licence: CC-BY-4.0. Forking and commercial use are permitted. The only obligation is
attribution.** No share-alike, no non-commercial clause.

Attribution must credit: Arenas Mamani, Carlos Choquepuma, Apaza Rodriguez, Hilario Tacuri —
*"OpenFLRC v1.0", DOI 10.5281/zenodo.21159006, CC-BY-4.0.*

**What "fork" means here, per artefact:**

1. **The measurement data** — copy in with a `PROVENANCE` line naming the DOI and licence. This
   is the low-risk, high-value use.
2. **The firmware** — fork the GitHub repo, keep the licence and attribution in the fork, and
   treat it as a **reference implementation**, not as a base to build on. Our drivers are
   already further along for our hardware.
3. **The hardware** — **do not fork.** Different EDA tool, different layer count, different
   mechanical interface. Taking it would mean abandoning KiCad and the whole ADR/DCR regime.

**Practically:** a 4.9 GB zip is not something to clone into this repo. If we adopt anything,
fetch the specific `measurements/` files and record the DOI beside them.

### Also useful — a pin-level cross-check of our SX1280 module

Their `OpenFLRC.h` pin map and our `tracker/hardware/footprints/lora1280/LoRa1280.kicad_mod`
pin functions were compared signal by signal:

| OpenFLRC | GPIO | our net | match |
|---|---|---|---|
| SCK | 18 | `/SPI1_SCK` | ✓ |
| MISO | 17 | `/SPI1_MISO` | ✓ |
| MOSI | 16 | `/SPI1_MOSI` | ✓ |
| NSS | 15 | `/E28_CS_N` | ✓ |
| RESET | 8 | `/E28_RESET_N` | ✓ |
| BUSY | 7 | `/E28_BUSY` | ✓ |
| DIO1 | 9 | `/E28_DIO1` | ✓ |
| DIO2 / DIO3 | — | `/E28_DIO2`, `/E28_DIO3` | we wire more than they do |

Note our net names say `E28_*` but the part is a **G-NiceRF LoRa1280** (ADR-139); the net names
were inherited from the E28 footprint. The two modules share the SX1280 die and a 16-pad footprint
but are different products.

**They drive `TX_EN`/`RX_EN` on two GPIOs; we have neither — deliberately.** Their module is an
E28-2G4M27SX with a 27 dBm PA+LNA. ADR-139 chose our no-PA LoRa1280 precisely to avoid that:
German regulation caps 2.4 GHz at **10 mW EIRP**, so the PA cannot be lawfully used, and it costs
580 mA peak on a solar harvester plus the ranging feature. **The paper produces no change here** —
only an independent illustration of the option we rejected.

## What I did NOT do

- Did **not** download the 4.9 GB package. Nine specific members were extracted by HTTP range
  request (see Reproduce) — the README, schematic, layout, the SX1280 library sources, two
  benchmark `main.cpp` files, and one throughput CSV. Total ~90 KB fetched.
- Did **not** fork the GitHub repo.
- Did **not** copy any data or code into the tree — this document is the reference, not the
  artefact.

## Companion document

`docs/hardware-reference/OPENFLRC-zenodo-21159006.md` carries the longer board-level analysis
(what the package is built from, why the PCB does not transfer, and the RF-layout lesson). This
document is the authoritative citation and the measurement finding; read them together.

**What would change the assessment:** if their attenuation data disproves one of our
`data/walk-tests/` throughput figures, that becomes a first-class finding rather than a
citation.

## Reproduce

```
curl -s https://zenodo.org/api/records/21159006 | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['metadata']['license'], d['doi'])"
grep -rl "flrc" firmware/ tools/ configs/ data/ | head
```

**Extracting individual members without downloading 4.9 GB** — the archive is ZIP64, so the
central directory offset is in the ZIP64 EOCD record, reached via the locator that precedes the
normal EOCD. Two range requests give the file list; each member then costs one 30-byte local-header
fetch plus its compressed bytes:

```
# list every member (267 entries) from the tail of the archive
python3 docs/analysis/zenodo_extract.py --list
# extract the members used above
python3 docs/analysis/zenodo_extract.py --get README.md     'firmware\libraries\OpenFLRC_Library\src\OpenFLRC.cpp'     'measurements\phase1_dynamic_load\FLRC_2.4GHz\sx1280_throughput_data_v6.csv'
```
