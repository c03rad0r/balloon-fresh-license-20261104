import pcbnew

BOARD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
NETS = ['/F33_VSENSE', '/VSCAP', '/EN', '/IO0']

b = pcbnew.LoadBoard(BOARD)
conn = b.GetConnectivity()
b.BuildConnectivity()

MM = 1e6

for netname in NETS:
    print(f'=== {netname}')
    net = None
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        if ni.GetNetname() == netname:
            net = ni
            break
    if net is None:
        print('  no such net')
        continue
    items = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == netname:
                items.append(('pad', f'{fp.GetReference()}.{p.GetNumber()}', p))
    for t in b.GetTracks():
        if t.GetNetname() == netname:
            kind = 'via' if t.GetClass() == 'PCB_VIA' else 'trk'
            items.append((kind, '', t))
    print(f'  {len(items)} copper objects')
    # group by connected island
    islands = {}
    for kind, name, obj in items:
        n = conn.GetConnectedItems(obj, [pcbnew.PCB_TRACE_T, pcbnew.PCB_VIA_T, pcbnew.PCB_PAD_T])
        key = frozenset(id(x) for x in n)
        islands.setdefault(key, []).append((kind, name, obj))
    print(f'  distinct connectivity keys: {len(islands)}')
    for i, (key, members) in enumerate(sorted(islands.items(), key=lambda kv: -len(kv[1]))):
        pads = [m[1] for m in members if m[0] == 'pad']
        print(f'   island {i}: {len(members)} objects, pads={pads[:6]}')
