import pcbnew,json,sys
b=pcbnew.LoadBoard(sys.argv[1]); out=[]
for f in b.GetFootprints():
 if not f.GetReference().startswith('J_W'): continue
 for pad in f.Pads():
  out.append(dict(ref=f.GetReference(),number=pad.GetNumber(),uuid=pad.m_Uuid.AsString(),net=pad.GetNetname(),xy=[pad.GetPosition().x/1e6,pad.GetPosition().y/1e6],layers=[b.GetLayerName(l) for l in [0,2,4,6] if pad.IsOnLayer(l)],attribute=int(pad.GetAttribute())))
print(json.dumps(out,indent=2))
