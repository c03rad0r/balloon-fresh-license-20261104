#!/usr/bin/env python3
"""order_params.py -- everything a JLCPCB order form asks for, read from the board file.

Read-only. Pulls the values that must be typed into the order page, so they are quoted from
the board rather than remembered: dimensions, layer count, thickness, copper weight, finish,
solder mask, surface finish, min track/space, min drill, and the pad-level constraints that
JLCPCB will check in their own DFM tool.

pcbnew does not expose the stackup directly, so the .kicad_pcb setup block is parsed as text
as well. Both are reported: what the design says, and what the geometry measures.
"""
import re
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb"
MM = 1e6

b = pcbnew.LoadBoard(BOARD)
txt = open(BOARD, encoding="utf-8", errors="replace").read()

bb = b.GetBoardEdgesBoundingBox()
w, h = bb.GetWidth() / MM, bb.GetHeight() / MM
print(f"board file : {BOARD.split('/')[-1]}")
print(f"outline    : {w:.2f} x {h:.2f} mm   (bbox, includes any edge tabs)")
print(f"area       : {w * h:.1f} mm2")

copper = [b.GetLayerName(l) for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)]
print(f"copper     : {len(copper)} layers -> {', '.join(copper)}")

# --- text parse of the setup / stackup block
m = re.search(r"\(general\s*\(thickness\s*([\d.]+)\)", txt)
print(f"thickness  : {m.group(1) if m else 'NOT SET'} mm   (from (general (thickness ...)))")

stack = re.search(r"\(stackup(.*?)\n\t\t\)", txt, re.S)
if stack:
    body = stack.group(1)
    print("\nstackup block:")
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("(layer ") or "thickness" in s or "material" in s or "copper_finish" in s:
            print(f"  {s[:100]}")
else:
    print("\nstackup block: ABSENT (KiCad will use its default for the layer count)")

for key in ("copper_finish", "dielectric_constraints", "solder_mask_color",
            "silk_screen_color", "edge_plating", "castellated"):
    m = re.search(rf"\({key}[^)]*\)", txt)
    if m:
        print(f"{key:22s}: {m.group(0)[:70]}")

# --- measured geometry: what JLCPCB's DFM actually checks
tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
if tracks:
    print(f"\nmin track width : {min(t.GetWidth() for t in tracks) / MM:.3f} mm "
          f"({len(tracks)} tracks)")
if vias:
    print(f"min via drill   : {min(t.GetDrill() for t in vias) / MM:.3f} mm "
          f"({len(vias)} vias)")
    print(f"min via diameter: {min(t.GetWidth() for t in vias) / MM:.3f} mm")
    ann = min((t.GetWidth() - t.GetDrill()) / 2 for t in vias) / MM
    print(f"min via annulus : {ann:.3f} mm")

pads = list(b.GetPads())
smd = [p for p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
pth = [p for p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
print(f"\npads            : {len(pads)} total, {len(smd)} SMD, {len(pth)} PTH")
if smd:
    smallest = min(smd, key=lambda p: p.GetSize().x * p.GetSize().y)
    print(f"smallest SMD pad: {smallest.GetSize().x / MM:.3f} x "
          f"{smallest.GetSize().y / MM:.3f} mm "
          f"({smallest.GetParentFootprint().GetReference()}.{smallest.GetNumber()})")

# drill histogram from the generated fab file if present, since that is what ships
import os
drl = os.path.join(os.path.dirname(BOARD), "fab-11opens", "board.drl")
if os.path.exists(drl):
    sizes, hits, tool = {}, {}, None
    for line in open(drl):
        line = line.strip()
        m = re.match(r"^T(\d+)C([\d.]+)$", line)
        if m:
            sizes[m.group(1)] = float(m.group(2)); continue
        m = re.match(r"^T(\d+)$", line)
        if m:
            tool = m.group(1); continue
        if line.startswith("X") and tool:
            hits[tool] = hits.get(tool, 0) + 1
    print(f"\ndrill table shipped ({os.path.basename(drl)}):")
    for t, s in sorted(sizes.items(), key=lambda kv: kv[1]):
        print(f"  {s:.3f} mm  x{hits.get(t, 0):3d}")
    print(f"  total holes: {sum(hits.values())}")
