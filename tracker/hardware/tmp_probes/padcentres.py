
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
out={}
for fp in b.GetFootprints():
    xs=[];ys=[]
    for p in fp.Pads():
        bb=p.GetBoundingBox()
        xs += [bb.GetX()/MM,(bb.GetX()+bb.GetWidth())/MM]
        ys += [bb.GetY()/MM,(bb.GetY()+bb.GetHeight())/MM]
    if xs:
        out[fp.GetReference()]=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2)
import json; print(json.dumps(out))
