#!/usr/bin/env python3
"""Native, unrouted core candidate. Connectivity ONLY from fresh schematic XML."""
import hashlib, json, re, subprocess, uuid
from pathlib import Path
import xml.etree.ElementTree as ET
import pcbnew as pcb
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'placement'
# Coordinates in mm, north edge y=0. No motor components invented.
SITES = {
'U1':(28,6.75,0), 'J1':(2.6,28,270),
'C2':(16,2.0,0), 'C3':(16,4,0), 'R1':(13,6,0), 'C1':(16,6,0),
'R2':(40,18,0), 'SW1':(7,12,0), 'SW2':(42,25,0),
'R3':(9.5,25,90), 'R4':(9.5,29,90), 'R5':(16,16,0), 'R6':(16,18,0),
'U2':(13,43,0), 'C4':(9.7,41.27,90), 'L1':(18.25,42.75,0),
'C5':(23.6,41.3,90), 'C6':(23.6,46.5,90), 'R7':(11,48.5,90), 'R8':(13.5,51,0),
'U3':(57,10,0), 'U4':(69,10,0), 'C7':(53.5,9.4,90), 'C8':(65.5,9.4,90),
'R9':(49,20,0), 'R10':(49,22,0)}
def require(ok, message):
    if not ok: raise ValueError(message)
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inputs(xml):
    tree=ET.parse(xml)
    comps={c.attrib['ref']:c for c in tree.findall('./components/comp')}
    endpoints={}
    for net in tree.findall('./nets/net'):
        for node in net.findall('node'):
            key=(node.attrib['ref'],node.attrib['pin'])
            require(key not in endpoints, 'duplicate exported endpoint')
            endpoints[key]=net.attrib['name']
    require(len(endpoints)==125, f'expected 125 endpoints, got {len(endpoints)}')
    require(set(comps)==set(SITES), 'component references differ from placement')
    return comps,endpoints

def validate(board, comps, endpoints):
    fps=list(board.GetFootprints()); refs=[f.GetReference() for f in fps]
    require(len(refs)==len(set(refs)) and set(refs)==set(comps), 'duplicate/missing reference')
    actual={}
    for f in fps:
        ref=f.GetReference()
        require(f.GetFPID().GetUniStringLibId()==comps[ref].findtext('footprint'), 'footprint ID mismatch '+ref)
        for pad in f.Pads():
            num=pad.GetNumber()
            if not num: continue
            key=(ref,num); net=pad.GetNetname()
            require(key in endpoints and endpoints[key]==net, 'pad mapping mismatch '+str(key))
            actual[key]=net
    require(actual==endpoints, 'missing endpoint')
    # Individual transformed pad boxes, not max-size envelope across a module.
    for i,f in enumerate(fps):
        for other in fps[i+1:]:
            for a in f.Pads():
                if not a.GetNumber(): continue
                for b in other.Pads():
                    if not b.GetNumber(): continue
                    require(not a.GetBoundingBox().Intersects(b.GetBoundingBox()), 'pad overlap '+f.GetReference()+' '+other.GetReference())
    require(len(list(board.GetTracks()))==0,'candidate must remain unrouted')
    # Courtyards, not guessed component sizes. Antenna courtyard may overhang edge.
    boxes={}
    for f in fps:
        gs=[g.GetBoundingBox() for g in f.GraphicalItems() if g.GetLayer()==pcb.F_CrtYd]
        require(bool(gs),'missing courtyard '+f.GetReference())
        boxes[f.GetReference()]=(min(g.GetLeft() for g in gs)/1e6,min(g.GetTop() for g in gs)/1e6,max(g.GetRight() for g in gs)/1e6,max(g.GetBottom() for g in gs)/1e6)
    from shapely.geometry import LineString, box as rect
    from shapely.ops import polygonize, unary_union
    polygons={}
    for f in fps:
        lines=[]
        for g in f.GraphicalItems():
            if g.GetLayer()!=pcb.F_CrtYd: continue
            if g.GetShapeStr()=='Rect':
                a,b=g.GetStart(),g.GetEnd(); polygons[f.GetReference()]=rect(a.x/1e6,a.y/1e6,b.x/1e6,b.y/1e6)
            else:
                require(g.GetShapeStr()=='Line','unsupported courtyard shape')
                a,b=g.GetStart(),g.GetEnd(); lines.append(LineString([(a.x/1e6,a.y/1e6),(b.x/1e6,b.y/1e6)]))
        if lines: polygons[f.GetReference()]=unary_union(list(polygonize(lines)))
        require(not polygons[f.GetReference()].is_empty,'empty courtyard polygon')
    for ref,poly in polygons.items():
        require(poly.intersection(rect(48,34,78,58)).area==0, 'motor reservation occupied '+ref)
        for other,b in polygons.items():
            if ref<other: require(poly.intersection(b).area<1e-8, 'courtyard overlap '+ref+' '+other)
    u1=next(f for f in fps if f.GetReference()=='U1')
    require(abs(u1.GetPosition().y/1e6-6.75)<1e-6 and u1.GetOrientationDegrees()==0,'antenna edge datum')
    # Stock courtyard bar above the module = manufacturer antenna keepout (48 x 21 mm,
    # 21 mm > Espressif's 15 mm enclosure guidance). Nothing may sit in it.
    keepout=rect(4,-21.025,52,-6.75)
    for ref,poly in polygons.items():
        require(poly.intersection(keepout).area==0 or ref=='U1', 'antenna keepout occupied '+ref)
    # Connector shell must protrude past the west edge for plug access, not sit inboard.
    require(polygons['J1'].bounds[0]<-0.5 and polygons['J1'].bounds[2]<8, 'USB shell datum')
    # Pad-centre distances for the TI section 11 loop; routing is still owed, so report only.
    def pad(ref,num,n=0):
        return [p for p in next(f for f in fps if f.GetReference()==ref).Pads() if p.GetNumber()==num][n]
    def gap(a,b):
        return round((a.GetPosition()-b.GetPosition()).EuclideanNorm()/1e6,2)
    measurements={
        'CIN_to_VIN_mm':gap(pad('C4','1'),pad('U2','2')),
        'CIN_to_PGND_mm':gap(pad('C4','2'),pad('U2','1')),
        'SW_to_L_mm':gap(pad('U2','7'),pad('L1','1')),
        'L_to_COUT_mm':gap(pad('L1','2'),pad('C5','1')),
        'COUT_to_VOS_mm':gap(pad('C5','1'),pad('U2','6')),
        'FB_divider_to_FB_mm':gap(pad('R7','2'),pad('U2','5')),
        'sensor_to_inductor_mm':gap(pad('U3','1'),pad('L1','2')),
        'sensor_to_S3shield_mm':gap(pad('U3','1'),pad('U1','41'))}
    return {'references':len(refs),'unique_endpoints':len(actual),'tracks':0,'courtyard_overlaps':0,'pad_overlaps':0,'power_loop_mm':measurements,'antenna_keepout_mm':[4,-21.025,52,-6.75]}

