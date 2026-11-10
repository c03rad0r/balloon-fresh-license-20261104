#!/usr/bin/env python3
"""Prove the geometry gate can fail: poison the real board, require refusal."""
import shutil, subprocess, sys, tempfile
from pathlib import Path
import pcbnew as p
import placement as m

def poison(kind, path):
    b = p.LoadBoard(str(m.OUT / 'core-placement.kicad_pcb'))
    f = {x.GetReference(): x for x in b.GetFootprints()}
    if kind == 'short':
        # Copper from one net's land straight onto a DIFFERENT net's land.
        pads = {p.GetNumber(): p for p in f['C1'].Pads() if p.GetNumber()}
        a, c = pads['1'], pads['2']
        assert a.GetNetname() != c.GetNetname()
        t = p.PCB_TRACK(b)
        t.SetStart(a.GetPosition()); t.SetEnd(c.GetPosition())
        t.SetWidth(p.FromMM(0.25)); t.SetLayer(p.F_Cu)
        t.SetNet(a.GetNet())          # net MUST be set before Add
        b.Add(t)
    elif kind == 'overlap':
        f['U4'].SetPosition(f['U3'].GetPosition())
    elif kind == 'crossnet':
        f['U3'].Pads()[0].SetNet(b.FindNet('/GND'))
    elif kind == 'reserved':
        f['U4'].SetPosition(p.VECTOR2I(p.FromMM(60), p.FromMM(40)))
    p.SaveBoard(str(path), b)

def main():
    tmp = Path(tempfile.mkdtemp())
    results = {}
    for kind, expect in [('short', 'DRC'), ('overlap', 'courtyard'), ('crossnet', 'mapping'), ('reserved', 'reservation')]:
        board = tmp / f'{kind}.kicad_pcb'
        poison(kind, board)
        if kind == 'short':
            r = subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json',
                                '-o', str(tmp / 'd.json'), str(board)], capture_output=True, text=True)
            import json
            d = json.loads((tmp / 'd.json').read_text())
            kinds = {v['type'] for v in d['violations']}
            ok = 'shorting_items' in kinds
            results[kind] = f"shorting_items reported: {ok}"
        else:
            try:
                m.validate(p.LoadBoard(str(board)), *m.inputs(m.OUT / 'core.xml'))
                results[kind] = 'NOT REFUSED'
            except ValueError as exc:
                results[kind] = f'refused: {exc}'
        print(f'{kind:10} expected {expect:11} -> {results[kind]}')
    failures = [k for k, v in results.items() if v == 'NOT REFUSED' or v.endswith('False')]
    print('POISON RESULT:', 'FAIL' if failures else 'ALL NEGATIVE CONTROLS TRIPPED')
    return 1 if failures else 0

if __name__ == '__main__':
    sys.exit(main())
