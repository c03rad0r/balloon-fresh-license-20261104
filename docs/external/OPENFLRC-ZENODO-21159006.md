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

## Is it useful to us — measured against our own tree

| OpenFLRC | ours | verdict |
|---|---|---|
| SX1280 in **FLRC** mode | `firmware/esp32-c3-flrc`, `firmware/rp2040-flrc-max` | **same silicon, same mode** — directly comparable |
| **ESP32-S3** host | U1 is ESP32-S3-WROOM-1U | same MCU family |
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

## What I did NOT do

- Did **not** download the 4.9 GB package.
- Did **not** fork the GitHub repo.
- Did **not** copy any data in — this document is the reference, not the artefact.

**What would change the assessment:** if their attenuation data disproves one of our
`data/walk-tests/` throughput figures, that becomes a first-class finding rather than a
citation.

## Reproduce

```
curl -s https://zenodo.org/api/records/21159006 | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['metadata']['license'], d['doi'])"
grep -rl "flrc" firmware/ tools/ configs/ data/ | head
```
