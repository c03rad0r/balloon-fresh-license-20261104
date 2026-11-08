from pathlib import Path
import pcbnew as p,shutil,json,hashlib
R=Path('/home/c08r4d0r/worktrees/o35-ground-repair-20261106'); O=R/'docs/analysis/o35-ground-repair-20261106'; O.mkdir(exist_ok=True)
S=R/'docs/analysis/c10-silk-acceptance-20261106/candidate'
assert hashlib.sha256((S/'board.kicad_pcb').read_bytes()).hexdigest()=='b899ad04f1e61bd4693b52f9a5275b4a406d8dfc59b778138d598ce768b90fbd'
for label in ['baseline','candidate']:
 d=O/label;d.mkdir(exist_ok=True)
 for ext in ['kicad_pcb','kicad_pro','kicad_dru']:shutil.copy2(S/('board.'+ext),d/('board.'+ext))
 b=p.LoadBoard(str(d/'board.kicad_pcb'))
 if label=='candidate':
  pad=next(q for f in b.GetFootprints() if f.GetReference()=='D_BP4' for q in f.Pads() if q.GetNumber()=='2')
  via=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=='ada07303-f780-4328-8252-828fab20734c')
  assert isinstance(via,p.PCB_VIA) and via.GetViaType()==p.VIATYPE_THROUGH and via.GetNetname()==pad.GetNetname()=='GND'
  # Deterministic shortest connection to an existing same-net through-via; no invented via placement.
  t=p.PCB_TRACK(b);t.SetStart(pad.GetPosition());t.SetEnd(via.GetPosition());t.SetWidth(p.FromMM(.2));t.SetLayer(p.B_Cu);t.SetNetCode(pad.GetNetCode());b.Add(t)
  (O/'addition.json').write_text(json.dumps({'track_uuid':t.m_Uuid.AsString(),'existing_via_uuid':via.m_Uuid.AsString(),'start':[29,6],'end':[31.040292,6],'width':.2,'layer':'B.Cu','net':'GND'},indent=2))
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(d/'board.kicad_pcb'),b)
print(O)
