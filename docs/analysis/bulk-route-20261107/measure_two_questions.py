#!/usr/bin/env python3
"""measure_two_questions.py -- exact geometry for the two things the operator must decide.

Q1  the two-face wing pads: which pad objects exist on J_W4.1 and J_W3.4, on which
    layer each, and are they separate objects sharing one pad number?
Q2  /W2_SOLAR_N: the copper islands, where the B.Cu chain actually ends, where J_W3
    pad 1 is, and how far apart they are -- plus where the J_W3 socket cavity sits,
    because AGENTS 13a forbids a track crossing it.

Everything printed here is read from the board file, not from a previous report.
"""
import os
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb"

b = pcbnew.LoadBoard(BOARD)
MM = 1e6


def mm(v):
    return v / MM


def rect_of(pad):
    bb = pad.GetBoundingBox()
    return (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetX() + bb.GetWidth()), mm(bb.GetY() + bb.GetHeight()))


def lname(lid):
    return b.GetLayerName(lid)


print(f"board: {os.path.basename(BOARD)}")
bb = b.GetBoardEdgesBoundingBox()
print(f"outline bbox: {mm(bb.GetX()):.2f},{mm(bb.GetY()):.2f} .. "
      f"{mm(bb.GetX()+bb.GetWidth()):.2f},{mm(bb.GetY()+bb.GetHeight()):.2f}")

print("\n=== Q1: the wing connector pads in question ===")
for ref in ("J_W3", "J_W4"):
    fp = b.FindFootprintByReference(ref)
    if not fp:
        print(f"  {ref}: NOT FOUND")
        continue
    print(f"\n  {ref}  position=({mm(fp.GetPosition().x):.2f},{mm(fp.GetPosition().y):.2f})  "
          f"layer={lname(fp.GetLayer())}")
    for pad in fp.Pads():
        num = pad.GetNumber()
        if num not in ("1", "4"):
            continue
        r = rect_of(pad)
        drill = pad.GetDrillSize()
        print(f"    pad {ref}.{num}  layer={lname(pad.GetLayer()):8s} "
              f"attr={'PTH' if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else 'SMD'} "
              f"size={mm(pad.GetSize().x):.3f}x{mm(pad.GetSize().y):.3f} "
              f"center=({mm(pad.GetPosition().x):.3f},{mm(pad.GetPosition().y):.3f}) "
              f"bbox=({r[0]:.2f},{r[1]:.2f},{r[2]:.2f},{r[3]:.2f}) "
              f"drill={mm(drill.x):.2f} net={pad.GetNetname()!r}")

print("\n  pads per number on those two connectors (looking for duplicates by number):")
for ref in ("J_W3", "J_W4"):
    fp = b.FindFootprintByReference(ref)
    if not fp:
        continue
    counts = {}
    for pad in fp.Pads():
        counts.setdefault(pad.GetNumber(), []).append(lname(pad.GetLayer()))
    for num, lays in sorted(counts.items(), key=lambda kv: (len(kv[0]), kv[0])):
        if len(lays) > 1:
            print(f"    {ref}.{num}: {len(lays)} pad objects on {lays}")

print("\n=== Q2: /W2_SOLAR_N copper ===")
NET = "/W2_SOLAR_N"
pad_list = [p for p in b.GetPads() if p.GetNetname() == NET]
print(f"  pads on {NET}: {len(pad_list)}")
for p in pad_list:
    print(f"    {p.GetParentFootprint().GetReference()}.{p.GetNumber()} "
          f"layer={lname(p.GetLayer()):8s} center=({mm(p.GetPosition().x):.3f},"
          f"{mm(p.GetPosition().y):.3f})")

seg_end = []
print(f"  tracks/vias on {NET}:")
for t in b.GetTracks():
    if t.GetNetname() != NET:
        continue
    if t.GetClass() == "PCB_VIA":
        print(f"    VIA ({mm(t.GetPosition().x):.3f},{mm(t.GetPosition().y):.3f}) "
              f"d={mm(t.GetWidth()):.2f}")
        continue
    a = (mm(t.GetStart().x), mm(t.GetStart().y))
    e = (mm(t.GetEnd().x), mm(t.GetEnd().y))
    print(f"    TRACK {lname(t.GetLayer()):8s} w={mm(t.GetWidth()):.2f} "
          f"({a[0]:.3f},{a[1]:.3f}) -> ({e[0]:.3f},{e[1]:.3f})  len={mm(t.GetLength()):.3f}")
    if lname(t.GetLayer()) == "B.Cu":
        seg_end.append((a, e))

print("\n=== Q2: J_W3 socket cavity (Edge.Cuts near the connector) ===")
j = b.FindFootprintByReference("J_W3")
if j:
    cx, cy = mm(j.GetPosition().x), mm(j.GetPosition().y)
    print(f"  J_W3 at ({cx:.2f},{cy:.2f})")
    for d in b.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if d.GetClass() == "PCB_SHAPE":
            s = d.GetStart()
            e = d.GetEnd()
            xs, ys = mm(s.x), mm(s.y)
            xe, ye = mm(e.x), mm(e.y)
            if abs(xs - cx) < 8 and abs(ys - cy) < 8:
                print(f"    Edge.Cuts {d.GetShape()!s:12s} "
                      f"({xs:.3f},{ys:.3f}) -> ({xe:.3f},{ye:.3f})")
