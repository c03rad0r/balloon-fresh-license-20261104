#!/usr/bin/env python3
"""Negative controls for physical graph and locked geometry, real board fixtures."""
import json
import subprocess
import sys
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
# VIA-BRIDGE NEGATIVE CONTROL (2026-11-11). The graph now models a through-via as a barrel
# bridging its own net across layers. That must be LOAD-BEARING: removing the barrel from an I2C
# net on the routed candidate must split that net, otherwise the bridge is decorative and a
# broken via would still read as connected.
VIA_BOARD=ROOT/'route.kicad_pcb'
vb=partitions(VIA_BOARD)
vias=[t for t in pcbnew.LoadBoard(str(VIA_BOARD)).GetTracks() if isinstance(t,pcbnew.PCB_VIA)]
assert vias, 'via control needs a board that has vias'
victim_net=vias[0].GetNetname()
with tempfile.TemporaryDirectory() as tmp:
    # The vault removal runs in a SEPARATE PROCESS. PCB_TRACK::Remove() invalidates the SWIG
    # wrappers for the owning BOARD (the B59 defect recorded in route_v10_astar.py); in-process
    # it left a dangling board and segfaulted the run. A subprocess is the only version that
    # cannot corrupt the graph objects this test still needs.
    p=Path(tmp)/'novia.kicad_pcb'
    # This subprocess does EXACTLY ONE thing after the removal: save. Any further pcbnew call in
    # the same process raises "'SwigPyObject' object has no attribute" -- Remove() corrupts
    # process-global pcbnew state, so verification of the result belongs to the parent.
    subprocess.run([sys.executable,'-c',(
        "import pcbnew,sys\n"
        "b=pcbnew.LoadBoard(sys.argv[1])\n"
        "net=sys.argv[3]\n"
        "for t in [t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()==net]:\n"
        "    b.Remove(t)\n"
        "pcbnew.SaveBoard(sys.argv[2],b)\n"),
        str(VIA_BOARD), str(p), victim_net], check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    via_cut=partitions(p)
    # PROVE the removal actually happened, in the parent (clean pcbnew state): a control whose
    # precondition silently failed would pass by testing an unmodified board.
    remaining=[t for t in pcbnew.LoadBoard(str(p)).GetTracks()
               if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()==victim_net]
    assert not remaining, f'via removal precondition failed: {len(remaining)} {victim_net} vias remain'
    via_broken=splits(vb,via_cut)
assert any(x['net']==victim_net for x in via_broken), \
    f'via barrel removal did not split {victim_net} -- the via bridge is not load-bearing'
# And the UNMODIFIED candidate must show no split against itself (control is not always-red).
assert not splits(vb,vb)

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
