from pathlib import Path
import json,collections,hashlib,re
O=Path(__file__).parent
G={l:json.loads((O/(l+'-geometry.json')).read_text()) for l in ['baseline','candidate']}
def parts(g):
 adj={k:set() for k in g['nodes']}
 for a,b in g['edges']:adj[a].add(b);adj[b].add(a)
 c={}
 for k in adj:
  if k in c:continue
  stack=[k];c[k]=k
  while stack:
   for j in adj[stack.pop()]:
    if j not in c:c[j]=k;stack.append(j)
 return c
A,B=map(parts,G.values()); retained=[k for k in A if G['baseline']['nodes'][k]['type']!='polygon']
assert all(k in B for k in retained)
loss=[(a,b) for i,a in enumerate(retained) for b in retained[i+1:] if A[a]==A[b] and B[a]!=B[b]]
assert not loss
assert 'U7.2' in G['candidate']['components']['C10.2']['pads']
assert 'U1.2' in G['candidate']['components']['C10.1']['pads']
def blocks(text):
 depth=0;ins=False;esc=False;start=0;out=[]
 for i,c in enumerate(text):
  if ins:
   if esc:esc=False
   elif c=='\\':esc=True
   elif c=='"':ins=False
  elif c=='"':ins=True
  elif c=='(': 
   depth+=1
   if depth==2:start=i
  elif c==')':
   if depth==2:out.append(text[start:i+1])
   depth-=1
 return out
a=blocks((O/'baseline/board.kicad_pcb').read_text());b=blocks((O/'candidate/board.kicad_pcb').read_text())
assert len(a)==len(b)
changed=[(x,y) for x,y in zip(a,b) if x!=y]
assert len(changed)==1
x,y=changed[0];assert '(property "Reference" "C10"' in x
# Exact text-only delta, including zone fill and every other object byte-for-byte unchanged.
assert x.replace('(at 1.3 -0.85 90)','(at 1.52 -0.85 90)',1)==y
D={l:json.loads((O/l/'drc.json').read_text()) for l in G}
def key(v):return (v['type'],v['severity'],tuple(sorted(i['uuid'] for i in v.get('items',[]))))
r={'retained_nonpolygon_layer_nodes':len(retained),'lost_connections':len(loss),'ground_U7_2':True,'power_U1_2':True,'only_changed_object':'C10 Reference y 41.42 -> 41.20 mm','drc':{}}
for sec in ['violations','unconnected_items']:
 a,b=[collections.Counter(key(v) for v in D[l][sec]) for l in G]
 r['drc'][sec]={'before':sum(a.values()),'after':sum(b.values()),'added':list((b-a).elements()),'removed':list((a-b).elements())}
assert not r['drc']['violations']['added']
assert len(r['drc']['violations']['removed'])==1 and r['drc']['violations']['removed'][0][0]=='silk_overlap'
assert r['drc']['unconnected_items']['before']==r['drc']['unconnected_items']['after']==39
assert G['baseline']['nodes']==G['candidate']['nodes']
assert {tuple(e) for e in G['baseline']['edges']}=={tuple(e) for e in G['candidate']['edges']}
r['ratsnest_note']='Native spanning-forest anchors may change; full native-geometry node/edge sets are identical.'
r['hashes']={str(f.relative_to(O)):hashlib.sha256(f.read_bytes()).hexdigest() for l in G for f in (O/l).glob('*.kicad_*') if f.suffix!='.kicad_prl'}
for ext in ['kicad_pro','kicad_dru']:assert (O/'baseline'/('board.'+ext)).read_bytes()==(O/'candidate'/('board.'+ext)).read_bytes()
(O/'verification.json').write_text(json.dumps(r,indent=2)); print(json.dumps(r,indent=2))
