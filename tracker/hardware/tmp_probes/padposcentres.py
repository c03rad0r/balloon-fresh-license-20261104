
import pcbnew, json
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
out={}
for fp in b.GetFootprints():
    ps=list(fp.Pads())
    if not ps: continue
    xs=[p.GetPosition().x/MM for p in ps]; ys=[p.GetPosition().y/MM for p in ps]
    out[fp.GetReference()]=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2)
print(json.dumps(out))
