#!/usr/bin/env python3
"""Ask KiCad's OWN connectivity engine, not a shapely reimplementation.

Inter-tool disagreement is a STOP. The shapely graph says C10.1 (+3V3) is an isolated
island; native DRC reports +3V3 with ONE open (J_PROG.2 -> R_F1.1). One of them is wrong.

This prints, per pad, the FULL copper layer set and the items KiCad's CN_CONNECTIVITY says
are connected to it -- the same engine the DRC ratsnest comes from.
"""
import sys

import pcbnew

UM = 1e6


def main(board_path):
    b = pcbnew.LoadBoard(board_path)
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    print("board unconnected count (KiCad):", conn.GetUnconnectedCount(False))

    def dump(ref, num):
        fp = b.FindFootprintByReference(ref)
        pads = [x for x in fp.Pads() if x.GetNumber() == num]
        for p in pads:
            seq = [pcbnew.LayerName(x) for x in p.GetLayerSet().Seq()]
            print(f"\n{ref}.{num} net={p.GetNetname()} attr={p.GetAttribute()} "
                  f"shape={p.GetShape()} drill={p.GetDrillSize().x/UM:.3f}")
            print(f"   layer set = {seq}")
            items = []
            try:
                it = pcbnew.PCB_CONNECTED_ITEM if hasattr(pcbnew, "PCB_CONNECTED_ITEM") else None
                conn.GetConnectedItems(p, items,
                                       pcbnew.ITEM_PAD_T | pcbnew.ITEM_VIA_T
                                       | pcbnew.ITEM_TRACE_T | pcbnew.ITEM_ZONE_T)
            except Exception as exc:            # noqa: BLE001
                print(f"   GetConnectedItems failed: {exc.__class__.__name__}: {exc}")
                items = []
            print(f"   connected items: {len(items)}")
            for q in items[:25]:
                t = type(q).__name__
                if isinstance(q, pcbnew.PAD):
                    tag = f"{q.GetParentFootprint().GetReference()}.{q.GetNumber()}"
                elif isinstance(q, pcbnew.PCB_VIA):
                    pos = q.GetPosition()
                    tag = f"VIA({pos.x/UM:.3f},{pos.y/UM:.3f})"
                elif isinstance(q, pcbnew.PCB_TRACK):
                    a, c = q.GetStart(), q.GetEnd()
                    tag = (f"TRK({a.x/UM:.2f},{a.y/UM:.2f})-({c.x/UM:.2f},{c.y/UM:.2f}) "
                           f"{pcbnew.LayerName(q.GetLayer())}")
                elif isinstance(q, pcbnew.ZONE):
                    tag = f"ZONE {q.GetZoneName() or '?'}"
                else:
                    tag = str(q)
                print(f"      {t:22s} {tag}")

    for ref, num in (("C10", "1"), ("C10", "2"), ("R_F1", "1"), ("J_PROG", "2")):
        dump(ref, num)

    # per-net island count straight from KiCad
    print("\n--- net item counts per target net (KiCad connectivity) ---")
    for net in ("+3V3", "/EN", "/F33_IRQ", "/SPI2_SCK", "/F33_VSENSE",
                "/HUB_PV_MID1", "/HUB_PV_N", "/HUB_PV_P", "/SPI1_MISO",
                "/SPI1_MOSI", "/SPI1_SCK", "/U3_IRQ", "/VSCAP",
                "/W2_SOLAR_N", "/W3_SOLAR_N", "GND"):
        n = b.FindNet(net)
        if n is None:
            print(f"  {net}: NO SUCH NET")
            continue
        pads = [x for f in b.GetFootprints() for x in f.Pads()
                if x.GetNetname() == net]
        print(f"  {net:14s} netcode={n.GetNetCode():3d} pads={len(pads)}")


if __name__ == "__main__":
    main(sys.argv[1])
