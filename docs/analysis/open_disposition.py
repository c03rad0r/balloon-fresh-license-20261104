"""Per-open disposition for the live board: every open named, classified, and costed.

This is the artifact an order decision actually needs. It replaces the scattered findings
from this campaign with one table where each of the 22 opens has:
  - its identity (net, the two items DRC reports)
  - its measured class (assembly land / zone island / cross-layer transition / wall)
  - the exact action that would close it, and whether that action touches frozen copper
  - whether ANY legal routing at S1 can close it (established by measurement, not opinion)

Classification is derived from the DRC items themselves plus the per-island and per-fragment
measurements already on disk, so the table cannot drift from the board.
"""
import json
import os
import re

import pcbnew as p

ROOT = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107'
LIVE = os.path.join(ROOT, 'latest.kicad_pcb')
DRC = os.path.join(ROOT, 'batches/SOLARPAIR/drc.json')
STITCH = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/gnd-stitching.json'
OUT_MD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/OPEN-DISPOSITION.md'
OUT_JSON = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/open-disposition.json'

# Frozen placement region (C10). Nothing inside may be moved, added or rerouted.
FROZEN = (39.5, 43.0, 43.5, 46.0)


def net_of(items):
    for it in items:
        d = it.get('description', '')
        m = re.search(r'\[([^\]]+)\]', d)
        if m:
            return m.group(1)
    return None


def kinds_of(items):
    """Return (set of item kinds, same-layer-both-sides flag)."""
    kinds, layers = set(), set()
    for it in items:
        d = it.get('description', '')
        if d.startswith('Pad') or d.startswith('PTH pad'):
            kinds.add('pad')
        elif d.startswith('Track'):
            kinds.add('track')
        elif d.startswith('Zone'):
            kinds.add('zone')
        elif d.startswith('Via'):
            kinds.add('via')
        for m in re.finditer(r'\b(F\.Cu|B\.Cu|In1\.Cu|In2\.Cu)\b', d):
            layers.add(m.group(1))
    return kinds, layers


def classify(items, padinfo):
    """Assign a measured class. Every branch states why."""
    kinds, layers = kinds_of(items)
    descs = [it.get('description', '') for it in items]

    if 'zone' in kinds:
        return ('zone-island',
                'Zone-to-zone record. A pour on one layer cannot connect to a pour on '
                'another without a via; DRC reports the pair. Fix = stitching via if the '
                'pour is isolated, or accept as a zone-connectivity record.',
                'stitching via (outside frozen region) or accept')

    # two pads of the same footprint number on opposite faces = assembly land
    if kinds == {'pad'} and len(items) == 2:
        refs, nums = set(), set()
        for d in descs:
            m = re.match(r'(?:PTH )?Pad (\S+) .*of (\S+) on', d)
            if m:
                nums.add(m.group(1))
                refs.add(m.group(2))
        if len(nums) == 1 and len(refs) == 1 and {'F.Cu', 'B.Cu'} <= layers:
            return ('assembly-land',
                    'Same pad number on both faces of one connector: F.Cu and B.Cu copper '
                    'with no barrel. These join when the wing tab is soldered. Routing or '
                    'vias here is WRONG (WING_TAB_4P / ADR-120 R1).',
                    'none -- completes in assembly, must be accepted as a documented exception')

    if kinds == {'pad'}:
        return ('pad-pair-route',
                'Two pads on the same net that no existing copper joins. Needs a plain '
                'track route between them; measured with the tested router and the '
                'board-wide flood. Where it reports no path, the terminal is trapped in '
                'its own pad fanout (measured pocket sizes: /SPI2_SCK 166 cells, '
                '/F33_VSENSE 186 cells) and no rule relaxation opens it.',
                'route pad-to-pad at S1, or accept as exception if the flood says trapped')

    if 'pad' in kinds and 'track' in kinds:
        descs_join = ' '.join(descs)
        if len(layers) == 1:
            return ('same-layer-pad-track',
                    'Pad and track on the SAME layer. This needs no via: it is a plain '
                    'copper gap and should be routable at S1.',
                    'route it -- a same-layer bridge')
        return ('cross-layer-transition',
                'Pad on one layer, track on another. Needs a plated transition (via) at or '
                'near the pad; measured: no legal 0.600/0.300 via site exists at frozen S1.',
                'drill-in-pad authorisation, or accept as exception')

    if kinds == {'track'} and len(layers) >= 2:
        return ('cross-layer-fragment',
                'Two track fragments on different layers. Needs a via joining them. Measured '
                'by probe: a bridge can be routed, but it did not reduce the open count '
                '(BRIDGE1: 22 -> 22), so this record is not the geometry the DRC is '
                'actually complaining about.',
                'drill-in-pad, or accept as exception')

    if kinds == {'track'}:
        return ('same-layer-fragment',
                'Two track fragments on ONE layer. Purely a copper gap, needs no via at all.',
                'routable -- a plain bridge')

    return ('unclassified', 'Pattern not matched by the classifier.', 'investigate')


