
import pcbnew
from collections import defaultdict
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
trk=defaultdict(int); via=defaultdict(int); zones=set()
for t in b.GetTracks():
    n=t.GetNetname()
    if n:
        if t.GetClass()=="PCB_VIA": via[n]+=1
        else: trk[n]+=1
for z in b.Zones():
    if z.GetNetname(): zones.add(z.GetNetname())

for ref in ("D_BP1","D_BP2","D_BP3","D_BP4"):
    fp=next(f for f in b.GetFootprints() if f.GetReference()==ref)
    print(f"{ref}  flipped={fp.IsFlipped()}  side={fp.GetLayerName()}")
    for p in fp.Pads():
        n=p.GetNetname()
        lay=p.GetLayerName() if hasattr(p,"GetLayerName") else "?"
        cu = "B.Cu" if p.IsOnLayer(pcbnew.B_Cu) else ("F.Cu" if p.IsOnLayer(pcbnew.F_Cu) else "?")
        print(f"   pad {p.GetNumber():2s} net={n or '(none)':22s} copper={cu:5s} "
              f"tracks={trk.get(n,0):3d} vias={via.get(n,0):2d} zone={'Y' if n in zones else '-'}")
