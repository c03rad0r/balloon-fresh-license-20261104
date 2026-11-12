from pathlib import Path
import pcbnew as p,json,collections
from shapely.geometry import Polygon
from shapely.ops import unary_union
O=Path(__file__).parent
nets={'GND','+3V3','/SPI1_MISO','/SPI2_MOSI'}
def uid(q):return q.m_Uuid.AsString()
def geom(ps):
 def coords(c):return [(v.x/1e6,v.y/1e6) for v in c.CPoints()]
 return unary_union([Polygon(coords(ps.COutline(i)),[coords(ps.CHole(i,j)) for j in range(ps.HoleCount(i))]) for i in range(ps.OutlineCount())])
def component(adj,s):
 seen={s};stack=[s]
 while stack:
  for k in adj[stack.pop()]-seen:seen.add(k);stack.append(k)
 return seen
for label in ['baseline','candidate']:
 b=p.LoadBoard(str(O/label/'board.kicad_pcb'));nodes={};shapes={};gs={};objs={}
 items=[q for f in b.GetFootprints() for q in f.Pads()]+list(b.GetTracks())+[q for q in b.GetDrawings() if q.GetLayerSet().CuStack()]+[q for f in b.GetFootprints() for q in f.GraphicalItems() if q.GetLayerSet().CuStack()]
 for q in items:
  k=uid(q);objs[k]=q
  for l in q.GetLayerSet().CuStack():
   if not b.IsLayerEnabled(l):continue
   key=k+':'+str(l);ps=p.SHAPE_POLY_SET();q.TransformShapeToPolygon(ps,l,0,100,p.ERROR_INSIDE)
   nodes[key]={'uuid':k,'layer':l,'layer_name':b.GetLayerName(l),'net':q.GetNetname(),'type':type(q).__name__,'name':q.GetParentFootprint().GetReference()+'.'+q.GetNumber() if isinstance(q,p.PAD) else k}
   shapes[key]=q.GetEffectiveShape(l);gs[key]=geom(ps)
 for z in b.Zones():
  for l in z.GetLayerSet().CuStack():
   ps=z.GetFilledPolysList(l)
   for i in range(ps.OutlineCount()):
    key=f'{uid(z)}:{l}:poly{i}';shapes[key]=ps.UnitSet(i);gs[key]=geom(shapes[key]);nodes[key]={'uuid':uid(z),'layer':l,'layer_name':b.GetLayerName(l),'net':z.GetNetname(),'type':'polygon','name':key}
 selected=list(nodes);adj={k:set() for k in selected};edges=[]
 for i,a in enumerate(selected):
  for c in selected[i+1:]:
   na,nc=nodes[a],nodes[c]
   if na['net']!=nc['net']:continue
   if na['layer']!=nc['layer']:
    if na['uuid']!=nc['uuid'] or na['type']=='polygon':continue
    q=objs[na['uuid']]
    hit=isinstance(q,p.PCB_VIA) or isinstance(q,p.PAD) and q.GetAttribute()==p.PAD_ATTRIB_PTH
   else:hit=bool(shapes[a].Collide(shapes[c],0))
   if hit:adj[a].add(c);adj[c].add(a);edges.append([a,c])
 results={}
 for name in sorted(set(n['name'] for n in nodes.values() if n['type']=='PAD' and n['net'] in nets)):
  start=next(k for k in selected if nodes[k]['name']==name);seen=component(adj,start)
  results[name]={'nodes':sorted(seen),'pads':sorted(set(nodes[k]['name'] for k in seen if nodes[k]['type']=='PAD')),'size':len(seen)}
 (O/(label+'-geometry.json')).write_text(json.dumps({'nodes':nodes,'edges':edges,'components':results},indent=2))
 print(label,{k:{'pads':v['pads'],'size':v['size']} for k,v in results.items()})
