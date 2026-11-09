import pcbnew

b = pcbnew.LoadBoard('docs/analysis/bulk-route-20261107/work.kicad_pcb')
for fp in b.GetFootprints():
    if fp.GetReference() != 'U1':
        continue
    seen = set()
    for p in fp.Pads():
        n = p.GetNumber()
        if n in seen:
            continue
        seen.add(n)
        if not p.GetNetname():
            print('free pad', n, 'at', round(p.GetPosition().x / 1e6, 2),
                  round(p.GetPosition().y / 1e6, 2))
