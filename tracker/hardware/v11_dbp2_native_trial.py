#!/usr/bin/python3
"""Native D_BP2 placement-only trial; never writes the source board."""
import json, shutil, subprocess
from pathlib import Path
from collections import Counter
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'docs/analysis/bulk-route-20261107/work.kicad_pcb'
OUT=ROOT/'docs/analysis/v11-dbp2-native'
OUT.mkdir(exist_ok=True)
def identity(v):
    return (v['type'],tuple(sorted(i['uuid'] for i in v.get('items',[]))))
def run(name,site=None,poison=False):
    dst=SRC.with_name('v11-dbp2-'+name+'.kicad_pcb')
    for ext in ('.kicad_pro','.kicad_dru'):
        shutil.copyfile(SRC.with_suffix(ext),dst.with_suffix(ext))
    b=p.LoadBoard(str(SRC)); f=b.FindFootprintByReference('D_BP2')
    old=[{'pad':x.GetNumber(),'net':x.GetNetname(),'xy_mm':[p.ToMM(x.GetPosition().x),p.ToMM(x.GetPosition().y)]} for x in f.Pads()]
    if site:
        if f.IsFlipped(): f.Flip(f.GetPosition(),False)
        f.SetOrientationDegrees(site[2]); f.SetPosition(p.VECTOR2I(p.FromMM(site[0]),p.FromMM(site[1])))
    if poison:
        pad=list(f.Pads())[0]
        t=p.PCB_TRACK(b); t.SetStart(pad.GetPosition()); t.SetEnd(pad.GetPosition()+p.VECTOR2I(p.FromMM(1),0)); t.SetWidth(p.FromMM(.5)); t.SetLayer(p.F_Cu)
        t.SetNetCode(b.FindNet('GND').GetNetCode()); b.Add(t)
    # Native polygons and explicit layer membership, not circles or body keepouts.
    pads=[]
    for x in f.Pads():
        poly=x.GetEffectivePolygon(p.F_Cu) if x.IsOnLayer(p.F_Cu) else None
        pads.append({'pad':x.GetNumber(),'net':x.GetNetname(),'xy_mm':[p.ToMM(x.GetPosition().x),p.ToMM(x.GetPosition().y)],'F_Cu':x.IsOnLayer(p.F_Cu),'polygon_outlines':poly.OutlineCount() if poly else 0})
    p.ZONE_FILLER(b).Fill(b.Zones()); p.SaveBoard(str(dst),b)
    report=OUT/(name+'.json')
    subprocess.run(['kicad-cli','pcb','drc','--format','json','--severity-all','--output',str(report),str(dst)],check=True,stdout=subprocess.DEVNULL)
    data=json.loads(report.read_text())
    return {'name':name,'board':str(dst.relative_to(ROOT)),'old_endpoints':old,'new_endpoints':pads,'violations':data['violations'],'unconnected':data.get('unconnected_items',[])}
def main():
    baseline=run('baseline'); counts=Counter(identity(v) for v in baseline['violations'])
    results=[]
    for name,site,poison in [('spec',(36.5,77,0),False),('nearby',(36.5,74,0),False),('poison',(36.5,77,0),True)]:
        r=run(name,site,poison); seen=Counter(); added=[]
        for v in r.pop('violations'):
            k=identity(v); seen[k]+=1
            if seen[k]>counts[k]: added.append(v)
        r['introduced']=added
        r['legal_placement']=not any(v['type'] in ('shorting_items','clearance','copper_edge_clearance','courtyards_overlap','courtyard_overlap','overlapping_footprints') for v in added)
        results.append(r)
        print(name,r['legal_placement'],dict(Counter(v['type'] for v in added)),flush=True)
    spec_shorts={identity(v) for v in results[0]['introduced'] if v['type']=='shorting_items'}
    poison_shorts={identity(v) for v in results[-1]['introduced'] if v['type']=='shorting_items'}
    assert poison_shorts-spec_shorts,'planted overlap did not introduce a native short identity'
    assert not results[-1]['legal_placement'],'planted overlap escaped validator'
    (OUT/'summary.json').write_text(json.dumps({'baseline_counts':dict(Counter(v['type'] for v in baseline['violations'])),'results':results},indent=2))
if __name__=='__main__': main()
