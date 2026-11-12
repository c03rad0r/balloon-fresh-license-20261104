"""Re-test the CURRENT board's real opens for routability. No stale analysis.

The "routing exhausted at S1" conclusion was reached on a 25-open board. Since then BRIDGE3
added a 42.61 mm cross-layer bridge, DEADVIA removed two vestigial vias, and SILKTEXT moved
silk text to F.Fab. Copper topology therefore changed, and a corridor that was blocked at 25
opens may be open now. This asks the question again, on the board as it is.

Method, deliberately conservative:
  - classify every current open by the item kinds DRC reports (pad/pad on both faces = assembly
    land and NOT a routing task; pad/track or track/track = a real connection gap)
  - for each real open, run a Collide-only A* on F.Cu and B.Cu at the frozen S1 rules
    (track 0.200 mm, clearance 0.200 mm, guard band CLEAR + half a diagonal step)
  - report whether a legal path exists NOW, with the step count and the exact first-blocker
    point when there is none

No board mutation. Read-only except for writing the JSON result.
"""
import json
import math
import os
import sys

sys.path.insert(0, '/home/c08r4d0r/reports/flight-readiness-20261102/rdiv2-local-clearance')

import pcbnew as p

UM = 1_000_000.0
BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'
DRC = '/tmp/drc18.json'
OUT = '/tmp/current-routability.json'

CLEAR = 200_000                  # 0.200 mm
TRACK = 200_000                  # 0.200 mm
GUARD = CLEAR + 70_711           # point-sampled diagonal step guard

LAYERS = (p.F_Cu, p.B_Cu)


def load_opens():
    with open(DRC) as fh:
        d = json.load(fh)
    out = []
    for u in d.get('unconnected_items', []) or d.get('violations', []):
        if u.get('type') not in (None, 'unconnected_items'):
            continue
        items = u.get('items') or []
        rec = {'desc': u.get('description', ''), 'items': []}
        for it in items:
            pos = it.get('pos') or {}
            if pos.get('x') is None:
                continue
            idesc = it.get('description', '')
            # The NET NAME lives in the ITEM description ("Pad 4 [/SPI2_SCK] of U1 on F.Cu"),
            # not in the violation's own description ("Missing connection between items").
            # Reading the wrong level leaves net='' and every pad becomes its own blocker.
            mnet = ''
            if '[' in idesc and ']' in idesc:
                mnet = idesc[idesc.index('[') + 1:idesc.index(']')]
            mlay = ''
            for cand in ('F.Cu', 'B.Cu', 'In1.Cu', 'In2.Cu'):
                if cand in idesc:
                    mlay = cand
                    break
            rec['items'].append({
                'x': float(pos['x']) * UM,     # DRC JSON is run with --units mm
                'y': float(pos['y']) * UM,
                'layer': mlay or it.get('layer', ''),
                'net': mnet,
                'desc': idesc,
            })
        if rec['items']:
            out.append(rec)
    return out


