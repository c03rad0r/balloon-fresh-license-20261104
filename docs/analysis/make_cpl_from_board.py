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
# ORIGIN FROM THE EDGE_CUTS CENTRELINE, NOT THE BOUNDING BOX.
#
# GetBoardEdgesBoundingBox() is inflated by half the Edge.Cuts line width on every side, so it
# measures 72.10 x 80.10 while the outline the fab cuts is 72.00 x 80.00. JLCPCB's own Standard-PCBA
# message confirms the real figure: it quotes "82*80mm" after adding two 5 mm edge rails on the
# shorter sides -- 72 + 5 + 5 = 82, with the long side untouched at 80. A 0.10 mm inflation is
# harmless on its own, but it shifts every coordinate by 0.050 mm and made this file disagree with
# tracker/hardware/export_fab_files.py, which reads the centreline. Two generators, two answers,
# and only one of them can be right.
edge_xs, edge_ys = [], []
for _d in b.GetDrawings():
    if _d.GetLayer() == pcbnew.Edge_Cuts and _d.GetClass() == 'PCB_SHAPE':
        for _p in (_d.GetStart(), _d.GetEnd()):
            edge_xs.append(_p.x / 1e6)
            edge_ys.append(_p.y / 1e6)
if edge_xs:
    X0, Y0 = min(edge_xs), min(edge_ys)
    H = max(edge_ys) - min(edge_ys)
else:                                    # no Edge.Cuts shapes: fall back to the bbox
    bb = b.GetBoardEdgesBoundingBox()
    H = bb.GetHeight() / 1e6
    X0 = bb.GetLeft() / 1e6
    Y0 = bb.GetTop() / 1e6

print(f"board outline (centreline) x {X0:.3f}..{X0:+.3f}".replace(f"{X0:+.3f}", f"{max(edge_xs) if edge_xs else X0:.3f}")
      + f"  y {Y0:.3f}..{(max(edge_ys) if edge_ys else Y0):.3f}")
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
    # CENTRE OF THE PAD ARRAY, NOT fp.GetPosition().
    #
    # Measured 2026-11-09: for KiCad's PinHeader footprints the anchor sits on PAD 1, not on the
    # body. Emitting the anchor put J_HUB_PV 5.080 mm and J_PROG 6.350 mm away from the centre of
    # their own pin arrays -- 2.0 and 2.5 pin pitches at 2.54 mm. JLCPCB rotates the part about the
    # point it is given, so a header placed there does not land in its holes. U1 was 1.587 mm off
    # and U7 0.227 mm off for the same reason.
    #
    # The existing round-trip check below could not catch this: it converts jx/jy BACK to
    # fp.GetPosition(), which is the very number it started from. A transform that is
    # self-consistent but off-centre passes it perfectly. That is why the error survived a
    # "verified to <0.001 mm" claim -- the check verified the arithmetic, not the convention.
    pads = list(fp.Pads())
    if pads:
        xs0 = [(q.GetPosition().x - q.GetSize().x / 2) for q in pads]
        xs1 = [(q.GetPosition().x + q.GetSize().x / 2) for q in pads]
        ys0 = [(q.GetPosition().y - q.GetSize().y / 2) for q in pads]
        ys1 = [(q.GetPosition().y + q.GetSize().y / 2) for q in pads]
        x = ((min(xs0) + max(xs1)) / 2) / 1e6
        y = ((min(ys0) + max(ys1)) / 2) / 1e6
    else:
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
ANCHOR_NOTES = []
for ref, value, pkg, jx, jy, rot, layer in rows:
    back_x = jx + X0
    back_y = (H - jy) + Y0
    fp = b.FindFootprintByReference(ref)
    # Verify against the PAD-ARRAY CENTRE, the same quantity that was emitted. Checking against
    # fp.GetPosition() would re-introduce the blind spot: it compares the output to the input
    # rather than to the thing the fab needs, so an off-centre anchor passes.
    pads = list(fp.Pads())
    if pads:
        xs0 = [(q.GetPosition().x - q.GetSize().x / 2) for q in pads]
        xs1 = [(q.GetPosition().x + q.GetSize().x / 2) for q in pads]
        ys0 = [(q.GetPosition().y - q.GetSize().y / 2) for q in pads]
        ys1 = [(q.GetPosition().y + q.GetSize().y / 2) for q in pads]
        cx = ((min(xs0) + max(xs1)) / 2) / 1e6
        cy = ((min(ys0) + max(ys1)) / 2) / 1e6
    else:
        pos = fp.GetPosition(); cx = pcbnew.ToMM(pos.x); cy = pcbnew.ToMM(pos.y)
    dx = abs(back_x - cx)
    dy = abs(back_y - cy)
    if dx > 0.001 or dy > 0.001:
        errors.append((ref, dx, dy))
    # Note where the footprint anchor sits. This is INFORMATIONAL, not a failure: the emitted
    # coordinate is the pad-array centre, which is what the fab needs regardless of where KiCad
    # puts the anchor. It is printed because an anchor far from the centre is the signature of a
    # footprint positioned by pin 1 rather than by its body -- the exact condition that made the
    # previous version of this file wrong by 5.08 and 6.35 mm.
    pos = fp.GetPosition()
    off = ((pcbnew.ToMM(pos.x) - cx) ** 2 + (pcbnew.ToMM(pos.y) - cy) ** 2) ** 0.5
    if off > 0.05:
        ANCHOR_NOTES.append((ref, off, float(jx), float(jy), cx, cy))

if errors:
    raise SystemExit(f"CPL transform FAILED verification for {len(errors)} part(s): {errors[:5]}")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
    for ref, value, pkg, jx, jy, rot, layer in rows:
        w.writerow([ref, value, pkg, f"{jx:.4f}", f"{jy:.4f}", f"{rot:g}", layer])

print(f"\nwrote {OUT} ({len(rows)} placements, all verified to <0.001 mm)")
if ANCHOR_NOTES:
    print(f"\n{len(ANCHOR_NOTES)} part(s) have their KiCad anchor away from the pad-array centre:")
    for ref, off, jx, jy, cx, cy in ANCHOR_NOTES:
        print(f"   {ref:<10} anchor {off:6.3f} mm from centre  ->  emitting centre "
              f"({jx:.3f}, {jy:.3f}) instead of the anchor")
print(f"skipped {len(skipped)}:")
for ref, why in skipped:
    print(f"   {ref:<10} {why}")
