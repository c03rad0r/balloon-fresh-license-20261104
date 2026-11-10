#!/usr/bin/env python3
"""Exported BOM + conditional engineering arithmetic; not a hardware qualification."""
import math
import xml.etree.ElementTree as ET
from pathlib import Path
p=Path(__file__).resolve().parent
r=ET.parse(p/'core.xml').getroot()
c={x.attrib['ref']:x for x in r.findall('./components/comp')}
def check(ok,why):
    if not ok: raise ValueError(why)
check(c['U2'].findtext('value')=='TPS62160DSGR','1A WSON buck required')
check('3.3u' in c['L1'].findtext('value'),'3.3uH required')
check(c['R7'].findtext('value')=='100k 0.1%','feedback top')
check(c['R8'].findtext('value')=='32k 0.1%','feedback bottom')
check('22u' in c['C4'].findtext('value'),'input capacitance')
check(all('22u' in c[x].findtext('value','') for x in ('C5','C6')),'output capacitance')
v=0.8*(1+100/32)
check(abs(v-3.3)<1e-9,'feedback equation')
check(3 <= 4.75 <= 5.5 <= 17,'input within recommended range')
# Explicit engineering envelope, NOT guaranteed min frequency or bias curve.
lmin=3.3e-6*0.8*0.7
f_floor=1.5e6
di=v*(1-v/5.5)/(lmin*f_floor)
peak=1+di/2
rms=math.sqrt(1+di*di/12)
check(peak*1.2<12.2,'inductor saturation margin (25C typical rating)')
check(rms<6,'inductor RMS 20C-rise reference')
# Reference-board thermal budget; actual PCB requires measurements.
pallowed=(125-60)/61.8
check(pallowed>1,'WSON reference thermal budget')
# Acceptance requirements, not assumed typical efficiencies.
eta_accept=0.75
iin=3.3/(4.75*eta_accept)
check(iin<1.5,'external 1.5A source requirement')
print(f'PASS conditional arithmetic: Vout={v:.3f}V ripple={di:.3f}A peak={peak:.3f}A RMS={rms:.3f}A; IC loss budget @60C={pallowed:.3f}W; input at 75% acceptance={iin:.3f}A')
