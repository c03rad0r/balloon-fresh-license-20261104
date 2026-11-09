
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
fp=next(f for f in b.GetFootprints() if f.GetReference()=="U1")
print("anchor GetPosition():", fp.GetPosition().x/MM, fp.GetPosition().y/MM)

# PAD bbox (copper extents)
xs=[];ys=[]
for p in fp.Pads():
    bb=p.GetBoundingBox()
    xs += [bb.GetX()/MM,(bb.GetX()+bb.GetWidth())/MM]
    ys += [bb.GetY()/MM,(bb.GetY()+bb.GetHeight())/MM]
print(f"pad bbox       : x {min(xs):.4f}..{max(xs):.4f}  centre {(min(xs)+max(xs))/2:.4f}")
print(f"                 y {min(ys):.4f}..{max(ys):.4f}  centre {(min(ys)+max(ys))/2:.4f}")

# pad POSITION centres (not extents)
xs2=[p.GetPosition().x/MM for p in fp.Pads()]
ys2=[p.GetPosition().y/MM for p in fp.Pads()]
print(f"pad-position   : x {min(xs2):.4f}..{max(xs2):.4f}  centre {(min(xs2)+max(xs2))/2:.4f}")
print(f"                 y {min(ys2):.4f}..{max(ys2):.4f}  centre {(min(ys2)+max(ys2))/2:.4f}")

# courtyard / body
try:
    cy=fp.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount():
        bb=cy.BBox()
        print(f"courtyard      : centre ({(bb.GetX()+bb.GetWidth()/2)/MM:.4f},{(bb.GetY()+bb.GetHeight()/2)/MM:.4f})")
except Exception as e:
    print("courtyard err", e)

pad_count=len(list(fp.Pads()))
print("pad count:", pad_count)
ys3=sorted(set(round(p.GetPosition().y/MM,3) for p in fp.Pads()))
print("distinct pad y rows:", len(ys3), ys3[:6], "...", ys3[-4:])
