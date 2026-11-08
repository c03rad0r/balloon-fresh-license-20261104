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

D={l:json.loads((O/l/'drc.json').read_text()) for l in G}
def key(v):return (v['type'],v['severity'],tuple(sorted(i['uuid'] for i in v.get('items',[]))))
a,b=[collections.Counter(key(v) for v in D[l]['violations']) for l in G]
assert a==b
addition=json.loads((O/'addition.json').read_text())
target='0b5d101b-cf4c-4c94-a581-5020ff4b1a7d:2'
track='3785d7c4-b54b-4758-b0dc-3979b462f16c:0'
assert A[target]!=A[track] and B[target]==B[track]
assert len(D['baseline']['unconnected_items'])==39 and len(D['candidate']['unconnected_items'])==38
for ext in ['kicad_pro','kicad_dru']:assert (O/'baseline'/('board.'+ext)).read_bytes()==(O/'candidate'/('board.'+ext)).read_bytes()
r={'retained_nonpolygon_layer_nodes':len(retained),'lost_previously_connected_pairs':len(loss),'target_connected':True,'c10_power_ground_preserved':True,'native_violation_identities_identical':True,'opens_before':39,'opens_after':38,'candidate_sha256':hashlib.sha256((O/'candidate/board.kicad_pcb').read_bytes()).hexdigest()}
(O/'verification.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
