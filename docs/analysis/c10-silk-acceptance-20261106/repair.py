from pathlib import Path
import pcbnew as p, json, hashlib
O=Path(__file__).parent
b=p.LoadBoard(str(O/'candidate/board.kicad_pcb'))
f=next(f for f in b.GetFootprints() if f.GetReference()=='C10')
r=f.Reference(); before=[r.GetPosition().x,r.GetPosition().y]
assert before==[8530000,41420000]
r.SetPosition(p.VECTOR2I(before[0],before[1]-220000))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(O/'candidate/board.kicad_pcb'),b)
b=p.LoadBoard(str(O/'baseline/board.kicad_pcb'));p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(O/'baseline/board.kicad_pcb'),b)
(O/'repair.json').write_text(json.dumps({'scope':'C10 reference only; restore pre-whole-footprint-move text y','before_nm':before,'after_nm':[before[0],before[1]-220000]},indent=2))
