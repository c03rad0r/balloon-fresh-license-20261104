
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
for ref in ("J_HUB_PV","J_PROG"):
    fp=next(f for f in b.GetFootprints() if f.GetReference()==ref)
    print(f"\n{ref}: {fp.GetFPID().GetLibItemName()}")
    print("  pads (number, x, y, pad-shape, drill):")
    for p in fp.Pads():
        pos=p.GetPosition()
        sh_ = {0:"CIRCLE",1:"RECT",2:"OVAL",3:"TRAPEZOID",4:"ROUNDRECT"}.get(int(p.GetShape()),str(p.GetShape()))
        print(f"    {p.GetNumber():>2s}  ({pos.x/MM:7.3f},{pos.y/MM:7.3f})  {sh_:9s} drill={p.GetDrillSize().x/MM:.2f}  size={p.GetSize().x/MM:.2f}x{p.GetSize().y/MM:.2f}")
