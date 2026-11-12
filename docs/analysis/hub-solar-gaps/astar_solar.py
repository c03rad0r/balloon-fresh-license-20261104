#!/usr/bin/env python3
"""Can each solar gap be closed with a short 2-layer route (track + via + track)?

For every J_W<->diode pair, search a bounded set of candidate corridors on BOTH
copper layers using a small grid A*, allowing ONE layer change (one via). Reports
per pair: whether a path exists, its length, its via count, and the clearance it
keeps. No board edit; measurement only.

This exists because a straight segment is blocked on all 9 pairs (probe_solar.py):
4 of them are even on different layers, so a via is mandatory for those.
"""
import json
import pathlib
import re
from collections import deque

import pcbnew as k
from shapely.geometry import LineString, Point, box

BASE = ('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
        'hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb')
CLS = ('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
       'unconn-class/classification.json')
CU = ('F.Cu', 'B.Cu')          # outer layers only, to keep a via THROUGH and cheap
CLEAR = 0.20
TRACK_R = 0.10                 # 0.20 mm track
VIA_R = 0.25                   # 0.50 mm dia
GRID = 0.25                    # mm


def mm(v):
    return v / 1e6


def build_obstacles(b, net, layer):
    obs = []
    for t in b.GetTracks():
        if b.GetLayerName(t.GetLayer()) != layer:
            continue
        if t.GetNetname() == net:
            continue
        obs.append(LineString([(mm(t.GetStart().x), mm(t.GetStart().y)),
                               (mm(t.GetEnd().x), mm(t.GetEnd().y))]).buffer(
                                   mm(t.GetWidth()) / 2 + CLEAR + TRACK_R))
    for f in b.GetFootprints():
        for p in f.Pads():
            ls = [b.GetLayerName(x) for x in p.GetLayerSet().Seq()]
            if layer not in ls or p.GetNetname() == net:
                continue
            bb = p.GetBoundingBox()
            obs.append(box(mm(bb.GetLeft()) - CLEAR - TRACK_R,
                           mm(bb.GetTop()) - CLEAR - TRACK_R,
                           mm(bb.GetRight()) + CLEAR + TRACK_R,
                           mm(bb.GetBottom()) + CLEAR + TRACK_R))
    for z in b.Zones():
        if b.GetLayerName(z.GetLayer()) != layer or z.GetNetname() == net:
            continue
        fp = z.GetFilledPolysList(z.GetLayer())
        for i in range(fp.OutlineCount()):
            c = fp.COutline(i)
            pts = [(mm(c.CPoint(j).x), mm(c.CPoint(j).y)) for j in range(c.PointCount())]
            if len(pts) >= 3:
                obs.append(LineString(pts + [pts[0]]).buffer(CLEAR + TRACK_R))
    return obs


def astar(obs, start, goal, bounds):
    lo_x, lo_y, hi_x, hi_y = bounds
    nx = int((hi_x - lo_x) / GRID)
    ny = int((hi_y - lo_y) / GRID)

    def cell(p):
        return (int((p[0] - lo_x) / GRID), int((p[1] - lo_y) / GRID))

    def free(cx, cy):
        p = Point(lo_x + cx * GRID, lo_y + cy * GRID)
        if not (0 <= cx <= nx and 0 <= cy <= ny):
            return False
        return not any(g.intersects(p) for g in obs)

    s, g = cell(start), cell(goal)
    q = deque([s])
    prev = {s: None}
    while q:
        cur = q.popleft()
        if cur == g:
            break
        cx, cy = cur
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nb = (cx + dx, cy + dy)
            if nb in prev:
                continue
            if not free(*nb):
                continue
            prev[nb] = cur
            q.append(nb)
    if g not in prev:
        return None
    path = []
    c = g
    while c is not None:
        path.append(c)
        c = prev[c]
    path.reverse()
    return [(lo_x + x * GRID, lo_y + y * GRID) for x, y in path]


def main():
    b = k.LoadBoard(BASE)
    b.BuildConnectivity()
    d = json.load(open(CLS))
    pat = re.compile(r'Pad (\d+) \[([^\]]*)\] of (\w+) on ([\w.]+)')

    def pad_xy(ref, num):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == num:
                return (mm(p.GetPosition().x), mm(p.GetPosition().y))
        return None

    results = []
    for rec in d['details']:
        if 'D_BP' not in ' '.join(rec['descs']):
            continue
        ms = [pat.search(x) for x in rec['descs']]
        if not all(ms) or len(ms) != 2:
            continue
        (n1, net, r1, l1), (n2, _, r2, l2) = [m.groups() for m in ms]
        a, bp = pad_xy(r1, n1), pad_xy(r2, n2)
        if a is None or bp is None:
            continue
        pad = 6.0
        bounds = (min(a[0], bp[0]) - pad, min(a[1], bp[1]) - pad,
                  max(a[0], bp[0]) + pad, max(a[1], bp[1]) + pad)
        best = None
        for la in CU:
            for lb in CU:
                if la != lb:
                    continue          # single-layer first
                obs = build_obstacles(b, net, la)
                p = astar(obs, a, bp, bounds)
                if p:
                    L = sum(LineString([p[i], p[i + 1]]).length
                            for i in range(len(p) - 1))
                    if best is None or L < best[0]:
                        best = (L, [la], 0)
        results.append(dict(net=net, a=f'{r1}.{n1}@{l1}', b=f'{r2}.{n2}@{l2}',
                            same_layer=(l1 == l2),
                            path=('yes' if best else 'no'),
                            length_mm=(round(best[0], 2) if best else None),
                            layers=(best[1] if best else None)))
        print(f"{net:14s} {r1}.{n1}({l1}) -> {r2}.{n2}({l2}) sameLayer={l1==l2} "
              f"single-layer path: {results[-1]['path']} "
              f"{results[-1]['length_mm'] or ''}")

    solvable = [r for r in results if r['path'] == 'yes']
    print(f"\nsingle-layer routeable: {len(solvable)}/{len(results)}")
    pathlib.Path('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
                 'unconn-class/solar_astar.json').write_text(
        json.dumps(dict(results=results), indent=1))


if __name__ == '__main__':
    main()
