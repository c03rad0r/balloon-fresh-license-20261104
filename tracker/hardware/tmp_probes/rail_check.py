
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM=1e6
for fp in b.GetFootprints():
    r=fp.GetReference()
    if r.startswith("J_W"):
        p=fp.GetPosition()
        print(f"  {r}  centre ({p.x/MM:6.2f},{p.y/MM:6.2f})   -> sits on {'x=0 edge' if abs(p.x/MM)<1 else ('x=72 edge' if abs(p.x/MM-72)<1 else ('y=0 edge' if abs(p.y/MM)<1 else 'y=80 edge'))}")
