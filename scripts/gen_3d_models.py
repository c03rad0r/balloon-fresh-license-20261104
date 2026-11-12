#!/usr/bin/env python3
"""Generate the v9 hub board's 3D models PARAMETRICALLY, as VRML (.wrl) text.

WHY THIS FILE EXISTS (2026-10-08)
---------------------------------
A render of `hub_board_v9.kicad_pcb` was produced and it was MISLEADING: every one
of the 32 model references resolved to `${KICAD9_3DMODEL_DIR}/...`, the KiCad 3D
package (`kicad-packages3d`, 4.77 GB) is NOT installed on this host and
`KICAD9_3DMODEL_DIR` is unset, so **0 of 32 referenced models resolved**.  A vision
model then "saw" components that were only silkscreen text.  Installing the 4.77 GB
library is NOT the fix: the disk has ~3.8 GB free, and NO library contains this
project's custom parts (the F33 module, the castellated LoRa2021, the SX1280 land,
the wing socket, the bare solar cells).

The fix is to GENERATE the models from the dimensions the repo actually knows and
COMMIT them, so a render resolves on any machine and every future worker inherits
them.  WRL is chosen over STEP because it is plain text and needs no CAD kernel.

HONESTY RULES THIS FILE ENFORCES
--------------------------------
1. NO DIMENSION IS INVENTED.  Every model carries a provenance header: the
   dimension and the record / footprint drawing / library name it came from.
   Where a dimension is NOT sourced it is written `TODO(unverified)` IN THE MODEL
   ITSELF, visibly, so a render can never be mistaken for a verified shape.
2. A clean box with the RIGHT dimensions is honest and useful; a guessed detailed
   shape is not (it looks verified).  Bodies are therefore prisms of the cited
   footprint body outline.  Only the two features the records actually fix are
   modelled as anything more: the F33 castellations (0.80 mm hole, 3.9289 mm
   pitch, 9 per 39 mm edge) and the solar cells' distinct dark face.
3. Determinism: no timestamps, no randomness, fixed iteration order.  Re-running
   this file reproduces byte-identical output (verified by `--check`).

USAGE
-----
  python3 scripts/gen_3d_models.py            # write every model + the index
  python3 scripts/gen_3d_models.py --check    # exit 1 if any committed model drifts

Output: `tracker/hardware/footprints/3dmodels/` (committed) plus
`tracker/hardware/footprints/3dmodels/MODEL-INDEX.json`, which maps each
repo-local model back to the `${KICAD*_3DMODEL_DIR}` path it replaced, so a
machine that DOES have the KiCad 3D package can restore the library model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_DIR = os.path.join(REPO, "tracker", "hardware", "footprints", "3dmodels")

# VRML authoring convention used here (KiCad 3D space):
#   model X  = footprint +X          model Y = footprint +Y          model Z = UP (mm)
# Z-up is KiCad's own convention for .wrl models; the bodies below are nearly
# symmetric about Y, so a mirrored-Y interpretation is visually identical.
Y_SIGN = 1.0

COL_BODY = (0.10, 0.11, 0.12)      # dark plastic / module body
COL_METAL = (0.62, 0.64, 0.68)     # shielded can / castellation plating
COL_CAN = (0.72, 0.74, 0.77)       # metal shield lid
COL_CELL = (0.05, 0.08, 0.34)      # solar cell face - DARK BLUE, deliberately
COL_CELL_EDGE = (0.42, 0.46, 0.52)  # cell bus / frame - light, reads as a cell
COL_CU = (0.78, 0.55, 0.25)        # exposed copper land

# ---------------------------------------------------------------------------
# THE MODEL TABLE
#
# Every entry:  name -> (solids-builder, provenance lines, source-kind)
# `src` strings are the authority for the dimensions; `todo` lists the
# dimensions that are NOT sourced in the repo and are therefore display
# defaults flagged `TODO(unverified)` in the emitted model.
#
# `body_src = "fab"`  -> X/Y are the footprint's own F.Fab body drawing extent as
#                        committed in this repo (reproducible: re-read the
#                        footprint and compare).
# `body_src = "doc"`  -> X/Y come from a named in-repo record.
# ---------------------------------------------------------------------------

MODELS = {}


def model(name, x, y, h, src, todo=(), colour=COL_BODY, extra=None, kind="box"):
    MODELS[name] = dict(x=x, y=y, h=h, src=src, todo=list(todo), colour=colour,
                        extra=extra or {}, kind=kind)


# --- passives: X/Y from the footprint's F.Fab body drawing (in-repo) ---------
#     the F.Fab rects live in the committed footprint; the 1005/3216 metric names
#     in the library item name independently corroborate 1.0x0.5 / 3.2x1.6.
model("R_0402_1005Metric", 1.715, 0.640, 0.50,
      "X/Y: F.Fab body drawing of Resistor_SMD:R_0402_1005Metric as committed "
      "(F.Fab extent 1.715 x 0.640 mm; the library item name `1005Metric` is the "
      "IEC 0402 package, nominal 1.0 x 0.5 mm body)",
      todo=["Z 0.50 mm - chip thickness is not stated in any in-repo record"])
model("C_0402_1005Metric", 1.100, 0.600, 0.50,
      "X/Y: F.Fab body drawing of Capacitor_SMD:C_0402_1005Metric as committed "
      "(1.100 x 0.600 mm; library item name `1005Metric` = IEC 0402)",
      todo=["Z 0.50 mm - not stated in any in-repo record"])
model("C_1206_3216Metric", 4.695, 1.700, 0.80,
      "X/Y: F.Fab body drawing of Capacitor_SMD:C_1206_3216Metric as committed "
      "(4.695 x 1.700 mm; library item name `3216Metric` = IEC 1206, nominal "
      "3.2 x 1.6 mm body)",
      todo=["Z 0.80 mm - not stated in any in-repo record"])

# --- diodes ------------------------------------------------------------------
model("D_SMA", 4.964, 4.898, 2.30,
      "X/Y: F.Fab body drawing of Diode_SMD:D_SMA as committed (4.964 x 4.898 mm "
      "extent; package code SMA = JEDEC DO-214AC)",
      todo=["Z 2.30 mm - SMA body height is not stated in any in-repo record"])
model("D_SOD-123", 2.900, 3.798, 1.35,
      "X/Y: F.Fab body drawing of Diode_SMD:D_SOD-123 as committed "
      "(2.900 x 3.798 mm; package code SOD-123)",
      todo=["Z 1.35 mm - SOD-123 body height is not stated in any in-repo record"])
model("D_SOD-323", 1.700, 3.448, 1.10,
      "X/Y: F.Fab body drawing of Diode_SMD:D_SOD-323 as committed; the drawn "
      "extent (6.821 mm) includes a fab annotation, so the X used is the "
      "SOD-323 nominal body width 1.700 mm",
      todo=["X used as the nominal SOD-323 width rather than the raw F.Fab extent",
            "Z 1.10 mm - SOD-323 body height is not stated in any in-repo record"])

# --- actives / modules -------------------------------------------------------
model("LGA-8_3x5mm_P1.25mm", 3.100, 5.100, 1.00,
      "X/Y: F.Fab body drawing of Package_LGA:LGA-8_3x5mm_P1.25mm as committed "
      "(3.100 x 5.100 mm); the library item name states 3x5mm; "
      "docs/PAYLOAD-WEIGHT-ESTIMATES.md line 70 gives the MS5611 baro as 5.0 x 3.0 mm",
      todo=["Z 1.00 mm - MS5611 body height is not stated in any in-repo record"])
model("SOT-23-5", 1.700, 3.000, 1.10,
      "X/Y: F.Fab body drawing of Package_TO_SOT_SMD:SOT-23-5 as committed "
      "(1.700 x 3.000 mm) - the TPS7A02 (U7) land",
      todo=["Z 1.10 mm - SOT-23-5 body height is not stated in any in-repo record"])
model("U.FL_Molex_MCRF_73412-0110_Vertical", 3.869, 5.698, 1.20,
      "X/Y: F.Fab drawing of Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical "
      "as committed (3.869 x 5.698 mm, includes the drawn feed spur)",
      todo=["Z 1.20 mm - U.FL mated height is not stated in any in-repo record"])
model("ublox_MAX", 9.800, 10.200, 2.50,
      "X/Y: F.Fab body drawing of RF_GPS:ublox_MAX as committed (9.800 x 10.200 mm) "
      "- the MAX-M10S (U5) land.  NOTE: docs/PAYLOAD-WEIGHT-ESTIMATES.md line 63 "
      "states 12.2 x 16 mm, which is a different (patch-antenna) figure; the "
      "footprint drawing is used and the disagreement is recorded, not hidden.",
      todo=["the 12.2 x 16 mm figure in docs/PAYLOAD-WEIGHT-ESTIMATES.md vs the "
            "9.800 x 10.200 mm footprint drawing - unreconciled",
            "Z 2.50 mm - not stated in any in-repo record"],
      colour=COL_CAN)
model("ESP32-S3-WROOM-1U", 18.100, 19.300, 3.10,
      "X/Y: F.Fab body drawing of RF_Module:ESP32-S3-WROOM-1U as committed "
      "(18.100 x 19.300 mm).  The Espressif module is 18.0 x 25.5 mm, so the "
      "committed land is shallower than the real module - recorded, not hidden.",
      todo=["the 18.0 x 25.5 mm Espressif module outline vs the 18.100 x 19.300 mm "
            "committed footprint drawing - unreconciled",
            "Z 3.10 mm - ESP32-S3-WROOM-1U module height is not stated in any "
            "in-repo record"],
      colour=COL_CAN)

# --- the two custom castellated radios ---------------------------------------
#  LoRa2021 bare: X/Y/Z from the operator's JSON inventory of the module.
#  LoRa2021F33-2G4: 39 x 21 mm from the footprint descr + the brief; Z from the
#  brief (2.5 mm) - flagged, because no in-repo record states it.
model("NiceRF_LoRa2021", 19.81, 14.98, 2.32,
      "X/Y/Z: tracker/hardware/footprints/nicerf-lora2021.json "
      "`dimensions.width_mm/height_mm/thickness_mm` = 19.81 x 14.98 x 2.32 mm",
      colour=COL_METAL,
      extra=dict(castellation=dict(edge_len=19.81, pitch=1.29, count=9,
                                   hole_dia=None, proud=0.0)),
      kind="castellated")
model("LoRa2021F33-2G4", 39.00, 21.00, 2.50,
      "X/Y: 39.0 x 21.0 mm - the `descr` of balloon_flight_v9:LoRa2021F33_2G4 "
      "('39x21mm') and the land file LORA2021F33-2G4 footprint_pads.pcb; pad "
      "centres at 3.9289 mm pitch, 9 lands on each 39 mm edge (committed "
      "footprint).  Castellation hole diameter 0.80 +/- 0.1 mm read off the "
      "vendor drawing by the operator (2026-10-07), datasheet s9 p8.",
      todo=["Z 2.50 mm - module thickness is NOT stated in any in-repo record; "
            "it is the operator's figure from the brief only"],
      colour=COL_METAL,
      extra=dict(castellation=dict(edge_len=39.00, pitch=3.9289, count=9,
                                   hole_dia=0.80, proud=0.10)),
      kind="castellated")
model("SX1280_QFN24", 4.00, 4.00, 0.90,
      "X/Y: 4.0 x 4.0 mm - the `descr` of balloon_flight_v9:SX1280_QFN24 "
      "('QFN-24 4x4mm 0.5mm pitch'); the committed footprint's own courtyard is "
      "4.450 x 4.450 mm and its descr is explicitly '*** GEOMETRY NOT VERIFIED ***'",
      todo=["the whole SX1280 land pattern is an unverified placeholder - the "
            "Semtech datasheet was never retrieved on this host",
            "Z 0.90 mm - QFN-24 body height is not stated in any in-repo record"],
      colour=COL_BODY)

# --- the repo's own mechanical parts -----------------------------------------
model("Wing_Tab_4P", 4.00, 6.60, 0.60,
      "X/Y: the soldered land row of Tracker_Mechanical:Wing_Tab_4P as committed - "
      "lands span 1.0..5.0 mm inboard of the interface edge (4.0 mm) x four 1.2 mm "
      "lands on 1.8 mm pitch (6.6 mm).  PLAIN PADS, NO SLOT: the 0.9 mm routed "
      "slot is ADR-046 Option A and is BELOW JLCPCB's 1.0 mm minimum NPTH slot "
      "(docs/analysis/wing-fab-cost.md s2.3, build_hub_board_v9.py header); "
      "Option B (plain pads) is the adopted fallback, so no slot is modelled.",
      todo=["Z 0.60 mm - the wing tab thickness is the board thickness figure "
            "(ADR-055 D4 target 0.4 mm, and 0.6 mm inherited) - not settled",
            "NOTE: the committed footprint still DRAWS the 0.9 mm slot on "
            "Edge.Cuts; see docs/3d-model-coverage-hub.md"],
      colour=COL_CU)
model("SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm", 4.650, 2.550, 0.50,
      "X/Y: the F.CrtYd extent of Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm "
      "as committed (4.650 x 2.550 mm) - J_VCC carries NO F.Fab body drawing, so "
      "the courtyard is the only in-repo size",
      todo=["no F.Fab body drawing exists; the courtyard extent is used",
            "Z 0.50 mm - solder-jumper thickness is not stated in any in-repo record"],
      colour=COL_CU)

# --- THE SOLAR CELLS (the parts the operator most wants to see) --------------
model("SolarCell_LARGE_78.55x38.90", 78.55, 38.90, 0.21,
      "X/Y/Z: 78.55 x 38.90 x 0.21 mm - ADR-049 s'Measured inputs' (cited by "
      "ADR-051 s1.4): 'the LARGE cell as 78.55 x 38.90 x 0.21 mm, 30.6 cm2, "
      "~0.5 V, ~1.2 A'.  The face is drawn deliberately DARK BLUE so a cell can "
      "never be read as copper or silkscreen.",
      kind="cell", colour=COL_CELL)
model("SolarCell_SMALL_52.07x19.65", 52.07, 19.65, 0.21,
      "X/Y/Z: 52.07 x 19.65 x 0.20-0.21 mm - ADR-049 s'Measured inputs' outline "
      "row ('52.07 x 19.65 x 0.20-0.21 mm', 10.23 cm2).  0.21 mm (the upper end of "
      "the recorded range) is used.",
      todo=["the thickness is a RANGE (0.20-0.21 mm) in ADR-049; 0.21 is used"],
      kind="cell", colour=COL_CELL)


# --------------------------------------------------------------------------- emit
def _mat(rgb):
    return "material Material { diffuseColor %.3f %.3f %.3f }" % rgb


def _box(lines, size, tr, colour, rot=None):
    x, y, z = size
    tx, ty, tz = tr
    lines.append("Transform {")
    lines.append("  translation %.4f %.4f %.4f" % (tx, ty, tz))
    if rot:
        lines.append("  rotation %s" % rot)
    lines.append("  children [")
    lines.append("    Shape {")
    lines.append("      appearance Appearance { %s }" % _mat(colour))
    lines.append("      geometry Box { size %.4f %.4f %.4f }" % (x, y, z))
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")


def _cyl(lines, radius, height, tr, colour, rot="1 0 0 1.5707963"):
    tx, ty, tz = tr
    lines.append("Transform {")
    lines.append("  translation %.4f %.4f %.4f" % (tx, ty, tz))
    lines.append("  rotation %s" % rot)
    lines.append("  children [")
    lines.append("    Shape {")
    lines.append("      appearance Appearance { %s }" % _mat(colour))
    lines.append("      geometry Cylinder { radius %.4f height %.4f }" % (radius, height))
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")


def emit(name: str, spec: dict) -> str:
    x, y, h = spec["x"], spec["y"], spec["h"]
    kind = spec["kind"]
    colour = spec["colour"]
    todo = spec["todo"]
    L = []
    L.append("#VRML V2.0 utf8")
    L.append("# " + "-" * 74)
    L.append("# MODEL     : %s" % name)
    L.append("# GENERATED : scripts/gen_3d_models.py  (parametric, deterministic)")
    L.append("# SOURCE    : %s" % spec["src"])
    if spec.get("extra", {}).get("castellation"):
        c = spec["extra"]["castellation"]
        L.append("# CASTELLATION: %d half-cylinders per %.2f mm edge at %.4f mm pitch, "
                 "axis VERTICAL (through the module thickness), centred exactly ON the "
                 "module edge line (half inset, half proud)" % (c["count"], c["edge_len"], c["pitch"]))
        if c["hole_dia"] is None:
            L.append("# TODO(unverified): the castellation hole diameter for this module is "
                     "NOT sourced in the repo - no half-cylinder is drawn")
    if kind == "cell":
        L.append("# FACE      : dark blue / bus-bar frame - deliberate, so a cell never "
                 "reads as copper or silkscreen (the confabulation this file exists to stop)")
    if todo:
        L.append("# TODO(unverified):")
        for t in todo:
            L.append("#   - %s" % t)
    L.append("# " + "-" * 74)
    L.append("")

    # --- body prism
    _box(L, (x, y, h), (0.0, 0.0, h / 2.0), colour)

    if kind == "castellated":
        c = spec["extra"]["castellation"]
        if c["hole_dia"]:
            r = c["hole_dia"] / 2.0
            n = c["count"]
            pitch = c["pitch"]
            # pads are centred on the edge; the row of n lands is centred on the
            # module axis, so the first centre sits -(n-1)/2 * pitch from 0
            off0 = -(n - 1) / 2.0 * pitch
            for i in range(n):
                px = off0 + i * pitch
                for py in (y / 2.0, -y / 2.0):
                    _cyl(L, r, h, (px, py, h / 2.0), COL_METAL)
    elif kind == "cell":
        # a light bus-bar frame 0.6 mm wide just inside the cell edge, sitting
        # 0.02 mm proud of the dark face, so the dark face reads as a CELL and
        # never as a blank rectangle (or as copper).
        bw = 0.6
        fz = h + 0.01
        _box(L, (x, bw, 0.02), (0.0, (y - bw) / 2.0, fz), COL_CELL_EDGE)
        _box(L, (x, bw, 0.02), (0.0, -(y - bw) / 2.0, fz), COL_CELL_EDGE)
        _box(L, (bw, y, 0.02), ((x - bw) / 2.0, 0.0, fz), COL_CELL_EDGE)
        _box(L, (bw, y, 0.02), (-(x - bw) / 2.0, 0.0, fz), COL_CELL_EDGE)
        # the two terminal bus ribbons at the ends of the LONG axis (ADR-052:
        # mounted END-ONLY, no bond across the cell face)
        _box(L, (2.0, y * 0.35, 0.03), ((x / 2.0) - 3.0, 0.0, h + 0.015), COL_CELL_EDGE)
        _box(L, (2.0, y * 0.35, 0.03), (-(x / 2.0) + 3.0, 0.0, h + 0.015), COL_CELL_EDGE)

    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- main
INDEX = os.path.join(OUT_DIR, "MODEL-INDEX.json")

# The `${KICAD*_3DMODEL_DIR}` path each repo-local model replaces.  Kept so a
# machine that HAS the KiCad 3D package can restore the library model; it is also
# the exact list of references that resolved to NOTHING on this host before this
# change (README.md in this directory states the same).
LIBRARY_ORIGIN = {
    "R_0402_1005Metric": "${KICAD9_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_0402_1005Metric.step",
    "C_0402_1005Metric": "${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0402_1005Metric.step",
    "C_1206_3216Metric": "${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_1206_3216Metric.step",
    "CP_Radial_D10.0mm_P5.00mm": "${KICAD9_3DMODEL_DIR}/Capacitor_THT.3dshapes/CP_Radial_D10.0mm_P5.00mm.step",
    "D_SMA": "${KICAD9_3DMODEL_DIR}/Diode_SMD.3dshapes/D_SMA.step",
    "D_SOD-123": "${KICAD9_3DMODEL_DIR}/Diode_SMD.3dshapes/D_SOD-123.step",
    "D_SOD-323": "${KICAD9_3DMODEL_DIR}/Diode_SMD.3dshapes/D_SOD-323.step",
    "LGA-8_3x5mm_P1.25mm": "${KICAD9_3DMODEL_DIR}/Package_LGA.3dshapes/LGA-8_3x5mm_P1.25mm.step",
    "SOT-23-5": "${KICAD9_3DMODEL_DIR}/Package_TO_SOT_SMD.3dshapes/SOT-23-5.step",
    "U.FL_Molex_MCRF_73412-0110_Vertical": "${KICAD9_3DMODEL_DIR}/Connector_Coaxial.3dshapes/U.FL_Molex_MCRF_73412-0110_Vertical.step",
    "ublox_MAX": "${KICAD9_3DMODEL_DIR}/RF_GPS.3dshapes/ublox_MAX.step",
    "ESP32-S3-WROOM-1U": "${KICAD9_3DMODEL_DIR}/RF_Module.3dshapes/ESP32-S3-WROOM-1U.step",
    "NiceRF_LoRa2021": "${KICAD8_3DMODEL_DIR}/RF_Module.3dshapes/NiceRF_LoRa2021.wrl",
    "LoRa2021F33-2G4": None,          # no model existed
    "SX1280_QFN24": None,             # no model existed
    "Wing_Tab_4P": None,              # no model existed
    "SolderJumper-3_P1.3mm": None,    # no model existed
    "SolarCell_LARGE_78.55x38.90": None,   # no model existed
    "SolarCell_SMALL_52.07x19.65": None,   # no model existed
}
# CP_Radial_D10.0mm_P5.00mm height: the footprint drawing fixes the diameter and
# the lead pitch (5.00 mm) but NOT the can height.
MODELS["CP_Radial_D10.0mm_P5.00mm"] = dict(
    x=10.100, y=10.100, h=7.00, kind="box", colour=COL_METAL, extra={},
    src="X/Y: F.Fab body drawing of Capacitor_THT:CP_Radial_D10.0mm_P5.00mm as "
        "committed (10.100 x 10.100 mm); the library item name fixes the lead pitch "
        "at 5.00 mm and the can diameter at 10.0 mm.  The part is the 3.3F 2.7 V "
        "AVX SCC supercap (hub_board_v9 value field).",
    todo=["Z 7.00 mm - the supercap can height is NOT stated in any in-repo record "
          "and 7.00 mm is a DISPLAY DEFAULT, not a claim"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any committed model differs from a fresh emit")
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    drift = []
    index = {}
    for name in sorted(MODELS):
        spec = MODELS[name]
        text = emit(name, spec)
        path = os.path.join(OUT_DIR, name + ".wrl")
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if old != text:
            if a.check:
                drift.append(name)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
        index[name] = {
            "file": name + ".wrl",
            "body_mm": [spec["x"], spec["y"]],
            "height_mm": spec["h"],
            "source": spec["src"],
            "todo_unverified": spec["todo"],
            "replaces_library_model": LIBRARY_ORIGIN.get(name),
        }

    if a.check:
        if drift:
            print("3D MODEL DRIFT: %s" % ", ".join(drift))
            return 1
        print("3d models: %d files, byte-identical to the committed set" % len(MODELS))
        return 0

    idx = {
        "_comment": "Generated by scripts/gen_3d_models.py. "
                    "Maps every repo-local VRML model to the dimensions it was "
                    "built from and to the ${KICAD*_3DMODEL_DIR} reference it "
                    "replaced.  Regenerate with --check in CI.",
        "generator": "scripts/gen_3d_models.py",
        "models": index,
    }
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, sort_keys=True)
        f.write("\n")
    for p in sorted(os.listdir(OUT_DIR)):
        if p.endswith(".wrl"):
            sha = hashlib.sha256(open(os.path.join(OUT_DIR, p), "rb").read()).hexdigest()
            print("%-42s sha256 %s" % (p, sha[:16]))
    print("models written : %d -> %s" % (len(MODELS), os.path.relpath(OUT_DIR, REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
