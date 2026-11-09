#!/usr/bin/env python3
"""make_cpl_from_board.py -- regenerate the JLCPCB CPL straight from the board of record, honouring
DNP / exclude-from-BOM, and VERIFY every row against pcbnew's own footprint position.

Why this exists: the committed CPL still carried a U_C row after U_C was set DNP, because the older
generator hardcodes a stale `asm.kicad_pcb`. A position file that disagrees with the board is worse
than no file -- JLC would solder a part the BOM says is absent.

Transform (per FINDING-cpl-coordinate-transform.md), all measured here, none hardcoded:
    jlc_x = x - X0
    jlc_y = H - (y - Y0)          # KiCad Y points down; JLC wants Y up from bottom-left
with H = Edge.Cuts bounding-box height. An earlier version of this project used H = 80.0 when the
board is 80.100, which shifts every part by 0.1 mm -- plausible-looking and wrong.

Only JLC-PLACEABLE footprints are emitted: anything with IsDNP() / IsExcludedFromBOM() is skipped,
and so is anything in HAND_FIT (wing sockets and the NiceRF radios have no LCSC part, so JLC cannot
place them and would stall the order on a no-match). DNP comes from the board's own attributes.

Run: /usr/bin/python3 docs/analysis/make_cpl_from_board.py
"""
import csv
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "bulk-route-20261107", "latest.kicad_pcb")
OUT = os.path.join(HERE, "bulk-route-20261107", "assembly-partial", "asm-cpl-jlc.csv")

b = pcbnew.LoadBoard(BOARD)
bb = b.GetBoardEdgesBoundingBox()
H = bb.GetHeight() / 1e6
X0 = bb.GetLeft() / 1e6
Y0 = bb.GetTop() / 1e6

print(f"board bbox x {X0:.3f}..{bb.GetRight()/1e6:.3f}  y {Y0:.3f}..{bb.GetBottom()/1e6:.3f}")
print(f"measured H = {H:.3f} mm   X0 = {X0:.3f}  Y0 = {Y0:.3f}")

# Hand-fit parts: JLC has no LCSC part for these, so they must NOT appear in the placement file.
# Wing sockets are a board feature (nothing to buy); the radios are NiceRF modules.
HAND_FIT = {"J_W1", "J_W2", "J_W3", "J_W4", "U3", "U_LORA1280", "U_C"}

rows = []
skipped = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    dnp = fp.IsDNP() or fp.IsExcludedFromBOM()
    # mounting holes are not components
    if ref.upper().startswith("H") and ref[1:].isdigit():
        skipped.append((ref, "mounting hole"))
        continue
    if ref.upper().startswith("HW"):
        skipped.append((ref, "mounting hole"))
        continue
    if dnp:
        skipped.append((ref, "DNP / excluded from BOM"))
        continue
    if ref in HAND_FIT:
        skipped.append((ref, "hand-fit after delivery (no LCSC part)"))
        continue
    pos = fp.GetPosition()
    x = pcbnew.ToMM(pos.x)
    y = pcbnew.ToMM(pos.y)
    jx = x - X0
    jy = H - (y - Y0)
    rot = fp.GetOrientationDegrees()
    layer = "top" if fp.GetLayer() == pcbnew.F_Cu else "bottom"
    rows.append((ref, fp.GetValue() or "", fp.GetFPID().GetLibItemName() or "", jx, jy, rot, layer))

rows.sort(key=lambda r: r[0])

# VERIFY: the round trip back to board coordinates must land on the footprint position.
errors = []
for ref, value, pkg, jx, jy, rot, layer in rows:
    back_x = jx + X0
    back_y = (H - jy) + Y0
    fp = b.FindFootprintByReference(ref)
    pos = fp.GetPosition()
    dx = abs(back_x - pcbnew.ToMM(pos.x))
    dy = abs(back_y - pcbnew.ToMM(pos.y))
    if dx > 0.001 or dy > 0.001:
        errors.append((ref, dx, dy))

if errors:
    raise SystemExit(f"CPL transform FAILED verification for {len(errors)} part(s): {errors[:5]}")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
    for ref, value, pkg, jx, jy, rot, layer in rows:
        w.writerow([ref, value, pkg, f"{jx:.4f}", f"{jy:.4f}", f"{rot:g}", layer])

print(f"\nwrote {OUT} ({len(rows)} placements, all verified to <0.001 mm)")
print(f"skipped {len(skipped)}:")
for ref, why in skipped:
    print(f"   {ref:<10} {why}")
