#!/usr/bin/env python3
"""One bounded exact pad-centre segment, native refill/DRC as acceptance oracle.
Not a router. No placement or rule edits; no vias. Illegal control deliberately
runs through adjacent U2.6. Full native checks include filled zones and local keepouts.
"""
import collections
import hashlib
import json
from pathlib import Path
import shutil
import pcbnew
from verify_batch import drc, opens_by_net
from physical_partitions import partitions, splits, pairs

ROOT=Path(__file__).resolve().parent

def signature(v):
    return json.dumps(v, sort_keys=True)

def make(out, illegal=False):
    b=pcbnew.LoadBoard(str(ROOT/'batch2.kicad_pcb'))
    pads={(f.GetReference(),p.GetNumber()):p for f in b.GetFootprints() for p in f.Pads()}
    a=pads['U2','7']; c=pads['L1','1']
    assert a.GetNetname()==c.GetNetname()=='/BUCK_SW'
    assert a.GetPosition().y==c.GetPosition().y
    points=[a.GetPosition(), c.GetPosition()]
    if illegal: points.insert(1,pads['U2','6'].GetPosition())
    for start,end in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b); t.SetStart(start); t.SetEnd(end)
        t.SetLayer(pcbnew.F_Cu); t.SetWidth(pcbnew.FromMM(.2)); t.SetNetCode(a.GetNetCode()); b.Add(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(str(out),b)
    shutil.copyfile(ROOT/'batch2.kicad_pro',out.with_suffix('.kicad_pro'))


def main():
    # Native DRC has UUID-bearing item records but no unique violation UUID.
    # Compare entire records, not just classes/counts, and retain exact records.
    proofdir=ROOT/'proofs'
    before=drc(str(ROOT/'batch2.kicad_pcb'),str(proofdir/'batch3-native-before.json'))
    old=collections.Counter(signature(v) for v in before['violations'])
    history={name:partitions(ROOT/(name+'.kicad_pcb')) for name in ('batch0','batch1','batch2')}
    prior_splits={a+'->'+b:splits(history[a],history[b]) for a,b in [('batch0','batch1'),('batch1','batch2')]}
    assert not any(prior_splits.values()), prior_splits
    assert len(history['batch2']['/GND'])==1
    outcomes={}
    for name,illegal in [('rejected-buck',True),('batch3',False)]:
        out=ROOT/(name+'.kicad_pcb'); make(out,illegal)
        d=drc(str(out),str(proofdir/(name+'-native-after.json')))
        new=collections.Counter(signature(v) for v in d['violations'])-old
        after=partitions(out)
        broken=splits(history['batch2'],after)
        accepted=not new and not broken and len(d['unconnected_items'])<len(before['unconnected_items'])
        assert accepted != illegal, (name,new,broken)
        outcomes[name]={'accepted':accepted,'opens':len(d['unconnected_items']),
                        'opens_by_net':opens_by_net(d['unconnected_items']),
                        'new_violation_records':[json.loads(s) for s in new.elements()],
                        'prior_partition_splits':broken,'physical_partitions':after,
                        'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
    proof={'baseline_opens':len(before['unconnected_items']), 'prior_partitions':history,
           'prior_pour_partition_splits':prior_splits,
           'baseline_GND_connected_pads':len(history['batch2']['/GND'][0]),
           'baseline_physical_connected_pairs':pairs(history['batch2']), 'outcomes':outcomes}
    (proofdir/'batch3-physical-native.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({k:{x:v[x] for x in ('accepted','opens','new_violation_records','prior_partition_splits')} for k,v in outcomes.items()},indent=2))

if __name__=='__main__': main()
