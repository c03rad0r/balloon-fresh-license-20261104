#!/usr/bin/env python3
"""Bounded official-symbol controller sub-block. No PCB or motor generator."""
import json, re, uuid, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parent
LIB = Path('/usr/share/kicad/symbols')
def parse(s):
    tokens = iter(re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]', s))
    def item(t):
        if t != '(': return t
        out=[]
        for t in tokens:
            if t == ')': return out
            out.append(item(t))
        raise ValueError('unclosed')
    return item(next(tokens))
def dump(x): return '('+' '.join(map(dump,x))+')' if isinstance(x,list) else str(x)
def children(x,k): return [v for v in x if isinstance(v,list) and v[0]==k]
def one(x,k): return children(x,k)[0]
def raw(s): return json.loads(s)
def q(s): return json.dumps(s)
def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL,'pressure-core/'+s))
def load(lib,name):
    tree=parse((LIB/(lib+'.kicad_sym')).read_text())
    sym=next(v for v in children(tree,'symbol') if raw(v[1])==name)
    if children(sym,'extends'):
        base=load(lib,raw(one(sym,'extends')[1]))
        for sub in children(base,'symbol'):
            sub[1]=q(raw(sub[1]).replace(raw(base[1]),name,1)); sym.append(sub)
        sym.remove(one(sym,'extends'))
    return sym
def pins(sym):
    return [p for s in children(sym,'symbol') for p in children(s,'pin')]
# USB-C sink and LDO implemented; thermal qualification remains a release blocker.
parts=[('U1','RF_Module','ESP32-S3-WROOM-1',100,90,None,{'1':'GND','2':'+3V3','3':'EN','27':'BOOT','40':'GND','41':'GND','13':'USB_DN','14':'USB_DP'}),
 ('R1','Device','R',40,40,'10k',{'1':'+3V3','2':'EN'}),
 ('R2','Device','R',60,40,'10k',{'1':'+3V3','2':'BOOT'}),
 ('C1','Device','C',40,65,'1u',{'1':'EN','2':'GND'}),
 ('C2','Device','C',40,90,'10u',{'1':'+3V3','2':'GND'}),
 ('C3','Device','C',40,115,'100n',{'1':'+3V3','2':'GND'}),
 ('SW1','Switch','SW_Push',170,40,'RESET',{'1':'EN','2':'GND'}),
 ('SW2','Switch','SW_Push',170,65,'BOOT',{'1':'BOOT','2':'GND'}),
 ('J1','Connector','USB_C_Receptacle_USB2.0_16P',230,65,'GCT USB4105',dict.fromkeys(['S1','A1','A12','B1','B12'],'GND') | dict.fromkeys(['A4','A9','B4','B9'],'USB5V') | {'A5':'CC1','B5':'CC2','A7':'USB_DN_CONN','B7':'USB_DN_CONN','A6':'USB_DP_CONN','B6':'USB_DP_CONN'}),
 ('R3','Device','R',200,110,'5.1k 1%',{'1':'CC1','2':'GND'}),
 ('R4','Device','R',220,110,'5.1k 1%',{'1':'CC2','2':'GND'}),
 ('R5','Device','R',200,140,'22',{'1':'USB_DN_CONN','2':'USB_DN'}),
 ('R6','Device','R',220,140,'22',{'1':'USB_DP_CONN','2':'USB_DP'}),
 ('U2','Regulator_Linear','AP2112K-3.3',65,165,'AP2112K-3.3TRG1',{'1':'USB5V','2':'GND','3':'USB5V','5':'+3V3'}),
 ('C4','Device','C',35,165,'2.2u 10V X7R',{'1':'USB5V','2':'GND'}),
 ('C5','Device','C',100,165,'2.2u 10V X7R',{'1':'+3V3','2':'GND'}),
 ('#FLG01','power','PWR_FLAG',170,90,None,{'1':'USB5V'}),
 ('#FLG02','power','PWR_FLAG',170,115,None,{'1':'GND'})]
footprints={'R':'Resistor_SMD:R_0603_1608Metric','C':'Capacitor_SMD:C_0603_1608Metric','SW_Push':'Button_Switch_SMD:SW_SPST_TL3342'}
rootid=uid('sheet'); libdefs={}; objects=[]; mapping={}; provenance={}
for ref,lib,name,x,y,value,nets in parts:
    x=round(round(x/1.27)*1.27,4); y=round(round(y/1.27)*1.27,4)
    sym=load(lib,name); libid=lib+':'+name
    libdefs[libid]=dump(sym).replace(q(name),q(libid),1)
    fp=footprints.get(name,'')
    if name=='USB_C_Receptacle_USB2.0_16P': fp='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'
    if name in ('ESP32-S3-WROOM-1','AP2112K-3.3'): fp=raw(next(p for p in children(sym,'property') if raw(p[1])=='Footprint')[2])
    if fp:
        fl,fn=fp.split(':'); path=Path('/usr/share/kicad/footprints')/(fl+'.pretty')/(fn+'.kicad_mod')
        pads={raw(p[1]) for p in children(parse(path.read_text()),'pad') if raw(p[1])}
        expected={raw(one(p,'number')[1]) for p in pins(sym)}
        assert pads==expected,(ref,pads,expected)
        provenance[fp]=hashlib.sha256(path.read_bytes()).hexdigest()
    props=' '.join(f'(property {q(k)} {q(v)} (at {x} {y+i*2.54} 0) (effects (font (size 1.27 1.27)){" (hide yes)" if k=="Footprint" else ""}))' for i,(k,v) in enumerate([('Reference',ref),('Value',value or name),('Footprint',fp)]))
    objects.append(f'(symbol (lib_id {q(libid)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)}) {props} (instances (project "core" (path "/{rootid}" (reference {q(ref)}) (unit 1)))))')
    mapping[ref]={}
    for p in pins(sym):
        num=raw(one(p,'number')[1]); pn=raw(one(p,'name')[1]); at=one(p,'at'); px=round(x+float(at[1]),4); py=round(y-float(at[2]),4)
        net=nets.get(num); mapping[ref][num]={'name':pn,'net':net,'footprint':fp}
        if net:
            objects.append(f'(label {q(net)} (at {px} {py} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {uid(ref+num+"label")}))')
        else: objects.append(f'(no_connect (at {px} {py}) (uuid {uid(ref+num+"nc")}))')
    provenance[lib+'.kicad_sym']=hashlib.sha256((LIB/(lib+'.kicad_sym')).read_bytes()).hexdigest()
text=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {rootid}) (paper "A4") (lib_symbols '+ ' '.join(libdefs.values())+') '+' '.join(objects)+')'
(ROOT/'core.kicad_sch').write_text(text+'\n')
(ROOT/'pin-map.json').write_text(json.dumps(mapping,indent=2)+'\n')
(ROOT/'library-sha256.json').write_text(json.dumps(provenance,indent=2)+'\n')
(ROOT/'sym-lib-table').write_text('(sym_lib_table '+ ' '.join(f'(lib (name "{lib}")(type "KiCad")(uri "/usr/share/kicad/symbols/{lib}.kicad_sym")(options "")(descr ""))' for lib in sorted({p[1] for p in parts}))+')\n')
print('Generated official 41-pin module sub-block; all symbol pins match native footprint pads.')
