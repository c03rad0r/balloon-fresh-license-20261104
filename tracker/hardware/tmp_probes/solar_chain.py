
import pcbnew
from collections import defaultdict
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
# every pad of the wing sockets
print("=== WING SOCKET PADS")
for fp in b.GetFootprints():
    if fp.GetReference().startswith("J_W"):
        print(f"  {fp.GetReference()}  (flipped={fp.IsFlipped()})")
        for p in fp.Pads():
            print(f"     pad {p.GetNumber():2s} -> {p.GetNetname() or '(none)'}")

# who else is on the solar-negative nets?
print("\n=== NET MEMBERSHIP for the solar chain")
for net in ("/W1_SOLAR_P","/W1_SOLAR_N","/W2_SOLAR_N","/W3_SOLAR_N","/W4_SOLAR_N","/W2_SOLAR_P","/W3_SOLAR_P","/W4_SOLAR_P","GND"):
    pads=[]
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname()==net:
                pads.append(f"{fp.GetReference()}.{p.GetNumber()}")
    tr=sum(1 for t in b.GetTracks() if t.GetNetname()==net and t.GetClass()!="PCB_VIA")
    vi=sum(1 for t in b.GetTracks() if t.GetNetname()==net and t.GetClass()=="PCB_VIA")
    zo=any(z.GetNetname()==net for z in b.Zones())
    print(f"  {net:16s} pads={len(pads):2d} trk={tr:3d} via={vi:2d} zone={'Y' if zo else '-'}  {pads}")
