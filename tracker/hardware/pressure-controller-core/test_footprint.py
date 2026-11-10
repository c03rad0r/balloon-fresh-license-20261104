#!/usr/bin/python3
"""Native read-only geometry gate plus in-memory negative controls; no generator import."""
import hashlib
import json
from pathlib import Path
import pcbnew as k
P = Path(__file__).resolve().parent
NAME = 'MS5611-01BA03_TE_Recommended'
def require(ok, message):
    if not ok:
        raise ValueError(message)
def load():
    fp = k.FootprintLoad(str(P/'PressureSensor.pretty'), NAME)
    require(fp is not None, 'native footprint load')
    return fp
def check(fp):
    pads = list(fp.Pads())
    require(len(pads)==8 and {p.GetNumber() for p in pads}==set('12345678'), 'exact eight pads')
    for p in pads:
        n=int(p.GetNumber())
        x=-1.1 if n<=4 else 1.1
        y=-1.875+(n-1)*1.25 if n<=4 else 1.875-(n-5)*1.25
        require(p.GetPosition()==k.VECTOR2I(k.FromMM(x),k.FromMM(y)), f'pin {n} orientation/centre')
        require(p.GetSize()==k.VECTOR2I(k.FromMM(1.1),k.FromMM(.6)), f'pin {n} land size')
        require(p.GetShape()==k.PAD_SHAPE_RECT, 'rectangular source lands')
        require(p.GetAttribute()==k.PAD_ATTRIB_SMD and p.GetDrillSize()==k.VECTOR2I(0,0), 'no PCB drills')
        require(set(p.GetLayerSet().Seq())=={k.F_Cu,k.F_Mask,k.F_Paste}, 'mask/paste/copper layers')
    ports=[g for g in fp.GraphicalItems() if g.GetShape()==k.SHAPE_T_CIRCLE and g.GetLayer()==k.F_Fab]
    require(len(ports)==2, 'two cap ports')
    require({(g.GetCenter().x,g.GetCenter().y) for g in ports}=={(650000,-1650000),(-650000,1650000)}, 'port orientation')
    require(all(g.GetRadius()==250000 for g in ports), 'port diameter')
    zones=list(fp.Zones())
    require(len(zones)==1 and zones[0].GetIsRuleArea() and zones[0].GetDoNotAllowTracks(), 'routing reservation')
if __name__=='__main__':
    check(load())
    for fault in ('old size','old centres','mirror','rotate','extra pad','missing pad','port drill'):
        f=load(); p=f.FindPadByNumber('1')
        if fault=='old size': p.SetSize(k.VECTOR2I(950000,550000))
        elif fault=='old centres': p.SetPosition(k.VECTOR2I(-1075000,-1875000))
        elif fault=='mirror': p.SetPosition(k.VECTOR2I(1100000,-1875000))
        elif fault=='rotate': p.SetPosition(k.VECTOR2I(1100000,1875000))
        elif fault=='extra pad': f.Add(k.PAD(f))
        elif fault=='missing pad': f.Remove(p)
        else: p.SetDrillSize(k.VECTOR2I(500000,500000))
        try: check(f)
        except ValueError: print('REJECT',fault)
        else: raise RuntimeError('negative control accepted: '+fault)
    old=k.FootprintLoad('/usr/share/kicad/footprints/Package_LGA.pretty','LGA-8_3x5mm_P1.25mm')
    try: check(old)
    except ValueError: print('REJECT installed stock footprint')
    else: raise RuntimeError('stock geometry accepted')
    digest=hashlib.sha256((P/'PressureSensor.pretty'/f'{NAME}.kicad_mod').read_bytes()).hexdigest()
    require(json.loads((P/'library-sha256.json').read_text())['PressureSensor:'+NAME]==digest,'provenance digest')
    print('PASS native geometry and 8 rejection controls; footprint sha256',digest)
