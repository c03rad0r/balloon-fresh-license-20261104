from pathlib import Path
import pcbnew as p,json,collections
from shapely.geometry import Polygon
from shapely.ops import unary_union
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch
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
 fig,axes=plt.subplots(1,4,figsize=(20,10))
 colors={'GND':'#4cbb70','+3V3':'#e75cde','/SPI1_MISO':'#ffb02e','/SPI2_MOSI':'#4acbff'}
 for ax,l in zip(axes,[0,4,6,2]):
  ax.set_facecolor('#141a26')
  for k,n in nodes.items():
   if n['layer']!=l:continue
   g=gs[k];polys=[g] if g.geom_type=='Polygon' else list(g.geoms) if g.geom_type=='MultiPolygon' else []
   for poly in polys:
    ax.add_patch(Patch(list(poly.exterior.coords),facecolor=colors.get(n['net'],'#667389'),alpha=.35 if n['type']=='polygon' else .9,edgecolor='none'))
    for ring in poly.interiors:ax.add_patch(Patch(list(ring.coords),facecolor='#141a26',edgecolor='none'))
   if n['type']=='PAD' and 6<g.centroid.x<13 and 33<g.centroid.y<46:ax.text(g.centroid.x,g.centroid.y,n['name'],fontsize=7,color='white')
  ax.set(xlim=(7.8,12.3),ylim=(44.5,39.5),aspect='equal',title=b.GetLayerName(l)+' (top view)',xlabel='mm');ax.grid(alpha=.15)
 fig.suptitle(label+' C10 actual copper after KiCad 9 refill | green GND, magenta +3V3, orange SPI1_MISO, cyan SPI2_MOSI\nDiagnostic only: board retains opens and warnings; inner-layer graphics are not vias',fontsize=14)
 fig.tight_layout();fig.savefig(O/(label+'-copper.png'),dpi=160);plt.close(fig)
