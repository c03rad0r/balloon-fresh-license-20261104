"""Bounded graphics-only candidate. Run with /usr/bin/python3; never routes."""
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
import pcbnew as k

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / 'output'
STEM = 'hub_board_v10_lora1280_7of9'
SOURCE = ROOT / 'tracker/hardware' / (STEM + '.kicad_pcb')
EXPECTED = '732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561'
TARGETS = {'1faf3492-15b9-4f0b-9396-c5d97f87f506', 'e97516be-ca8a-4061-819e-9b66ff243826'}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def tokens(text):
    return re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]', text)

def canonical_non_target(text):
    # Replace only the exact approved graphic layer token, retaining EVERY other
    # token (including pads, netlist, filled zones, drills, outline and UUIDs).
    graphics = []
    for uid in sorted(TARGETS):
        matches = [m for m in re.finditer(r'\(fp_line\s.*?\(uuid "[^"]+"\)\s*\)', text, re.S) if uid in m.group()]
        assert len(matches) == 1, (uid, len(matches))
        m = matches[0]
        block = m.group()
        assert '(layer "F.SilkS")' in block or '(layer "F.Fab")' in block
        block = block.replace('(layer "F.Fab")', '(layer "F.SilkS")')
        graphics.append(tokens(block))
        text = text[:m.start()] + text[m.end():]
    return hashlib.sha256(json.dumps([tokens(text), graphics], separators=(',', ':')).encode()).hexdigest()

def identities(d):
    return Counter(json.dumps((v['type'], v['severity'], v['description'], sorted((i['uuid'], i['description']) for i in v['items']))) for v in d['violations'])

def main():
    assert sha(SOURCE) == EXPECTED
    reports = {}
    for name in ('before', 'after'):
        directory = OUT / name
        directory.mkdir(parents=True, exist_ok=True)
        pcb = directory / (STEM + '.kicad_pcb')
        for ext in ('.kicad_pro', '.kicad_dru'):
            src = SOURCE.with_suffix(ext)
            if src.exists():
                shutil.copy2(src, pcb.with_suffix(ext))
        for table in SOURCE.parent.glob('*lib-table'):
            shutil.copy2(table, directory / table.name)
        b = k.LoadBoard(str(SOURCE))
        edited = []
        if name == 'after':
            for fp in b.GetFootprints():
                for item in fp.GraphicalItems():
                    if item.m_Uuid.AsString() in TARGETS:
                        assert fp.GetReference() == 'U_LORA1280' and item.GetLayer() == k.F_SilkS
                        item.SetLayer(k.F_Fab)
                        edited.append(item.m_Uuid.AsString())
            assert set(edited) == TARGETS
        k.ZONE_FILLER(b).Fill(b.Zones())
        k.SaveBoard(str(pcb), b)
        assert sha(pcb.with_suffix('.kicad_pro')) == sha(SOURCE.with_suffix('.kicad_pro'))
        run = subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all', '--exit-code-violations', '-o', str(directory/'drc.json'), str(pcb)], capture_output=True, text=True)
        assert run.returncode in (0, 5), run.stderr
        reports[name] = json.loads((directory/'drc.json').read_text())
        (directory/'command.json').write_text(json.dumps(dict(argv=run.args, exit=run.returncode, stdout=run.stdout, stderr=run.stderr), indent=2)+'\n')
    before = OUT/'before'/(STEM+'.kicad_pcb')
    after = OUT/'after'/(STEM+'.kicad_pcb')
    hashes = {name:canonical_non_target((OUT/name/(STEM+'.kicad_pcb')).read_text()) for name in reports}
    assert len(set(hashes.values())) == 1, 'NON-GRAPHIC GEOMETRY CHANGED'
    added = identities(reports['after']) - identities(reports['before'])
    removed = identities(reports['before']) - identities(reports['after'])
    assert not added, added
    assert sum(removed.values()) == 2, removed
    assert len(reports['before']['unconnected_items']) == len(reports['after']['unconnected_items']) == 86
    evidence = dict(source_sha256=sha(SOURCE), project_sha256=sha(SOURCE.with_suffix('.kicad_pro')), canonical_all_tokens_except_two_layers_sha256=hashes, before_sha256=sha(before), after_sha256=sha(after), added=dict(added), removed=dict(removed), counts={name:dict(Counter(v['type'] for v in d['violations'])) for name,d in reports.items()}, unconnected=86, copper_netlist_outline_drill_and_filled_zone_tokens_unchanged=True)
    assert sha(SOURCE) == EXPECTED
    (OUT/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))

if __name__ == '__main__':
    main()
