"""For every two-face pad in the opens list, decide assembly-land vs REAL gap.

A two-face pad is SMD copper on F.Cu and B.Cu at the same XY with NO drill. Its two faces are
electrically separate in KiCad, so DRC reports them as an unconnected pair unless something joins
them. On this board the wing tabs solder both faces in assembly (WING_TAB_4P / ADR-120 R1), so
that pair is BY DESIGN.

But that is only true if the net actually reaches the pad on at least one face. If NO track or via
touches the pad on ANY face, the pad is isolated and the open is a genuine missing connection,
not an assembly land. This probe separates those two cases by measurement rather than assumption.

Output: for each pad, which faces have copper contact, and the verdict.
"""
import json
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')

import pcbnew as p

UM = 1_000_000.0
BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
DRC = '/tmp/drc17.json'

TOL = 1000        # 1 um contact tolerance


def main():
    b = p.LoadBoard(BOARD)
    with open(DRC) as fh:
        d = json.load(fh)

    # index pads by (ref, number, x, y)
    pads = []
    for f in b.GetFootprints():
        for pad in f.Pads():
            c = pad.GetPosition()
            pads.append({
                'ref': f.GetReference(), 'num': str(pad.GetNumber()),
                'x': c.x, 'y': c.y, 'pad': pad,
                'net': str(pad.GetNetname()),
            })

    def tracks_touching(pad, layer):
        """Net names of tracks/vias whose shape contacts this pad on `layer`."""
        hits = []
        try:
            pshp = pad.GetEffectiveShape(layer)
        except Exception:
            return hits
        for t in b.GetTracks():
            if t.GetLayer() != layer and t.Type() != p.PCB_VIA_T:
                continue
            try:
                if p.SHAPE.Collide(pshp, t.GetEffectiveShape(0), TOL):
                    hits.append(str(t.GetNetname()))
            except Exception:
                pass
        return hits

    # which pads appear in an unconnected record
    seen = {}
    for u in d.get('unconnected_items', []):
        for it in u.get('items', []):
            e = it.get('description', '')
            if not e.startswith('Pad'):
                continue
            pos = it.get('pos') or {}
            if pos.get('x') is None:
                continue
            seen[(round(float(pos['x']) * UM), round(float(pos['y']) * UM))] = e

    print('%-10s %-8s %-16s %-6s %-6s %s' % (
        'REF', 'PIN', 'NET', 'F.Cu', 'B.Cu', 'VERDICT'))
    print('-' * 78)

    # A two-face land on this board is TWO pad objects at the same XY - one on F.Cu, one on
    # B.Cu - not one pad carrying both layers. Group by position before deciding.
    groups = {}
    for pd in pads:
        key = (round(pd['x']), round(pd['y']), pd['ref'], pd['num'])
        groups.setdefault(key, []).append(pd)

    two_face = 0
    real = 0
    for (kx, ky, ref, num), grp in sorted(groups.items()):
        key = (kx, ky)
        if key not in seen:
            continue
        faces = set()
        for pd in grp:
            if pd['pad'].IsOnLayer(p.F_Cu):
                faces.add('F')
            if pd['pad'].IsOnLayer(p.B_Cu):
                faces.add('B')
        drill = max(pd['pad'].GetDrillSize().x for pd in grp)
        if faces != {'F', 'B'} or drill > 0:
            continue      # only two-face undrilled lands matter here
        two_face += 1
        pd = grp[0]
        hf = tracks_touching(pd['pad'], p.F_Cu)
        hb = tracks_touching(pd['pad'], p.B_Cu)
        # ignore hits from other nets - those are shorts, not connections
        hf_same = [n for n in hf if n == pd['net']]
        hb_same = [n for n in hb if n == pd['net']]
        if hf_same or hb_same:
            verdict = 'ASSEMBLY_LAND (net reaches %s)' % (
                'F' if hf_same else 'B')
        else:
            verdict = 'REAL GAP (pad isolated on BOTH faces)'
            real += 1
        print('%-10s %-8s %-16s %-6s %-6s %s' % (
            pd['ref'], pd['num'], pd['net'][:16],
            'yes' if hf_same else '-', 'yes' if hb_same else '-', verdict))

    print()
    print('two-face pads in opens: %d' % two_face)
    print('of those, REAL GAPS (isolated both faces): %d' % real)


if __name__ == '__main__':
    main()
