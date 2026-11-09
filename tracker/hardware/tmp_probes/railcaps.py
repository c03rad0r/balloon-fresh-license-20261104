
import pcbnew
from collections import defaultdict
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
def S(x): return str(x)

print("=== which net is each cap on? (input side VSCAP vs output side +3V3)")
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    r=fp.GetReference()
    if not r.startswith("C"): continue
    nets=sorted({S(p.GetNetname()) for p in fp.Pads() if S(p.GetNetname())})
    pos=fp.GetPosition()
    print(f"  {r:8s} {S(fp.GetValue())[:12]:14s} ({pos.x/MM:6.2f},{pos.y/MM:6.2f})  {' <> '.join(nets)}")

print("\n=== U7 LDO pins -> nets")
fp=next(f for f in b.GetFootprints() if f.GetReference()=="U7")
print(f"  {S(fp.GetValue())}  {S(fp.GetFPID().GetLibItemName())}")
for p in fp.Pads():
    print(f"    pad {S(p.GetNumber())} -> {S(p.GetNetname()) or '(none)'}")

print("\n=== total capacitance per rail (only what is FITTED)")
val={}
for fp in b.GetFootprints():
    if not fp.GetReference().startswith("C"): continue
    if fp.IsExcludedFromBOM(): continue
    v=S(fp.GetValue())
    for p in fp.Pads():
        n=S(p.GetNetname())
        if n in ("/VSCAP","+3V3"):
            val.setdefault(n,[]).append((fp.GetReference(), v))
for n,items in val.items():
    print(f"  {n}: {items}")

print("\n=== +3V3 net: how many pads/tracks (is anything decoupling the MCU?)")
n="+3V3"
tr=sum(1 for t in b.GetTracks() if S(t.GetNetname())==n and t.GetClass()!="PCB_VIA")
vi=sum(1 for t in b.GetTracks() if S(t.GetNetname())==n and t.GetClass()=="PCB_VIA")
pads=[f"{fp.GetReference()}.{S(p.GetNumber())}" for fp in b.GetFootprints() for p in fp.Pads() if S(p.GetNetname())==n]
print(f"  {n}: trk={tr} via={vi} pads={len(pads)}")
print(f"  {pads}")
