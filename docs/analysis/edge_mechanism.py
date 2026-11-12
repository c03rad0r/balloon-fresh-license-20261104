"""Why do 16 copper_edge_clearance errors appear on ANY copper-edited pcbnew round-trip?

Established arms (all 0 errors):
  verbatim copy, one save, one save+refill, two saves, three saves
This arm reproduces the 16 WITHOUT adding or removing any copper:
  touch nothing, but write the board through the same path DEADVIA/BRIDGE3 used
and then compares the *design settings* the two files declare, because an edge-clearance
error is evaluated against the board's own edge rule. If the saved file carries a different
edge clearance value, that is the mechanism.

Reports, for the live file and the round-tripped file:
  m_CopperEdgeClearance, and any other clearance-like design settings
  the count of Edge.Cuts segments and their widths
  whether the file text contains the same (setup ...) block
"""
import json
import os
import re
import shutil
import subprocess

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107'
LIVE = os.path.join(ROOT, 'docs/analysis/bulk-route-20261107/latest.kicad_pcb')
WORK = '/home/c08r4d0r/.hermes/cache/scratch/edge-mech'


def drc(board, out):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
                    '--units', 'mm', '--output', out, board],
                   capture_output=True, timeout=1200)
    d = json.load(open(out))
    viol = d.get('violations', [])
    errs = [v for v in viol if v.get('severity') == 'error']
    kinds = {}
    for v in errs:
        kinds[v.get('type')] = kinds.get(v.get('type'), 0) + 1
    return len(d['unconnected_items']), len(viol), len(errs), kinds


def settings(board):
    b = p.LoadBoard(board)
    ds = b.GetDesignSettings()
    out = {}
    for attr in dir(ds):
        if 'learance' in attr and not attr.startswith('__'):
            try:
                out[attr] = getattr(ds, attr) / 1e6
            except Exception:
                pass
    edges = [t for t in b.GetDrawings() if t.GetLayer() == p.Edge_Cuts]
    return out, len(edges)


def main():
    os.makedirs(WORK, exist_ok=True)
    rt = os.path.join(WORK, 'roundtrip.kicad_pcb')
    shutil.copy(LIVE, rt)
    for ext in ('kicad_pro', 'kicad_dru', 'fp-lib-table'):
        s = LIVE.replace('.kicad_pcb', '.' + ext)
        if os.path.exists(s):
            shutil.copy(s, rt.replace('.kicad_pcb', '.' + ext))

    b = p.LoadBoard(rt)
    p.SaveBoard(rt, b)
    del b

    print('=== DRC')
    a = drc(LIVE, os.path.join(WORK, 'live.json'))
    c = drc(rt, os.path.join(WORK, 'rt.json'))
    print('  live        opens=%d viol=%d errors=%d %s' % a)
    print('  roundtrip   opens=%d viol=%d errors=%d %s' % c)

    print('\n=== DESIGN SETTINGS (clearance-like, mm)')
    sa, ea = settings(LIVE)
    sc, ec = settings(rt)
    for k in sorted(set(sa) | set(sc)):
        va, vc = sa.get(k), sc.get(k)
        flag = '' if va == vc else '   <-- DIFFERS'
        print('  %-34s live %-10s roundtrip %-10s%s' % (k, va, vc, flag))
    print('  Edge.Cuts drawing count: live %d  roundtrip %d' % (ea, ec))

    print('\n=== FILE TEXT (setup block)')
    for tag, f in (('live', LIVE), ('roundtrip', rt)):
        txt = open(f, errors='ignore').read()
        m = re.search(r'\(setup\s*\n(.*?)\n\t\)', txt, re.S)
        head = (m.group(1)[:600] if m else 'NO SETUP BLOCK')
        has_edge = 'copper_edge_clearance' in txt
        print('  %s: copper_edge_clearance in text = %s' % (tag, has_edge))
        for ln in head.splitlines():
            if 'clearance' in ln.lower() or 'edge' in ln.lower():
                print('      %s' % ln.strip())

    json.dump({'live': a, 'roundtrip': c, 'settings_live': sa, 'settings_rt': sc},
              open(os.path.join(ROOT, 'docs/analysis/edge-mech.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
