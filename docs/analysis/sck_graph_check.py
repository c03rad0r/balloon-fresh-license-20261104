"""Is the /SPI1_SCK F.Cu 'split' at (29.55, 16.75) a real electrical break?

DRC reports:
  Track [/SPI1_SCK] on F.Cu, length 1.0500 mm || Track [/SPI1_SCK] on F.Cu, length 5.9000 mm

Both are F.Cu and both meet EXACTLY at (29.550, 16.750), so geometrically they touch.
This measures the electrical question directly: build the copper graph of /SPI1_SCK and
report how many connected components exist, and which pads are in which component.

If the graph says one component, the DRC record is a KiCad connectivity artefact (or is
about a different pair entirely) and the open count needs re-reading. If it says two, the
split is real and SPISCK2 introduced it.
"""
import pcbnew as p
import math

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
NET = '/SPI1_SCK'
TOL = 2000          # 2 um: treat endpoints this close as joined


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def key(x, y, layer):
    """Quantise a coordinate so coincident endpoints union reliably."""
    return (round(x / TOL), round(y / TOL), layer)


def main():
    b = p.LoadBoard(BOARD)
    dsu = DSU()
    items = []

    for t in b.GetTracks():
        if t.GetNetname() != NET:
            continue
        if isinstance(t, p.PCB_VIA):
            s = t.GetPosition()
            # a via joins its own F and B endpoints
            kf = key(s.x, s.y, 'F')
            kb = key(s.x, s.y, 'B')
            dsu.union(kf, kb)
            items.append(('VIA', kf, kb))
        else:
            s, e = t.GetStart(), t.GetEnd()
            ln = b.GetLayerName(t.GetLayer())
            dsu.union(key(s.x, s.y, ln), key(e.x, e.y, ln))
            items.append((ln, key(s.x, s.y, ln), key(e.x, e.y, ln)))

    pads = []
    for f in b.GetFootprints():
        for q in f.Pads():
            if q.GetNetname() != NET:
                continue
            c = q.GetPosition()
            pad_layers = [b.GetLayerName(l) for l in (p.F_Cu, p.B_Cu) if q.IsOnLayer(l)]
            pads.append((f.GetReference() + '.' + q.GetNumber(),
                         round(c.x / 1e6, 3), round(c.y / 1e6, 3), pad_layers,
                         [key(c.x, c.y, l) for l in pad_layers]))

    # a pad joins every copper item whose endpoint lies inside it
    for name, px, py, layers, keys in pads:
        for it in items:
            for k in it[1:]:
                if k[2] in layers:
                    # same 2um quantisation, plus one cell each way
                    if abs(k[0] - keys[0][0]) > 40 or abs(k[1] - keys[0][1]) > 40:
                        continue
                    dsu.union(keys[0], k)

    comps = {}
    for k in list(dsu.p):
        comps.setdefault(dsu.find(k), []).append(k)

    print('net %s' % NET)
    print('  copper items: %d' % len(items))
    print('  connected components: %d' % len(comps))
    for i, (root, keys) in enumerate(sorted(comps.items(), key=lambda kv: -len(kv[1]))):
        layers = sorted({k[2] for k in keys})
        print('    component %d: %d nodes, layers %s' % (i, len(keys), layers))

    print('  pads and their component:')
    for name, px, py, layers, keys in pads:
        c = dsu.find(keys[0])
        size = len(comps.get(c, []))
        print('    %-16s (%.3f, %.3f) %-14s -> component of %d nodes'
              % (name, px, py, ','.join(layers), size))

    print('\nverdict: %s' % (
        'ONE component - the F.Cu fragments ARE joined; the DRC record is not an electrical break'
        if len(comps) == 1 else
        '%d components - the net IS split' % len(comps)))


if __name__ == '__main__':
    main()
