#!/usr/bin/env python3
"""Read-only, independent native-export contract; explicit failures survive -O."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
P = Path(__file__).resolve().parent

def require(ok, message):
    if not ok: raise ValueError(message)

def check(path):
    root = ET.parse(path).getroot()
    nets = {(n.attrib['ref'], n.attrib['pin']): net.attrib['name'].lstrip('/')
            for net in root.findall('./nets/net') for n in net.findall('node')}
    comps = {c.attrib['ref']: c for c in root.findall('./components/comp')}
    for ref, csb, address, source in [('U3','GND',0x77,'P_INTERNAL_ABS'),('U4','+3V3',0x76,'P_AMBIENT_ABS')]:
        require(ref in comps, f'{ref} missing')
        require(comps[ref].findtext('value') == 'MS5611-01BA03', 'exact suffix')
        require(comps[ref].findtext('footprint') == 'PressureSensor:MS5611-01BA03_TE_Recommended', 'real footprint')
        for pin, net in {'1':'+3V3','2':'+3V3','3':'GND','4':csb,'5':csb,'7':'I2C_SDA','8':'I2C_SCL'}.items():
            require(nets.get((ref,pin)) == net, f'{ref}.{pin} must be {net}')
        require(nets.get((ref,'6'),'').startswith('unconnected'), 'SDO must be NC')
        actual = 0x76 | (0 if nets[ref,'4'] == '+3V3' else 1)
        require(actual == address, 'CSB complement address')
        fields = {f.attrib['name']: f.text for f in comps[ref].findall('./fields/field')}
        require(fields.get('PressureSource') == source, 'pressure source domain')
        require(fields.get('I2CAddress7bit') == hex(address), 'address label')
    for pin, net in [('12','I2C_SDA'),('17','I2C_SCL')]:
        require(nets.get(('U1',pin)) == net, 'S3 pad assignment')
    for ref, net in [('R9','I2C_SDA'),('R10','I2C_SCL')]:
        require(comps[ref].findtext('value') == '4.7k', 'pullup value')
        require(nets[ref,'1'] == '+3V3' and nets[ref,'2'] == net, 'shared pullup')
    for ref in ['C7','C8']:
        require(comps[ref].findtext('value') == '100n', 'local bypass')
        require(nets[ref,'1'] == '+3V3' and nets[ref,'2'] == 'GND', 'bypass nets')
    require(not any('MOTOR' in n.upper() or 'VMOT' in n.upper() for n in nets.values()), 'actuation absent')
    sch = (P/'core.kicad_sch').read_text()
    require('DELTA_P = P_INTERNAL_ABS - P_AMBIENT_ABS' in sch, 'delta domain label')

if __name__ == '__main__':
    check(Path(sys.argv[1]) if len(sys.argv)>1 else P/'core.xml')
    print('PASS dual MS5611: exact pins, complemented addresses, source/delta domains, S3 endpoints, bypass/pullups')
