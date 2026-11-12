#!/usr/bin/env python3
"""Apply the solar-gap routes that A* proved, then verify with native DRC.

Only routes whose A* path exists on a layer where BOTH pads have copper are
applied. Because every J_W pad is a dual-face land at identical XY (measured),
a route landing on the J_W B.Cu face is electrically valid - the inserted wing
tab bridges the faces.

Writes to a COPY. The source candidate is never modified.
"""
import json
import pathlib
import shutil
import subprocess

import pcbnew as k
from shapely.geometry import LineString, Point, box

SRC = pathlib.Path('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
                   'hub-repair-20261102/output/after')
OUT = pathlib.Path('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/solar-fix')
STEM = 'hub_board_v10_lora1280_7of9'
CLEAR = 0.20
TRACK_R = 0.10
GRID = 0.25
CU = ('F.Cu', 'B.Cu')


def mm(v):
    return v / 1e6


def obstacles(b, net, layer):
    obs = []
    for t in b.GetTracks():
        if b.GetLayerName(t.GetLayer()) != layer or t.GetNetname() == net:
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
    return obs


def astar(obs, start, goal, bounds):
    lo_x, lo_y, hi_x, hi_y = bounds
    def cell(p):
        return (int((p[0] - lo_x) / GRID), int((p[1] - lo_y) / GRID))
    def free(cx, cy):
        p = Point(lo_x + cx * GRID, lo_y + cy * GRID)
        return not any(g.intersects(p) for g in obs)
    from collections import deque
    s, g = cell(start), cell(goal)
    q, prev = deque([s]), {s: None}
    while q:
        cur = q.popleft()
        if cur == g:
            break
        cx, cy = cur
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nb = (cx + dx, cy + dy)
            if nb in prev or not free(*nb):
                continue
            prev[nb] = cur
            q.append(nb)
    if g not in prev:
        return None
    path, c = [], g
    while c is not None:
        path.append(c)
        c = prev[c]
    path.reverse()
    return [(lo_x + x * GRID, lo_y + y * GRID) for x, y in path]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for f in SRC.glob(STEM + '.kicad_*'):
        shutil.copy(f, OUT / f.name)
    pcb = OUT / (STEM + '.kicad_pcb')

    b = k.LoadBoard(str(pcb))
    b.BuildConnectivity()
    before = b.GetConnectivity().GetUnconnectedCount(False)

    # the two provable pairs, on the layer where both pads carry copper
    pairs = [
        ('/W3_SOLAR_N', 'J_W4', '1', 'D_BP4', '1'),
    ]

    added = 0
    for net, ra, na, rb, nb_ in pairs:
        fa = b.FindFootprintByReference(ra)
        fb = b.FindFootprintByReference(rb)
        if not fa or not fb:
            print('missing footprint', ra, rb)
            continue
        pa = [p for p in fa.Pads() if p.GetNumber() == na][0]
        pb = [p for p in fb.Pads() if p.GetNumber() == nb_][0]
        a = (mm(pa.GetPosition().x), mm(pa.GetPosition().y))
        c = (mm(pb.GetPosition().x), mm(pb.GetPosition().y))
        # route on the layer that BOTH pads share
        la = set(b.GetLayerName(x) for x in pa.GetLayerSet().Seq())
        lb = set(b.GetLayerName(x) for x in pb.GetLayerSet().Seq())
        shared = [l for l in CU if l in la and l in lb]
        if not shared:
            print(f'{net}: no shared outer layer {la & lb}')
            continue
        for layer in shared:
            obs = obstacles(b, net, layer)
            pad = 6.0
            bounds = (min(a[0], c[0]) - pad, min(a[1], c[1]) - pad,
                      max(a[0], c[0]) + pad, max(a[1], c[1]) + pad)
            path = astar(obs, a, c, bounds)
            if not path:
                continue
            print(f'{net}: routing {ra}.{na} -> {rb}.{nb_} on {layer}, '
                  f'{len(path)} pts')
            for i in range(len(path) - 1):
                t = k.PCB_TRACK(b)
                t.SetStart(k.VECTOR2I(int(round(path[i][0] * 1e6)),
                                      int(round(path[i][1] * 1e6))))
                t.SetEnd(k.VECTOR2I(int(round(path[i + 1][0] * 1e6)),
                                    int(round(path[i + 1][1] * 1e6))))
                t.SetWidth(int(round(0.20 * 1e6)))
                t.SetLayer(b.GetLayerID(layer))
                t.SetNet(b.FindNet(net))
                b.Add(t)
                added += 1
            break

    if added:
        k.ZONE_FILLER(b).Fill(b.Zones())
        k.SaveBoard(str(pcb), b)

    b2 = k.LoadBoard(str(pcb))
    b2.BuildConnectivity()
    after = b2.GetConnectivity().GetUnconnectedCount(False)
    print(f'\ntracks added: {added}')
    print(f'unconnected {before} -> {after}  (delta {after - before:+d})')

    drc = OUT / 'drc.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', str(drc),
                    '--severity-all', str(pcb)], capture_output=True, text=True)
    d = json.loads(drc.read_text())
    print(f'violations: {len(d["violations"])}  unconnected: {len(d["unconnected_items"])}')

    (OUT / 'result.json').write_text(json.dumps(dict(
        tracks_added=added, before=before, after=after,
        violations=len(d['violations'])), indent=1))


if __name__ == '__main__':
    main()
