
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
def S(x): return str(x)
for ref in ("U_LORA1280","U3"):
    fp=next(f for f in b.GetFootprints() if f.GetReference()==ref)
    print(f"\n{ref}  fp={S(fp.GetFPID().GetLibNickname())}:{S(fp.GetFPID().GetLibItemName())}")
    print(f"  pads={len(list(fp.Pads()))}  flipped={fp.IsFlipped()}  DNP={fp.IsExcludedFromBOM()}")
    for p in fp.Pads():
        pos=p.GetPosition()
        print(f"    {S(p.GetNumber()):>2s} ({pos.x/MM:7.3f},{pos.y/MM:7.3f}) drill={p.GetDrillSize().x/MM:.2f} "
              f"size={p.GetSize().x/MM:.2f}x{p.GetSize().y/MM:.2f} net={S(p.GetNetname())}")
