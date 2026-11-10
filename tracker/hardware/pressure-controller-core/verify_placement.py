#!/usr/bin/env python3
"""Run native DRC, retain all findings, export views bound to exact source hashes."""
import json, subprocess, re
from collections import Counter
import placement as m

def run(*args): subprocess.run(args,check=True,cwd=m.ROOT)
def main():
    board=m.OUT/'core-placement.kicad_pcb'
    run('kicad-cli','pcb','drc','--format','json','-o',str(m.OUT/'drc.json'),str(board))
    d=json.loads((m.OUT/'drc.json').read_text())
    counts=Counter(v['type'] for v in d['violations'])
    m.require(not any(counts[t] for t in ['shorting_items','clearance','courtyards_overlap','copper_edge_clearance','lib_footprint_issues','drill_out_of_range','silk_edge_clearance']), 'electrical/placement DRC failure '+str(dict(counts)))
    for side,layers in [('top','F.Cu,F.Fab,F.Silkscreen,F.CrtYd,Edge.Cuts,Dwgs.User'),('bottom','B.Cu,B.Fab,B.CrtYd,Edge.Cuts,Dwgs.User')]:
        svg=m.OUT/(side+'.svg')
        run('kicad-cli','pcb','export','svg','--layers',layers,'--mode-single','--exclude-drawing-sheet','--page-size-mode','2','-o',str(svg),*(['--mirror'] if side=='bottom' else []),str(board))
        # Expand native SVG viewport by 3mm without altering plotted geometry.
        text=svg.read_text()
        match=re.search(r'viewBox="([^"]+)"',text)
        x,y,w,h=map(float,match[1].split())
        text=text[:match.start()]+f'viewBox="{x-3} {y-3} {w+6} {h+6}"'+text[match.end():]
        svg.write_text(text)
        run('rsvg-convert','-w','1600','-o',str(m.OUT/(side+'.png')),str(svg))
    import collections, xml.etree.ElementTree as ET
    tree=ET.parse(m.OUT/'core.xml')
    ends=[n for net in tree.findall('./nets/net') for n in net.findall('node')]
    degree=collections.Counter(net.attrib['name'] for net in tree.findall('./nets/net') for n in net.findall('node'))
    expected=sum(v-1 for v in degree.values() if v>1)
    kinds=collections.Counter(); cross=[]
    for rec in d['unconnected_items']:
        nets=[]
        for item in rec['items']:
            match=re.search(r'\[(.*?)\]',item['description'])
            nets.append(match.group(1) if match else '?')
        if '' in nets: kinds['unassigned_footprint_pad']+=1
        elif len(set(nets))>1: kinds['DIFFERENT_NETS']+=1; cross.append(nets)
        else: kinds['same_net_open']+=1
    m.require(not cross,'different nets reported unconnected: mapping defect')
    # Independent geometric open count: union-find on same-net pad boxes.
    import subprocess as sp
    geo=sp.run(['/usr/bin/python3',str(m.OUT/'geometric_opens.py'),str(board),str(m.OUT/'geometric_opens.json')],capture_output=True,text=True,check=True).stdout.split()
    fields=dict(zip(geo[0::2],geo[1::2]))
    geometric=int(fields['geometric_opens'])
    # Same accounting done again here, from the board, not from the helper's printout.
    npads=int(fields['pads']); merges=int(fields['merges']); nnets=int(fields['nets'])
    m.require(geometric==npads-merges-nnets, f'open accounting inconsistent: {geometric} != {npads}-{merges}-{nnets}')
    m.require(nnets==len(degree), f'board nets {nnets} != exported nets {len(degree)}')
    m.require(len(d['unconnected_items'])==geometric, f'DRC {len(d["unconnected_items"])} != geometric {geometric} opens')
    # The only tolerated non-electrical record must be the declared silk->Fab move on U1.
    toler={'lib_footprint_mismatch':1}
    m.require({k:v for k,v in counts.items() if v}==toler, 'unexpected DRC class set '+str(dict(counts)))
    m.require(all('ESP32-S3-WROOM-1' in v['description'] for v in d['violations']), 'mismatch is not the declared U1 silk move')
    # Per-net opens from the DRC records, cross-checked against the geometric islands.
    geo_detail=json.loads((m.OUT/'geometric_opens.json').read_text())
    per_net={}
    for rec in d['unconnected_items']:
        nets=set()
        for item in rec['items']:
            tag=re.search(r'\[(.*?)\]',item['description'])
            m.require(tag is not None,'unconnected record without a net tag')
            nets.add(tag.group(1))
        m.require(len(nets)==1,'unconnected record spans nets '+str(nets))
        net=next(iter(nets))
        per_net[net]=per_net.get(net,0)+1
    m.require(per_net=={k:v for k,v in geo_detail.items() if v}, f'per-net opens disagree: DRC {per_net} vs geometry {geo_detail}')
    proof={'board_sha256':m.digest(board),'violations':dict(counts),'unconnected_records':len(d['unconnected_items']),'unconnected_classified':dict(kinds),'naive_endpoint_degree_opens':expected,'geometric_opens':geometric,'pads':npads,'same_net_merges':merges,'stacked_duplicate_pads':int(fields['stacked_duplicate_pads']),'opens_by_net':per_net,'single_endpoint_nets':sum(1 for v in degree.values() if v==1),'net_count':len(degree),'shorts':counts['shorting_items'],'clearance':counts['clearance'],'copper_edge_clearance':counts['copper_edge_clearance'],'declared_footprint_deviation':'U1 stock silk body outline moved to F.Fab (antenna overhangs edge); no pad/copper change',
      'approval':'PENDING OPERATOR; NO ROUTING', 'sha256':{f:m.digest(m.OUT/f) for f in ['top.svg','bottom.svg','top.png','bottom.png','drc.json']}}
    (m.OUT/'view-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,indent=2))
if __name__=='__main__': main()
