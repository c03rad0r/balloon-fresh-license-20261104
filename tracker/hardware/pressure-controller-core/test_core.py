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
expected={'1':'GND','2':'+3V3','3':'EN','27':'BOOT','40':'GND','41':'GND','13':'USB_DN','14':'USB_DP','12':'I2C_SDA','17':'I2C_SCL'}
for pin,net in expected.items(): assert nets['U1',pin]==net,(pin,nets.get(('U1',pin)))
for ref,ns in {'R1':('+3V3','EN'),'R2':('+3V3','BOOT'),'C1':('EN','GND'),'C2':('+3V3','GND'),'C3':('+3V3','GND'),'SW1':('EN','GND'),'SW2':('BOOT','GND')}.items():
    for i,n in enumerate(ns,1): assert nets[ref,str(i)]==n
mapping=json.loads((p/'pin-map.json').read_text())['U1']
assert set(mapping)==set(map(str,range(1,42)))
for pin in set(mapping)-set(expected):
    assert nets.get(('U1',pin),'unconnected').startswith('unconnected'),pin
violations=[v for s in json.loads((p/'erc.json').read_text())['sheets'] for v in s['violations']]
assert not violations,violations
for ref,pins in {'J1':{'A1':'GND','A12':'GND','B1':'GND','B12':'GND','S1':'GND','A4':'USB5V','A9':'USB5V','B4':'USB5V','B9':'USB5V','A5':'CC1','B5':'CC2','A7':'USB_DN_CONN','B7':'USB_DN_CONN','A6':'USB_DP_CONN','B6':'USB_DP_CONN'},'U2':{'1':'GND','2':'USB5V','3':'USB5V','4':'GND','5':'BUCK_FB','6':'+3V3','7':'BUCK_SW','9':'GND'},'L1':{'1':'BUCK_SW','2':'+3V3'},'R7':{'1':'+3V3','2':'BUCK_FB'},'R8':{'1':'BUCK_FB','2':'GND'},'R3':{'1':'CC1','2':'GND'},'R4':{'1':'CC2','2':'GND'},'R5':{'1':'USB_DN_CONN','2':'USB_DN'},'R6':{'1':'USB_DP_CONN','2':'USB_DP'},'C4':{'1':'USB5V','2':'GND'},'C5':{'1':'+3V3','2':'GND'}}.items():
    for pin,net in pins.items(): assert nets[ref,pin]==net,(ref,pin)
assert nets.get(('U2','8'),'unconnected').startswith('unconnected')
for pin in ('A8','B8'): assert nets.get(('J1',pin),'unconnected').startswith('unconnected')
assert mapping['13']['name']=='USB_D-' and mapping['14']['name']=='USB_D+'
assert nets['C6','1']=='+3V3' and nets['C6','2']=='GND'
assert not any('MOTOR' in n.upper() or 'VMOT' in n.upper() for n in nets.values())
print('PASS: 41 S3 pins, reset/boot, USB-C, buck/feedback/sense connectivity; zero ERC violations; no motor supply net')
