
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
def S(x): return str(x)
print("=== every capacitor on the board")
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    r=fp.GetReference()
    if not r.startswith("C"): continue
    pos=fp.GetPosition(); bb=fp.GetBoundingBox()
    print(f"{r:10s} {S(fp.GetValue())[:16]:18s} {S(fp.GetFPID().GetLibItemName())[:34]:36s} "
          f"({pos.x/MM:6.2f},{pos.y/MM:6.2f}) {bb.GetWidth()/MM:5.2f}x{bb.GetHeight()/MM:5.2f}mm  "
          f"{'DNP' if fp.IsExcludedFromBOM() else 'PLACED'}")

print("\n=== do the storage caps have real pads?")
for ref in ("C_CAP1","C_CAP2"):
    fp=next((f for f in b.GetFootprints() if f.GetReference()==ref), None)
    if fp is None: print(f"  {ref}: NO FOOTPRINT"); continue
    print(f"  {ref}: val={S(fp.GetValue())}  fp={S(fp.GetFPID().GetLibItemName())}  DNP={fp.IsExcludedFromBOM()}")
    for p in fp.Pads():
        pos=p.GetPosition()
        print(f"     pad {S(p.GetNumber()):>2s} net={S(p.GetNetname()) or '(none)':16s} "
              f"({pos.x/MM:6.2f},{pos.y/MM:6.2f}) drill={p.GetDrillSize().x/MM:.2f} size={p.GetSize().x/MM:.2f}x{p.GetSize().y/MM:.2f}")

print("\n=== storage nets")
for net in ("/VSCAP","/SCAP_MID"):
    tr=sum(1 for t in b.GetTracks() if S(t.GetNetname())==net and t.GetClass()!="PCB_VIA")
    vi=sum(1 for t in b.GetTracks() if S(t.GetNetname())==net and t.GetClass()=="PCB_VIA")
    zo=[z for z in b.Zones() if S(z.GetNetname())==net]
    pads=[f"{fp.GetReference()}.{S(p.GetNumber())}" for fp in b.GetFootprints() for p in fp.Pads() if S(p.GetNetname())==net]
    print(f"  {net:12s} trk={tr:3d} via={vi:2d} zones={len(zo)}")
    print(f"     pads: {pads}")
