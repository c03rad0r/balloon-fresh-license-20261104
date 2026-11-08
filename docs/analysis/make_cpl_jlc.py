"""Write the JLCPCB CPL, with the Y transform VERIFIED against board coordinates, not assumed.

KiCad's pos exporter writes Y negative (internal Y points down from a top-left origin). JLCPCB
wants Y positive upward from the bottom-left. Per FINDING-cpl-coordinate-transform.md:

    jlc_y = H + cpl_y

That earlier finding derived H = 80.0 from a 72.00 x 80.00 board. THIS board's Edge.Cuts bounding
box is 72.10 x 80.10 (y -0.050 .. 80.050), so H = 80.100. Using 80.0 would shift every part by
0.100 mm -- small enough to look plausible and wrong.

So H is measured here, not hardcoded, and every row is checked against pcbnew's own footprint
position before the file is written.
"""
import csv
import pcbnew as p

BOARD = "asm.kicad_pcb"
SRC = "asm-cpl-raw.csv"
OUT = "asm-cpl-jlc.csv"

b = p.LoadBoard(BOARD)
bb = b.GetBoardEdgesBoundingBox()
H = bb.GetHeight() / 1e6
X0 = bb.GetLeft() / 1e6
Y0 = bb.GetTop() / 1e6
print("board bbox  x %.3f..%.3f  y %.3f..%.3f" % (X0, bb.GetRight() / 1e6, Y0, bb.GetBottom() / 1e6))
print("measured H = %.3f mm   (X0 = %.3f, Y0 = %.3f)" % (H, X0, Y0))

# Truth: each footprint's position in pcbnew coordinates (Y down, origin at board top-left + margin)
truth = {}
for f in b.GetFootprints():
    if f.GetAttributes() & p.FP_EXCLUDE_FROM_POS_FILES:
        continue
    pos = f.GetPosition()
    truth[str(f.GetReference())] = (pos.x / 1e6, pos.y / 1e6, f.GetLayerName())

rows = []
with open(SRC) as fh:
    for r in csv.DictReader(fh):
        ref = r["Ref"]
        cx, cy = float(r["PosX"]), float(r["PosY"])
        # KiCad internal Y is measured from the top; jlc Y is from the bottom, positive up.
        board_y = -cy                    # undo the exporter's sign
        jlc_y = H - board_y              # flip about the board height
        jlc_x = cx
        rows.append({
            "Designator": ref,
            "Val": r["Val"],
            "Package": r["Package"],
            "Mid X": "%.4f" % jlc_x,
            "Mid Y": "%.4f" % jlc_y,
            "Layer": "Top" if r["Side"] == "top" else "Bottom",
            "Rotation": "%.1f" % float(r["Rot"]),
        })

# VERIFY every row against pcbnew's own coordinates before writing.
bad = []
for r in rows:
    tx, ty, layer = truth[r["Designator"]]
    # tx,ty are pcbnew coords (Y down from origin 0). jlc_x should equal tx, jlc_y should equal H - ty.
    ex = abs(float(r["Mid X"]) - tx)
    ey = abs(float(r["Mid Y"]) - (H - ty))
    if ex > 1e-3 or ey > 1e-3:
        bad.append((r["Designator"], ex, ey))

print()
if bad:
    print("MISMATCH on %d row(s) -- first 5:" % len(bad))
    for ref, ex, ey in bad[:5]:
        print("   %-10s dx %.4f  dy %.4f" % (ref, ex, ey))
else:
    print("VERIFIED: all %d rows match pcbnew footprint coordinates to <0.001 mm" % len(rows))

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["Designator", "Val", "Package", "Mid X", "Mid Y", "Layer", "Rotation"])
    w.writeheader()
    w.writerows(rows)
print("wrote %s (%d placements)" % (OUT, len(rows)))

tops = [r for r in rows if r["Layer"] == "Top"]
bots = [r for r in rows if r["Layer"] == "Bottom"]
print("  Top: %d   Bottom: %d" % (len(tops), len(bots)))
print("  X range %.2f .. %.2f   Y range %.2f .. %.2f"
      % (min(float(r["Mid X"]) for r in rows), max(float(r["Mid X"]) for r in rows),
         min(float(r["Mid Y"]) for r in rows), max(float(r["Mid Y"]) for r in rows)))