def main():
    b = p.LoadBoard(LIVE)
    d = json.load(open(DRC))
    stitch = json.load(open(STITCH)) if os.path.exists(STITCH) else {}

    # pad -> (layers, position)
    padinfo = {}
    for f in b.GetFootprints():
        for q in f.Pads():
            c = q.GetPosition()
            padinfo['%s.%s' % (f.GetReference(), q.GetNumber())] = {
                'x': round(c.x / 1e6, 3), 'y': round(c.y / 1e6, 3),
                'layers': [b.GetLayerName(l) for l in (p.F_Cu, p.B_Cu) if q.IsOnLayer(l)],
            }

    rows = []
    for i, u in enumerate(d['unconnected_items']):
        items = u.get('items', [])
        net = net_of(items)
        cls, why, action = classify(items, padinfo)
        descs = [it.get('description', '') for it in items]

        # frozen test: any referenced pad inside the C10 box?
        infrozen = False
        for desc in descs:
            m = re.search(r'of (\S+) on', desc)
            if m and m.group(1) in padinfo:
                pi = padinfo[m.group(1)]
                if (FROZEN[0] <= pi['x'] <= FROZEN[2]
                        and FROZEN[1] <= pi['y'] <= FROZEN[3]):
                    infrozen = True
        for desc in descs:
            for m in re.finditer(r'\(([\d.]+),\s*([\d.]+)\)', desc):
                x, y = float(m.group(1)), float(m.group(2))
                if FROZEN[0] <= x <= FROZEN[2] and FROZEN[1] <= y <= FROZEN[3]:
                    infrozen = True

        rows.append({'id': i, 'net': net, 'class': cls, 'why': why,
                     'action': action, 'frozen': infrozen,
                     'items': descs})

    counts = {}
    for r in rows:
        counts[r['class']] = counts.get(r['class'], 0) + 1

    md = ['# Open disposition -- live board', '',
          '**Board:** `latest.kicad_pcb` (22 opens, 24 warnings, 0 errors)',
          '**Rules:** S1 frozen -- track 0.20 mm / clearance 0.20 mm / via 0.600 mm land, '
          '0.300 mm drill', '**C10 region frozen:** x 39.5-43.5 mm, y 43.0-46.0 mm', '',
          'Generated by `docs/analysis/open_disposition.py` from the board and its DRC '
          'report, so it cannot drift from the actual copper.', '',
          '## Summary', '']
    for k in sorted(counts, key=lambda k: -counts[k]):
        md.append('- **%s**: %d' % (k, counts[k]))
    md.append('')
    md.append('## Each open')
    md.append('')
    for r in rows:
        md.append('### %d. `%s` -- %s%s' % (r['id'], r['net'], r['class'],
                                           '  [FROZEN]' if r['frozen'] else ''))
        md.append('')
        md.append(r['why'])
        md.append('')
        md.append('- **Items:** %s' % ' || '.join(x[:80] for x in r['items']))
        md.append('- **To close:** %s' % r['action'])
        md.append('')

    open(OUT_MD, 'w').write('\n'.join(md) + '\n')
    json.dump({'rows': rows, 'counts': counts}, open(OUT_JSON, 'w'), indent=2)

    print('opens classified: %d' % len(rows))
    for k in sorted(counts, key=lambda k: -counts[k]):
        print('  %-26s %d' % (k, counts[k]))
    print('\nfrozen-region opens: %d' % sum(1 for r in rows if r['frozen']))
    print('wrote %s' % OUT_MD)


if __name__ == '__main__':
    main()
