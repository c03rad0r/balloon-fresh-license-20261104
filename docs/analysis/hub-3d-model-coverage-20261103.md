# 3D model coverage on the canonical hub board — measured, and what the merge does NOT fix

Board: `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`
SHA256 `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`
Tool: `scripts/3d_model_coverage_report.py` (retargeted from `hub_board_v9` to the
canonical board in this branch — it was grading the wrong artefact).

## Result

```
repo-local 0 / library 34 / none 15  of 49
```

**34 of 49 footprints resolve from the installed KiCad 3D package. 15 have no
model at all.** No repo-local VRML is in use.

## The 20 merged repo-local models are NOT wired to this board

PR #107's `tracker/hardware/footprints/3dmodels/*.wrl` (20 files) merged, but the
canonical board references only **two** `wrl` paths and both point at the KiCad
library, not the repo (`${KICAD8_3DMODEL_DIR}/RF_Module.3dshapes/NiceRF_LoRa2021.wrl`).
Every other reference is a `${KICAD9_3DMODEL_DIR}` `.step`.

Proof the render is unchanged: a fresh `kicad-cli pcb render` after the merge is
**238985 bytes — byte-identical** to the render taken before it.

`MODEL-INDEX.json` records the *original library paths* each repo VRML was meant to
replace ("A machine that HAS the KiCad 3D package can restore the library models").
That restoration has **not** been performed, and 9 of the 20 repo models are for
parts that already resolve from the library anyway.

## Why "library 34" is not "assembly verified"

Resolution is file existence plus path match. Three of the 15 gaps are genuine
library absences on this host, verified directly:

| reference | expected model | present? |
|---|---|---|
| `U1` | `RF_Module.3dshapes/ESP32-S3-WROOM-1U.step` | **NO** (only `-1`, `-2`, `-2U`) |
| `U5` | `RF_GPS.3dshapes/ublox_MAX.step` | **NO** (directory has no ublox part) |
| ANT/U.FL | `Connector_Coaxial.3dshapes/U.FL_Molex_MCRF_73412-0110_Vertical.step` | **NO** (only `U.FL_Hirose_U.FL-R-SMT-1_Vertical.step`) |

A resolved model also does not prove the *body* matches the real part — only that a
file of that name exists.

## Consequence for the visual review

Any 3D render of this board is an **incomplete assembly preview**. Bare footprints in
it must not be read as intentional DNP or as "unpopulated by design". Electrical and
mechanical review must not rest on a render.

## Not changed

No board file, no footprint, no model reference was edited in this branch. This
document records measurement only.
