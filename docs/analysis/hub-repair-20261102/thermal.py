"""Bounded starved-thermal cluster on top of the silk candidate. Never routes."""
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
import pcbnew as k

BASE = Path(__file__).resolve().parent / 'output' / 'after'
BASEPCB = BASE / 'hub_board_v10_lora1280_7of9.kicad_pcb'
BASEPRO = BASE / 'hub_board_v10_lora1280_7of9.kicad_pro'
BASEDRU = BASE / 'hub_board_v10_lora1280_7of9.kicad_dru'
OUT = Path(__file__).resolve().parent / 'thermal'
STEM = 'hub_board_v10_lora1280_7of9'
TARGETS = {'U_LORA1280': '14', 'J_PROG': '1'}
ORIGINAL = '732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561'
SILK = '94038dd0c4608f28181017599cb7b623dcb85d81f619ec66947fdec2406c1155'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def tokens(text):
    return re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]', text)

def parse(toks):
    """Minimal S-expression parse into nested lists, so groups can be normalized."""
    root = []
    stack = [root]
    for t in toks:
        if t == '(':
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif t == ')':
            assert len(stack) > 1, t
            stack.pop()
        else:
            stack[-1].append(t)
    assert stack == [root]
    return root

def normalize(node):
    out = []
    for item in node:
        if isinstance(item, list):
            head = item[0] if item else ''
            if head == 'filled_polygon':
                continue
            if head == 'zone_connect':
                continue
            out.append(normalize(item))
        else:
            out.append(item)
    return out

def canonical(text):
    """Copper geometry and netlist, with refilled polygons and pad zone-connect allowed to differ."""
    return hashlib.sha256(json.dumps(normalize(parse(tokens(text))), separators=(',', ':')).encode()).hexdigest()

def identities(d):
    return Counter(json.dumps((v['type'], v['severity'], v['description'], sorted((i['uuid'], i['description']) for i in v['items']))) for v in d['violations'])

def run(pcb_dir, edit):
    pcb_dir.mkdir(parents=True, exist_ok=True)
    pcb = pcb_dir / (STEM + '.kicad_pcb')
    shutil.copy2(BASEPRO, pcb.with_suffix('.kicad_pro'))
    if BASEDRU.exists():
        shutil.copy2(BASEDRU, pcb.with_suffix('.kicad_dru'))
    for table in BASE.glob('*lib-table'):
        shutil.copy2(table, pcb_dir / table.name)
    b = k.LoadBoard(str(BASEPCB))
    edited = []
    if edit:
        for ref, num in TARGETS.items():
            fp = b.FindFootprintByReference(ref)
            pads = [p for p in fp.Pads() if p.GetNumber() == num]
            assert len(pads) == 1, (ref, num, len(pads))
            pad = pads[0]
            assert pad.GetNetname() == 'GND', (ref, pad.GetNetname())
            pad.SetLocalZoneConnection(k.ZONE_CONNECTION_FULL)
            edited.append(f'{ref}.{num}')
        assert sorted(edited) == ['J_PROG.1', 'U_LORA1280.14']
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)
    assert sha(pcb.with_suffix('.kicad_pro')) == sha(BASEPRO)
    r = subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all', '--exit-code-violations', '-o', str(pcb_dir/'drc.json'), str(pcb)], capture_output=True, text=True)
    assert r.returncode in (0, 5), r.stderr
    (pcb_dir/'command.json').write_text(json.dumps(dict(argv=r.args, exit=r.returncode, stdout=r.stdout, stderr=r.stderr), indent=2)+'\n')
    return json.loads((pcb_dir/'drc.json').read_text()), pcb

def main():
    assert sha(BASEPCB) == SILK
    before, bpcb = run(OUT/'before', False)
    after, apcb = run(OUT/'after', True)
    hb, ha = canonical(bpcb.read_text()), canonical(apcb.read_text())
    assert hb == ha, 'NON-FILL COPPER/NETLIST/OUTLINE/PLACEMENT CHANGED'
    added = identities(after) - identities(before)
    removed = identities(before) - identities(after)
    assert not added, dict(added)
    assert sum(removed.values()) == 2 and all('starved_thermal' in k_ for k_ in removed), dict(removed)
    assert len(after['unconnected_items']) == len(before['unconnected_items']) == 86
    evidence = dict(original_board_sha256=ORIGINAL, silk_candidate_sha256=SILK,
                    thermal_candidate_sha256=sha(apcb),
                    canonical_union_netlist_outline_placement_sha256=dict(before=hb, after=ha),
                    filled_polygons_and_pad_zone_connect_allowed_to_change=True,
                    counts=dict(before=dict(Counter(v['type'] for v in before['violations'])),
                                after=dict(Counter(v['type'] for v in after['violations']))),
                    added=dict(added), removed=dict(removed),
                    unconnected=86,
                    pads=[dict(ref=r, num=n, zone_connect='FULL') for r, n in TARGETS.items()])
    (OUT/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))

if __name__ == '__main__':
    main()