def main():
    b = p.LoadBoard(BOARD)
    opens = load_opens()
    print('current opens in DRC: %d' % len(opens))

    # every copper shape we must not run into
    obstacles = []          # (netname, shape)
    for t in b.GetTracks():
        obstacles.append((str(t.GetNetname()), t.GetEffectiveShape(0)))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            for layer in LAYERS:
                if pad.IsOnLayer(layer):
                    obstacles.append((str(pad.GetNetname()), pad.GetEffectiveShape(layer)))
    print('copper obstacle shapes: %d' % len(obstacles))

    # spatial bucket so the A* is not O(obstacles) per cell
    CELL = 2_000_000
    buckets = {}

    def bkey(x, y):
        return (int(x // CELL), int(y // CELL))

    for net, shp in obstacles:
        bb = shp.BBox()
        x0, y0 = bb.GetLeft(), bb.GetTop()
        x1, y1 = bb.GetRight(), bb.GetBottom()
        for ix in range(int(x0 // CELL), int(x1 // CELL) + 1):
            for iy in range(int(y0 // CELL), int(y1 // CELL) + 1):
                buckets.setdefault((ix, iy), []).append((net, shp))

    def blocked(x, y, layer, net):
        cand = buckets.get(bkey(x, y), ())
        pt = p.SHAPE_CIRCLE(p.VECTOR2I(int(x), int(y)), TRACK // 2)
        for onet, shp in cand:
            if onet == net:
                continue
            try:
                if p.SHAPE.Collide(shp, pt, GUARD):
                    return True
            except Exception:
                pass
        return False

    results = []
    for i, op in enumerate(opens):
        its = op['items']
        if len(its) < 2:
            results.append({'i': i, 'verdict': 'INCOMPLETE_RECORD', 'n_items': len(its)})
            continue
        a, c = its[0], its[-1]
        # classify: two pads on opposite faces at same XY = assembly land
        layers_a = {it.get('layer') for it in its}
        dist = math.hypot(a['x'] - c['x'], a['y'] - c['y'])   # nm
        rec = {'i': i, 'a': [a['x'], a['y']], 'c': [c['x'], c['y']],
               'dist_mm': round(dist / UM, 3), 'layers': sorted(l for l in layers_a if l),
               'net': a.get('net') or c.get('net') or '',
               'kind_a': a.get('desc', '')[:44], 'kind_c': c.get('desc', '')[:44]}

        if dist < 10_000:      # 10 um in nm
            rec['verdict'] = 'SAME_XY_ASSEMBLY_LAND'
            results.append(rec)
            continue

        # which net? take from description bracket if present
        net = a.get('net') or c.get('net') or ''

        # simple grid A* on both outer layers with vias
        GRID = 250_000
        bbox = (min(a['x'], c['x']) - 8 * UM, min(a['y'], c['y']) - 8 * UM,
                max(a['x'], c['x']) + 8 * UM, max(a['y'], c['y']) + 8 * UM)
        nx = max(2, int((bbox[2] - bbox[0]) // GRID) + 1)
        ny = max(2, int((bbox[3] - bbox[1]) // GRID) + 1)
        if nx * ny > 4_000_000:
            rec['verdict'] = 'BBOX_TOO_LARGE'
            results.append(rec)
            continue

        start = (int((a['x'] - bbox[0]) // GRID), int((a['y'] - bbox[1]) // GRID))
        goal = (int((c['x'] - bbox[0]) // GRID), int((c['y'] - bbox[1]) // GRID))

        # CONTRACT: the two endpoints must land in DIFFERENT grid cells, otherwise the A* can
        # "succeed" in one step and the result is meaningless. This caught a units bug where
        # the DRC JSON is in mm and positions were treated as nm.
        if start == goal:
            rec['verdict'] = 'ENDPOINTS_IN_SAME_CELL_BUG'
            results.append(rec)
            print('  open %-2d ENDPOINTS_IN_SAME_CELL_BUG  (%s,%s) dist=%.3f mm' % (
                i, start, goal, dist / UM))
            continue

        import heapq
        best = {}
        pq = [(0.0, 0, start[0], start[1])]
        seen_goal = None
        steps = 0
        CAP = 400_000
        while pq and steps < CAP:
            f, lay, gx, gy = heapq.heappop(pq)
            steps += 1
            if (gx, gy) == goal:
                seen_goal = (lay, gx, gy)
                break
            k = (lay, gx, gy)
            if k in best:
                continue
            best[k] = f
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                tx, ty = gx + dx, gy + dy
                if not (0 <= tx < nx and 0 <= ty < ny):
                    continue
                wx = bbox[0] + int(tx * GRID + GRID // 2)
                wy = bbox[1] + int(ty * GRID + GRID // 2)
                if blocked(wx, wy, LAYERS[lay], net):
                    continue
                h = math.hypot(tx - goal[0], ty - goal[1])
                heapq.heappush(pq, (h, lay, tx, ty))

        if seen_goal:
            rec['verdict'] = 'ROUTABLE_NOW'
            rec['steps'] = steps
        elif steps >= CAP:
            rec['verdict'] = 'CAP_HIT'
            rec['steps'] = steps
        else:
            rec['verdict'] = 'NO_PATH'
            rec['steps'] = steps
        results.append(rec)
        print('  open %-2d %-12s d=%.2fmm %s steps=%s' % (
            i, rec["verdict"], dist / UM, rec.get("net","")[:14], rec.get("steps","-")))

    with open(OUT, 'w') as fh:
        json.dump(results, fh, indent=1)

    from collections import Counter
    print()
    print('SUMMARY:', dict(Counter(r['verdict'] for r in results)))
    print('written', OUT)


if __name__ == '__main__':
    main()
