
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
for ref in ("J_HUB_PV","J_PROG"):
    fp=next(f for f in b.GetFootprints() if f.GetReference()==ref)
    print(f"\n{ref}")
    print(f"  footprint: {fp.GetFPID().GetLibNickname()}:{fp.GetFPID().GetLibItemName()}")
    print(f"  orientation: {fp.GetOrientationDegrees()} deg   flipped={fp.IsFlipped()}")
    print(f"  pads: {len(list(fp.Pads()))}")
    xs=[]; ys=[]; drill=[]
    for p in fp.Pads():
        pos=p.GetPosition()
        xs.append(pos.x/MM); ys.append(pos.y/MM)
        drill.append(p.GetDrillSize().x/MM)
    print(f"  pad span: x {min(xs):.2f}..{max(xs):.2f} ({max(xs)-min(xs):.2f})  "
          f"y {min(ys):.2f}..{max(ys):.2f} ({max(ys)-min(ys):.2f})")
    print(f"  drill: {sorted(set(round(d,2) for d in drill))}")
    n3d = fp.Models().size() if hasattr(fp,"Models") else 0
    print(f"  embedded 3D models: {n3d}")
    for i in range(n3d):
        m=fp.Models()[i]
        print(f"    -> {m.m_Filename}")