def build(xml):
    comps,endpoints=inputs(xml); board=pcb.BOARD(); board.SetCopperLayerCount(2)
    nets={}
    for i,name in enumerate(sorted(set(endpoints.values())),1):
        n=pcb.NETINFO_ITEM(board,name,i); board.Add(n); nets[name]=n
    pinned=json.loads((ROOT/'library-sha256.json').read_text())
    for ref,c in sorted(comps.items()):
        fid=c.findtext('footprint'); lib,name=fid.split(':')
        directory=(ROOT if lib=='PressureSensor' else Path('/usr/share/kicad/footprints'))/(lib+'.pretty')
        require(digest(directory/(name+'.kicad_mod'))==pinned[fid], 'qualified footprint hash drift '+fid)
        f=pcb.FootprintLoad(str(directory),name); require(f is not None,'native load failed '+fid)
        f.SetFPID(pcb.LIB_ID(lib,name)); f.SetReference(ref); f.SetValue(c.findtext('value'))
        board.Add(f)
        for pad in f.Pads():
            if pad.GetNumber(): pad.SetNet(nets[endpoints[(ref,pad.GetNumber())]])
        x,y,a=SITES[ref]; f.SetOrientationDegrees(a); f.SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)))
        # Assembly names on Fab; no misleading silk collision suppression.
        f.Value().SetVisible(False); f.Reference().SetLayer(pcb.F_Fab)
        # U1 antenna sits over the edge by design; its stock silk outline would be
        # clipped, so the body outline lives on Fab (lossless, rules 23/26).
        if ref=='U1':
            for g in f.GraphicalItems():
                if g.GetLayer()==pcb.F_SilkS: g.SetLayer(pcb.F_Fab)
    shape=pcb.PCB_SHAPE(); shape.SetShape(pcb.SHAPE_T_RECT); shape.SetLayer(pcb.Edge_Cuts)
    shape.SetStart(pcb.VECTOR2I(0,0)); shape.SetEnd(pcb.VECTOR2I(pcb.FromMM(80),pcb.FromMM(60))); shape.SetWidth(pcb.FromMM(.05)); board.Add(shape)
    # Physical reservation, both copper layers: no tracks, vias, pours or parts.
    z=pcb.ZONE(board); z.SetIsRuleArea(True); z.SetLayerSet(pcb.LSET.AllCuMask())
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowFootprints(True)
    poly=z.Outline(); poly.NewOutline()
    for x,y in [(48,34),(78,34),(78,58),(48,58)]: poly.Append(pcb.FromMM(x),pcb.FromMM(y))
    board.Add(z)
    for text,x,y,size in [('INCOMPLETE CONTROLLER - NOT FAB READY',40,57,1),('RESERVED MOTOR / PROTECTION',63,42,.85),('NO ACTUATION CIRCUIT',63,45,.85),('INTERNAL',57,5,.8),('AMBIENT',69,5,.8)]:
        t=pcb.PCB_TEXT(board); t.SetText(text); t.SetLayer(pcb.Dwgs_User); t.SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))); t.SetTextSize(pcb.VECTOR2I(pcb.FromMM(size),pcb.FromMM(size))); t.SetTextThickness(pcb.FromMM(.12)); board.Add(t)
    validate(board,comps,endpoints)
    return board

