#!/usr/bin/env python3
"""Bounded pad-centre CC connections; native refill/DRC and physical partition gates.
No search, vias, placement, rule or net edits. Each net is an independent batch.
"""
import collections
import hashlib
import json
import shutil
from pathlib import Path
import pcbnew
from verify_batch import drc, opens_by_net
from physical_partitions import partitions, splits
from check_preservation import objects, ns
ROOT=Path(__file__).resolve().parent

def zones(path):
    tree=ns['parse'](path.read_text())
    return [ns['dump']([q for q in x if not (isinstance(q,list) and q and q[0]=='filled_polygon')])
            for x in tree[1:] if isinstance(x,list) and x[0]=='zone']

def candidate(before, out, net, source, resistor, illegal=False):
    b=pcbnew.LoadBoard(str(before))
    pads={(f.GetReference(),p.GetNumber()):p for f in b.GetFootprints() for p in f.Pads()}
    a=pads['J1',source]; c=pads[resistor,'1']
    assert a.GetNetname()==c.GetNetname()==net
    assert '5.1k' in c.GetParentFootprint().GetValue()
    # Exit connector pad horizontally beyond its copper end before changing y.
    # Bounding box comes from native rotated pad geometry, not nominal footprint size.
    exit_x=a.GetBoundingBox().GetRight()+pcbnew.FromMM(.30)
    assert exit_x<c.GetPosition().x
    points=[a.GetPosition(), pcbnew.VECTOR2I(exit_x,a.GetPosition().y), c.GetPosition()]
    if illegal: points=[a.GetPosition(),pads[resistor,'2'].GetPosition(),c.GetPosition()]
    for start,end in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b); t.SetStart(start); t.SetEnd(end)
        t.SetLayer(pcbnew.F_Cu); t.SetWidth(pcbnew.FromMM(.2)); t.SetNetCode(a.GetNetCode()); b.Add(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(str(out),b)
    shutil.copyfile(before.with_suffix('.kicad_pro'),out.with_suffix('.kicad_pro'))

def check(before, out, net):
    bd=drc(str(before),str(ROOT/'proofs'/f'{out.stem}-before.json'))
    ad=drc(str(out),str(ROOT/'proofs'/f'{out.stem}-after.json'))
    bp,ap=partitions(before),partitions(out)
    new=collections.Counter(json.dumps(v,sort_keys=True) for v in ad['violations'])-collections.Counter(json.dumps(v,sort_keys=True) for v in bd['violations'])
    broken=splits(bp,ap)
    unexpected=[n for n in bp if n!=net and bp[n]!=ap.get(n)]
    old,now=objects(before),objects(out)
    removed=[x for x in (old-now).elements() if not x.startswith('(zone ')]
    added=[x for x in (now-old).elements() if not x.startswith('(zone ')]
    locked=not removed and all(x.startswith('(segment ') for x in added) and zones(before)==zones(out) and before.with_suffix('.kicad_pro').read_bytes()==out.with_suffix('.kicad_pro').read_bytes()
    accepted=not new and not broken and not unexpected and locked and len(ad['unconnected_items'])<len(bd['unconnected_items']) and len(ap[net])==1
    result=dict(accepted=accepted,net=net,opens_before=len(bd['unconnected_items']),opens_after=len(ad['unconnected_items']),opens_by_net_before=opens_by_net(bd['unconnected_items']),opens_by_net_after=opens_by_net(ad['unconnected_items']),new_violation_records=[json.loads(x) for x in new.elements()],prior_partition_splits=broken,unintended_partition_changes=unexpected,locked_objects_preserved=locked,added_segments=len(added),before_partitions=bp,after_partitions=ap,sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    (ROOT/'proofs'/f'{out.stem}-physical-native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['accepted','net','opens_before','opens_after','new_violation_records','prior_partition_splits','unintended_partition_changes','locked_objects_preserved']}))
    return accepted

def main():
    before=ROOT/'batch3.kicad_pcb'
    rejected=ROOT/'rejected-cc.kicad_pcb'
    candidate(before,rejected,'/CC1','A5','R3',True)
    assert not check(before,rejected,'/CC1'), 'illegal GND-crossing control accepted'
    for name,net,source,resistor in [('batch4','/CC1','A5','R3'),('batch5','/CC2','B5','R4')]:
        out=ROOT/(name+'.kicad_pcb')
        assert len(partitions(before)[net])==2, 'already-connected nets must not be touched'
        candidate(before,out,net,source,resistor)
        assert check(before,out,net), 'candidate rejected; do not promote'
        before=out
if __name__=='__main__': main()
