#!/usr/bin/env python3
"""Negative controls for physical graph and locked geometry, real board fixtures."""
import json
import tempfile
from pathlib import Path
import pcbnew
from physical_partitions import partitions, splits
from check_preservation import objects
ROOT=Path(__file__).resolve().parent
before=partitions(ROOT/'batch2.kicad_pcb')
after=partitions(ROOT/'batch3.kicad_pcb')
assert not splits(before,after)
assert len(after['/BUCK_SW'])==1
assert len(after['/GND'])==1
# Remove physical ground fill without altering pad assignments: must split GND.
b=pcbnew.LoadBoard(str(ROOT/'batch2.kicad_pcb'))
for z in list(b.Zones()):
    if not z.GetIsRuleArea(): z.UnFill()
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/'cut.kicad_pcb'; pcbnew.SaveBoard(str(p),b)
    broken=splits(before,partitions(p))
assert any(x['net']=='/GND' for x in broken)
# Every non-zone original object byte-normalized and preserved; refills may differ.
a=objects(ROOT/'batch2.kicad_pcb'); c=objects(ROOT/'batch3.kicad_pcb')
removed=[x for x in (a-c).elements() if not x.startswith('(zone ')]
added=[x for x in (c-a).elements() if not x.startswith('(zone ')]
assert not removed
assert len(added)==1 and added[0].startswith('(segment ')
# All zone definitions (including board and footprint-local keepouts) immutable;
# filled_polygon children alone may change in native refill.
from check_preservation import ns
def zones(path):
    tree=ns['parse'](path.read_text())
    return [ns['dump']([q for q in x if not (isinstance(q,list) and q and q[0]=='filled_polygon')])
            for x in tree[1:] if isinstance(x,list) and x[0]=='zone']
assert zones(ROOT/'batch2.kicad_pcb')==zones(ROOT/'batch3.kicad_pcb')
report={'ground_fill_removal_negative_control':'PASS: physical GND split detected',
        'unchanged_non_zone_objects':sum(a.values())-sum(v for k,v in a.items() if k.startswith('(zone ')),
        'added_segments':1,'removed_or_changed_non_zone_objects':0,'zone_definitions_unchanged':True,
        'GND_pads_connected':len(after['/GND'][0]),'prior_partition_splits':[]}
(ROOT/'proofs/batch3-controls.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
