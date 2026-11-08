import sys,json,hashlib,importlib.util,collections
from pathlib import Path
import pcbnew as p
R=Path('/home/c08r4d0r/worktrees/c10-jlc-inventory-20261106'); O=Path(__file__).parent
H=R/'tracker/hardware'; B=R/'docs/analysis/c10-silk-acceptance-20261106/candidate/board.kicad_pcb'
spec=importlib.util.spec_from_file_location('parity',H/'check_schematic_parity.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sources={'board':B,'schematic':H/'schematics/flight_board/v10_flight.kicad_sch','committed_netlist':H/'schematics/flight_board/v10_flight.net','registry':H/'connectivity/v10_pinmap.reg','export':O/'v10-export.net'}
nets={'board':m.board_nets(str(B)),'export':m._parse_sexpr_netlist(sources['export'].read_text()),'committed_netlist':m._parse_sexpr_netlist(sources['committed_netlist'].read_text()),'registry':m.registry_nets(str(sources['registry']))}
def binding(n):return {refpin:[net for net,nodes in n.items() if tuple(refpin.split('.')) in nodes] for refpin in ['D_BP4.1','D_BP4.2','J_W4.4','U7.2','C10.2']}
r={'hashes':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sources.items()},'bindings':{k:binding(v) for k,v in nets.items()},'export_vs_committed_equal':nets['export']==nets['committed_netlist'],'registry_vs_export_equal':nets['registry']==nets['export']}
b=p.LoadBoard(str(B)); f=next(f for f in b.GetFootprints() if f.GetReference()=='D_BP4')
r['pads']=[{'number':q.GetNumber(),'net':q.GetNetname(),'uuid':q.m_Uuid.AsString(),'xy':[q.GetPosition().x/1e6,q.GetPosition().y/1e6],'size':[q.GetSize().x/1e6,q.GetSize().y/1e6],'layers':[b.GetLayerName(l) for l in q.GetLayerSet().CuStack()]} for q in f.Pads()]
r['near_tracks']=[{'uuid':t.m_Uuid.AsString(),'net':t.GetNetname(),'layer':t.GetLayerName(),'start':[t.GetStart().x/1e6,t.GetStart().y/1e6],'end':[t.GetEnd().x/1e6,t.GetEnd().y/1e6],'width':t.GetWidth()/1e6} for t in b.GetTracks() if 25<t.GetStart().x/1e6<33 and 0<t.GetStart().y/1e6<10]
erc=json.loads((O/'erc.json').read_text());r['erc_counts']=dict(collections.Counter((v['severity'],v['type']) for s in erc['sheets'] for v in s['violations'])) if False else str(collections.Counter((v['severity'],v['type']) for s in erc['sheets'] for v in s['violations']))
(O/'source-probe.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
