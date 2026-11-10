#!/usr/bin/env python3
"""Independent assertions against KiCad's exported connectivity, not generator nets."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
p=Path(__file__).resolve().parent
root=ET.parse(p/'core.xml').getroot()
nets={}
for net in root.findall('./nets/net'):
    for node in net.findall('node'): nets[node.attrib['ref'],node.attrib['pin']]=net.attrib['name'].lstrip('/')
expected={'1':'GND','2':'+3V3','3':'EN','27':'BOOT','40':'GND','41':'GND','13':'USB_DN_BOUNDARY','14':'USB_DP_BOUNDARY'}
for pin,net in expected.items(): assert nets['U1',pin]==net,(pin,nets.get(('U1',pin)))
for ref,ns in {'R1':('+3V3','EN'),'R2':('+3V3','BOOT'),'C1':('EN','GND'),'C2':('+3V3','GND'),'C3':('+3V3','GND'),'SW1':('EN','GND'),'SW2':('BOOT','GND')}.items():
    for i,n in enumerate(ns,1): assert nets[ref,str(i)]==n
mapping=json.loads((p/'pin-map.json').read_text())['U1']
assert set(mapping)==set(map(str,range(1,42)))
for pin in set(mapping)-set(expected):
    assert nets.get(('U1',pin),'unconnected').startswith('unconnected'),pin
violations=[v for s in json.loads((p/'erc.json').read_text())['sheets'] for v in s['violations']]
assert len(violations)==2 and all(v['type']=='label_dangling' for v in violations),violations
assert mapping['13']['name']=='USB_D-' and mapping['14']['name']=='USB_D+'
print('PASS: all 41 module pins accounted; intended reset/boot/decoupling connectivity; exactly two declared USB boundary ERC findings')
