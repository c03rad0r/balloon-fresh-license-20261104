#!/usr/bin/env python3
"""Poison native export without modifying committed artifacts; run with/without -O."""
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
P = Path(__file__).resolve().parent

def run(path, want):
    for opt in ([], ['-O']):
        r = subprocess.run([sys.executable,*opt,str(P/'test_measurement.py'),str(path)],capture_output=True,text=True)
        if (r.returncode == 0) != want:
            raise RuntimeError(r.stdout+r.stderr)

run(P/'core.xml', True)
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp)/'poison.xml'
    for label, ref, pin in [('address','U3','4'),('PS','U4','2'),('SDA','U3','7'),('SCL','U4','8'),('S3','U1','12')]:
        tree = ET.parse(P/'core.xml')
        for net in tree.findall('./nets/net'):
            for node in net.findall('node'):
                if node.attrib['ref']==ref and node.attrib['pin']==pin:
                    net.remove(node)
        tree.write(out)
        run(out,False)
    tree=ET.parse(P/'core.xml')
    field=tree.find("./components/comp[@ref='U3']/fields/field[@name='PressureSource']")
    if field is None: raise RuntimeError('missing source field')
    field.text='P_AMBIENT_ABS'
    tree.write(out); run(out,False)
    out.write_text(''); run(out,False)
    out.unlink(); run(out,False)
print('PASS 8 negative controls and clean export under normal Python and -O')
