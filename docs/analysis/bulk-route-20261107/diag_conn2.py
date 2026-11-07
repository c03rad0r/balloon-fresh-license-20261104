#!/usr/bin/env python3
"""Ask KiCad's CONNECTIVITY_DATA which items are attached to a pad.

The correct item-type constants in KiCad 9 python are PCB_PAD_T / PCB_VIA_T / PCB_TRACE_T /
PCB_ZONE_T (there is no ITEM_PAD_T). An earlier probe used the wrong names, swallowed the
AttributeError, and printed "connected items: 0" for EVERY pad -- which reads exactly like
"this pad is isolated". That is the silent-success shape: a predicate that tests nothing
reports nothing.
"""
import sys

import pcbnew

UM = 1e6
TYPES = [pcbnew.PCB_PAD_T, pcbnew.PCB_VIA_T, pcbnew.PCB_TRACE_T, pcbnew.PCB_ZONE_T]


def tag(q):
    if isinstance(q, pcbnew.PAD):
        return f"PAD {q.GetParentFootprint().GetReference()}.{q.GetNumber()}"
    if isinstance(q, pcbnew.PCB_VIA):
        p = q.GetPosition()
        return f"VIA ({p.x/UM:.3f},{p.y/UM:.3f}) dia={q.GetWidth(pcbnew.F_Cu)/UM:.2f}"
    if isinstance(q, pcbnew.PCB_TRACK):
        a, c = q.GetStart(), q.GetEnd()
        return (f"TRACE {pcbnew.LayerName(q.GetLayer())} "
                f"({a.x/UM:.2f},{a.y/UM:.2f})-({c.x/UM:.2f},{c.y/UM:.2f}) "
                f"w={q.GetWidth()/UM:.2f}")
    if isinstance(q, pcbnew.ZONE):
        return f"ZONE {q.GetZoneName() or '?'} net={q.GetNetname()}"
    return type(q).__name__


def main(board_path):
    b = pcbnew.LoadBoard(board_path)
    conn = b.GetConnectivity()
    print("KiCad unconnected count:", conn.GetUnconnectedCount(False))
    for ref, num in (("C10", "1"), ("C10", "2"), ("R_F1", "1"), ("U1", "2"),
                     ("R_BAL1", "1")):
        fp = b.FindFootprintByReference(ref)
        for p in [x for x in fp.Pads() if x.GetNumber() == num]:
            items = conn.GetConnectedItems(p, TYPES, False)
            print(f"\n{ref}.{num} net={p.GetNetname()} connected_items={len(items)}")
            for q in items[:20]:
                print("   ", tag(q))
    # how many +3V3 islands does KiCad see? count distinct via the pad reachability sets
    print("\n+3V3 pad reachability (component id = smallest pad tag in the set):")
    pads = [x for f in b.GetFootprints() for x in f.Pads() if x.GetNetname() == "+3V3"]
    seen = {}
    for p in pads:
        items = conn.GetConnectedItems(p, TYPES, False)
        key = frozenset(tag(q) for q in items if isinstance(q, pcbnew.PAD))
        seen.setdefault(key, []).append(f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}")
    for key, members in seen.items():
        print(f"  island of {len(members)} pad(s): {sorted(members)}")


if __name__ == "__main__":
    main(sys.argv[1])