def main():
    OUT.mkdir(exist_ok=True)
    subprocess.run(['kicad-cli','sch','erc','--format','json','--exit-code-violations','-o',str(OUT/'erc.json'),str(ROOT/'core.kicad_sch')],check=True)
    xml=OUT/'core.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(ROOT/'core.kicad_sch')],check=True)
    # The exporter stamps wall-clock time; that is not an input to placement.
    xml.write_text(re.sub(r'<date>[^<]*</date>','<date>NORMALISED</date>',xml.read_text()))
    board=build(xml); path=OUT/'core-placement.kicad_pcb'; pcb.SaveBoard(str(path),board)
    # Native constructors create random UUIDs; normalize only UUID identity, never geometry.
    # Load only parser function definitions; generate.py has top-level schematic writes.
    import ast
    module=ast.parse((ROOT/'generate.py').read_text())
    helpers=ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in {'parse','dump','children','raw'}],type_ignores=[])
    ns={'re':re,'json':json}; exec(compile(helpers,'parser-helpers','exec'),ns)
    parse,dump,children,raw=(ns[k] for k in ('parse','dump','children','raw'))
    tree=parse(path.read_text())
    def canonical(node):
        if not isinstance(node,list): return
        for child in node: canonical(child)
        unordered={'pad','fp_line','fp_rect','fp_circle','fp_arc','fp_text','property','zone','gr_text','gr_line','gr_rect'}
        for kind in unordered:
            indices=[i for i,v in enumerate(node) if isinstance(v,list) and v[0]==kind]
            ordered=sorted((node[i] for i in indices),key=lambda v: re.sub(r'\(uuid [^)]*\)','',dump(v)))
            for i,v in zip(indices,ordered): node[i]=v
    canonical(tree)
    fps=children(tree,'footprint')
    for fp in fps: tree.remove(fp)
    tree.extend(sorted(fps,key=lambda fp: raw(next(v for v in children(fp,'property') if raw(v[1])=='Reference')[2])))
    text=dump(tree); count=0
    def stable(m):
        nonlocal count
        count+=1
        return '(uuid "'+str(uuid.uuid5(uuid.NAMESPACE_URL,'pressure-placement/'+str(count)))+'")'
    text=re.sub(r'\(uuid\s+"?[-0-9a-f]+"?\)',stable,text); path.write_text(text)
    pro_path=OUT/'core-placement.kicad_pro'
    pro=json.loads((ROOT/'core.kicad_pro').read_text())
    # Documented fab floor, not a relaxed measurement: 0.20 mm is JLCPCB's standard
    # minimum and the stock S3/WSON thermal lands are 0.20/0.25 mm. Board defaults say 0.30.
    pro['board']['design_settings'].setdefault('rules',{})['min_through_hole_diameter']=0.2
    pro_path.write_text(json.dumps(pro,indent=2)+'\n')
    proof=validate(pcb.LoadBoard(str(path)),*inputs(xml))
    proof['sha256']={f:digest(ROOT/f) for f in ['core.kicad_sch','library-sha256.json','placement.py','placement/core.xml','placement/core-placement.kicad_pcb']}
    (OUT/'mapping-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,indent=2))
if __name__=='__main__': main()
