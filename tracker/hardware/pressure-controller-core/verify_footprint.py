#!/usr/bin/python3
"""Rebuild isolated no-net coupon; compare native export to pinned pre-repair nets."""
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as k
from test_footprint import load, check, NAME
P=Path(__file__).resolve().parent
E=P/'footprint-evidence'
E.mkdir(exist_ok=True)
BASE='57d654ff'
def netmap(data):
    root=ET.fromstring(data)
    return sorted((n.attrib['ref'],n.attrib['pin'],net.attrib['name']) for net in root.findall('./nets/net') for n in net.findall('node'))
old=subprocess.check_output(['git','show',BASE+':tracker/hardware/pressure-controller-core/core.xml'])
current=(P/'core.xml').read_bytes()
if netmap(old)!=netmap(current): raise ValueError('net assignments changed')
root=ET.fromstring(current)
for ref in ['U3','U4']:
    comp=root.find(f'./components/comp[@ref="{ref}"]')
    if comp.findtext('footprint')!='PressureSensor:'+NAME: raise ValueError('footprint mapping')
b=k.BOARD(); f=load(); check(f); b.Add(f)
f.SetFPID(k.LIB_ID('PressureSensor',NAME)); f.SetReference('U_TEST')
f.SetPosition(k.VECTOR2I(k.FromMM(10),k.FromMM(10)))
for a,z in [((5,5),(15,5)),((15,5),(15,15)),((15,15),(5,15)),((5,15),(5,5))]:
    edge=k.PCB_SHAPE(); edge.SetShape(k.SHAPE_T_SEGMENT); edge.SetLayer(k.Edge_Cuts); edge.SetWidth(k.FromMM(.05))
    edge.SetStart(k.VECTOR2I(*[k.FromMM(x) for x in a])); edge.SetEnd(k.VECTOR2I(*[k.FromMM(x) for x in z])); b.Add(edge)
k.SaveBoard(str(E/'coupon.kicad_pcb'),b)
(E/'coupon.kicad_pro').write_bytes((P/'core.kicad_pro').read_bytes())
(E/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "PressureSensor") (type "KiCad") (uri "${KIPRJMOD}/../PressureSensor.pretty") (options "") (descr "")))\n')
reloaded=k.LoadBoard(str(E/'coupon.kicad_pcb'))
for pad in next(iter(reloaded.GetFootprints())).Pads():
    if pad.GetSolderMaskExpansion(k.F_Mask)!=0 or pad.GetSolderPasteMargin(k.F_Paste)!=k.VECTOR2I(0,0):
        raise ValueError('effective coupon mask/paste is not 1:1')
subprocess.run(['kicad-cli','pcb','drc','--format','json','--severity-all','--exit-code-violations','-o',str(E/'drc.json'),str(E/'coupon.kicad_pcb')],check=True)
subprocess.run(['kicad-cli','pcb','export','svg','--layers','F.Cu,F.Silkscreen,F.Fab,F.Courtyard,Edge.Cuts','--page-size-mode','2','--mode-single','-o',str(E/'coupon.svg'),str(E/'coupon.kicad_pcb')],check=True)
subprocess.run(['rsvg-convert','-w','1400','-o',str(E/'coupon.png'),str(E/'coupon.svg')],check=True)
proof={'baseline':BASE,'unchanged_native_net_endpoints':len(netmap(current)),'mapped_refs':['U3','U4'],'footprint':'PressureSensor:'+NAME,'scope':'isolated no-net coupon only; not controller layout or fab readiness'}
proof['sha256']={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [P/'PressureSensor.pretty'/f'{NAME}.kicad_mod',P/'core.kicad_sch',P/'core.xml',E/'coupon.kicad_pcb',E/'coupon.svg',E/'coupon.png']}
(E/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
