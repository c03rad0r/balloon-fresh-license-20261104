#!/usr/bin/env python3
"""Prove additive-pour batches cannot break prior copper connections.
Compare normalized native serialization of every pre-existing top-level object,
including filled polygons, footprints (pads/net/pose/keepouts), setup, nets and outline.
Only NEW zones may be added; no old object may disappear or change.
"""
import ast,collections,json,re,tempfile
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parent
m=ast.parse((ROOT.parent/'generate.py').read_text())
ns={'re':re,'json':json}
exec(compile(ast.Module(body=[n for n in m.body if isinstance(n,ast.FunctionDef) and n.name in {'parse','dump','children','raw'}],type_ignores=[]),'helpers','exec'),ns)
def objects(path):
    b=pcbnew.LoadBoard(str(path))
    with tempfile.TemporaryDirectory() as t:
        f=Path(t)/'normalized.kicad_pcb';pcbnew.SaveBoard(str(f),b)
        tree=ns['parse'](f.read_text())
    return collections.Counter(ns['dump'](x) for x in tree[1:] if isinstance(x,list))
result=[]
for before,after in [('batch0','batch1'),('batch1','batch2')]:
    a,b=objects(ROOT/(before+'.kicad_pcb')),objects(ROOT/(after+'.kicad_pcb'))
    removed=list((a-b).elements()); added=list((b-a).elements())
    assert not removed, f'Existing objects changed: {removed[:1]}'
    assert len(added)==1 and added[0].startswith('(zone ')
    result.append({'before':before,'after':after,'unchanged_existing_objects':sum(a.values()),'added_zones':1,'removed_or_modified_existing_objects':0,'previously_connected_pairs_broken':0,'proof':'All pre-existing copper including filled polygons preserved exactly; additive copper cannot disconnect pairs.'})
(ROOT/'proofs/preservation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
